"""Outbound-only web channel backed by the shared web mailbox."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from pydantic import Field

from miniclaw.bus.events import OutboundMessage
from miniclaw.bus.queue import MessageBus
from miniclaw.channels.base import BaseChannel
from miniclaw.config.loader import load_config
from miniclaw.config.schema import Base
from miniclaw.web_events import WebEventMailbox


def _timestamp_ms() -> int:
    return int(time.time() * 1000)


@dataclass
class _StreamState:
    text: str
    message_id: str
    created: bool = False


class WebConfig(Base):
    enabled: bool = True
    allow_from: list[str] = Field(default_factory=lambda: ["*"])
    streaming: bool = True


class WebChannel(BaseChannel):
    """File-backed bridge used by the gateway to deliver events to web sessions."""

    name = "web"
    display_name = "Web"

    @classmethod
    def default_config(cls) -> dict[str, Any]:
        return WebConfig().model_dump(by_alias=True)

    def __init__(self, config: Any, bus: MessageBus):
        if isinstance(config, dict):
            config = WebConfig.model_validate(config)
        super().__init__(config, bus)
        self.config: WebConfig = config
        self._mailbox = WebEventMailbox(load_config().workspace_path)
        self._stream_states: dict[str, _StreamState] = {}

    async def start(self) -> None:
        self._running = True

    async def stop(self) -> None:
        self._running = False
        self._stream_states.clear()

    async def send(self, msg: OutboundMessage) -> None:
        # Progress chatter is noisy in the web UI; keep cron/heartbeat delivery
        # focused on final messages.
        if msg.metadata.get("_progress"):
            return
        event = {
            "type": "message.create",
            "timestamp": _timestamp_ms(),
            "payload": {
                "message_id": self._message_id(msg.chat_id, msg.metadata),
                "content": msg.content,
            },
        }
        self._mailbox.enqueue(msg.chat_id, event)

    async def send_delta(
        self, chat_id: str, delta: str, metadata: dict[str, Any] | None = None
    ) -> None:
        metadata = metadata or {}
        stream_key = f"{chat_id}:{metadata.get('_stream_id') or 'default'}"
        state = self._stream_states.get(stream_key)
        if state is None:
            state = _StreamState(
                text="",
                message_id=self._message_id(chat_id, metadata, prefix="web-stream"),
            )
            self._stream_states[stream_key] = state

        if delta:
            state.text += delta
            event_type = "message.create" if not state.created else "message.update"
            event = {
                "type": event_type,
                "timestamp": _timestamp_ms(),
                "payload": {
                    "message_id": state.message_id,
                    "content": state.text,
                },
            }
            self._mailbox.enqueue(chat_id, event)
            state.created = True

        if metadata.get("_stream_end"):
            self._stream_states.pop(stream_key, None)

    @staticmethod
    def _message_id(chat_id: str, metadata: dict[str, Any], prefix: str = "web-bg") -> str:
        raw = metadata.get("message_id")
        if isinstance(raw, str) and raw.strip():
            return raw
        stream_id = metadata.get("_stream_id")
        if isinstance(stream_id, str) and stream_id.strip():
            return f"{prefix}-{stream_id}"
        return f"{prefix}-{chat_id}-{time.time_ns()}"
