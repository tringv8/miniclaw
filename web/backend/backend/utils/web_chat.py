from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from miniclaw.agent.loop import AgentLoop
from miniclaw.bus.queue import MessageBus
from miniclaw.config.loader import set_config_path
from miniclaw.config.schema import Config
from miniclaw.cron.service import CronService
from miniclaw.session.manager import SessionManager
from miniclaw.utils.helpers import sync_workspace_templates

from backend.utils.config_store import load_raw_config

ChatEventSender = Callable[[dict[str, Any]], Awaitable[None]]


def _timestamp_ms() -> int:
    return int(time.time() * 1000)


def _make_provider(config: Config):
    from miniclaw.providers.base import GenerationSettings
    from miniclaw.providers.registry import find_by_name

    model = config.agents.defaults.model
    provider_name = config.get_provider_name(model)
    provider_config = config.get_provider(model)
    spec = find_by_name(provider_name) if provider_name else None
    backend = spec.backend if spec else "openai_compat"

    if backend == "azure_openai":
        if not provider_config or not provider_config.api_key or not provider_config.api_base:
            raise RuntimeError("Azure OpenAI requires api_key and api_base.")
    elif backend == "openai_compat" and not model.startswith("bedrock/"):
        needs_key = not (provider_config and provider_config.api_key)
        exempt = spec and (spec.is_oauth or spec.is_local or spec.is_direct)
        if needs_key and not exempt:
            raise RuntimeError("No API key configured for the selected model.")

    if backend == "openai_codex":
        from miniclaw.providers.openai_codex_provider import OpenAICodexProvider

        provider = OpenAICodexProvider(default_model=model)
    elif backend == "azure_openai":
        from miniclaw.providers.azure_openai_provider import AzureOpenAIProvider

        provider = AzureOpenAIProvider(
            api_key=provider_config.api_key,
            api_base=provider_config.api_base,
            default_model=model,
        )
    elif backend == "anthropic":
        from miniclaw.providers.anthropic_provider import AnthropicProvider

        provider = AnthropicProvider(
            api_key=provider_config.api_key if provider_config else None,
            api_base=config.get_api_base(model),
            default_model=model,
            extra_headers=provider_config.extra_headers if provider_config else None,
        )
    else:
        from miniclaw.providers.openai_compat_provider import OpenAICompatProvider

        provider = OpenAICompatProvider(
            api_key=provider_config.api_key if provider_config else None,
            api_base=config.get_api_base(model),
            default_model=model,
            extra_headers=provider_config.extra_headers if provider_config else None,
            spec=spec,
        )

    defaults = config.agents.defaults
    provider.generation = GenerationSettings(
        temperature=defaults.temperature,
        max_tokens=defaults.max_tokens,
        reasoning_effort=defaults.reasoning_effort,
    )
    return provider


class WebChatRuntime:
    def __init__(self, config_path: Path) -> None:
        self.config_path = config_path
        self._session_locks: dict[str, asyncio.Lock] = {}

    def _load_config(self) -> Config:
        set_config_path(self.config_path)
        payload = load_raw_config(self.config_path)
        return Config.model_validate(payload)

    def _build_agent(self) -> AgentLoop:
        config = self._load_config()
        sync_workspace_templates(config.workspace_path)
        provider = _make_provider(config)
        session_manager = SessionManager(config.workspace_path)
        cron = CronService(config.workspace_path / "cron" / "jobs.json")
        return AgentLoop(
            bus=MessageBus(),
            provider=provider,
            workspace=config.workspace_path,
            model=config.agents.defaults.model,
            max_iterations=config.agents.defaults.max_tool_iterations,
            context_window_tokens=config.agents.defaults.context_window_tokens,
            web_search_config=config.tools.web.search,
            web_proxy=config.tools.web.proxy or None,
            exec_config=config.tools.exec,
            cron_service=cron,
            restrict_to_workspace=config.tools.restrict_to_workspace,
            session_manager=session_manager,
            mcp_servers=config.tools.mcp_servers,
            channels_config=config.channels,
            timezone=config.agents.defaults.timezone,
        )

    async def stream_message(
        self,
        *,
        session_id: str,
        content: str,
        send_event: ChatEventSender,
    ) -> None:
        lock = self._session_locks.setdefault(session_id, asyncio.Lock())
        async with lock:
            await send_event({"type": "typing.start", "timestamp": _timestamp_ms()})
            agent: AgentLoop | None = None
            assistant_message_id = f"web-{time.time_ns()}"
            streamed_content = ""
            has_streamed = False

            async def on_stream(delta: str) -> None:
                nonlocal streamed_content, has_streamed
                streamed_content += delta
                await send_event(
                    {
                        "type": "message.create" if not has_streamed else "message.update",
                        "timestamp": _timestamp_ms(),
                        "payload": {
                            "message_id": assistant_message_id,
                            "content": streamed_content,
                        },
                    }
                )
                has_streamed = True

            try:
                agent = self._build_agent()
                response = await agent.process_direct(
                    content,
                    session_key=session_id,
                    channel="web",
                    chat_id=session_id,
                    on_stream=on_stream,
                )
                final_content = (response.content if response else "") or ""

                if not has_streamed and final_content:
                    streamed_content = final_content
                    has_streamed = True
                    await send_event(
                        {
                            "type": "message.create",
                            "timestamp": _timestamp_ms(),
                            "payload": {
                                "message_id": assistant_message_id,
                                "content": streamed_content,
                            },
                        }
                    )
                elif has_streamed and final_content and final_content != streamed_content:
                    streamed_content = final_content
                    await send_event(
                        {
                            "type": "message.update",
                            "timestamp": _timestamp_ms(),
                            "payload": {
                                "message_id": assistant_message_id,
                                "content": streamed_content,
                            },
                        }
                    )
                elif not has_streamed:
                    await send_event(
                        {
                            "type": "error",
                            "timestamp": _timestamp_ms(),
                            "payload": {
                                "message": "No response content was produced.",
                            },
                        }
                    )
            except BaseException as exc:
                if isinstance(exc, asyncio.CancelledError):
                    raise
                await send_event(
                    {
                        "type": "error",
                        "timestamp": _timestamp_ms(),
                        "payload": {"message": str(exc) or "Chat request failed."},
                    }
                )
            finally:
                if agent is not None:
                    await agent.close_mcp()
                await send_event({"type": "typing.stop", "timestamp": _timestamp_ms()})
