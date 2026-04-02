from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.utils.config_store import load_raw_config, save_raw_config
from backend.utils.oauth_native import delete_openai_oauth_token, load_openai_oauth_status

TOKEN_METHOD = "token"
BROWSER_METHOD = "browser"
DEVICE_CODE_METHOD = "device_code"

PROVIDER_CATALOG = [
    {
        "provider": "openai",
        "display_name": "OpenAI",
        "methods": [BROWSER_METHOD, DEVICE_CODE_METHOD, TOKEN_METHOD],
        "description": "Supports browser OAuth, device code, and token login.",
    },
    {
        "provider": "anthropic",
        "display_name": "Anthropic",
        "methods": [TOKEN_METHOD],
        "description": "Uses token login for Claude access.",
    },
    {
        "provider": "google-antigravity",
        "display_name": "Google Antigravity",
        "methods": [BROWSER_METHOD],
        "description": "Uses browser OAuth for Google Cloud Code Assist.",
    },
]


def list_provider_statuses(config_path: Path) -> list[dict[str, Any]]:
    raw = load_raw_config(config_path)
    providers = raw.get("providers") or {}
    statuses: list[dict[str, Any]] = []

    openai_oauth = detect_openai_codex_status()

    for item in PROVIDER_CATALOG:
        provider = item["provider"]
        if provider == "openai":
            block = providers.get("openai") or {}
            api_key = str(block.get("apiKey") or block.get("api_key") or "")
            token_logged_in = bool(api_key)
            oauth_logged_in = bool(openai_oauth.get("logged_in"))
            preferred = str(block.get("authMethod") or block.get("auth_method") or "").strip()
            auth_method = ""
            status = str(openai_oauth.get("status") or "not_logged_in")
            if preferred == "oauth" and oauth_logged_in:
                auth_method = "oauth"
            elif preferred == TOKEN_METHOD and token_logged_in:
                auth_method = TOKEN_METHOD
                status = "connected"
            elif token_logged_in:
                auth_method = TOKEN_METHOD
                status = "connected"
            elif oauth_logged_in:
                auth_method = "oauth"
            statuses.append(
                {
                    **item,
                    "logged_in": bool(auth_method),
                    "status": status,
                    "auth_method": auth_method,
                    "supports_token_input": True,
                    "supports_logout": token_logged_in or oauth_logged_in,
                    "account_id": openai_oauth.get("account_id", "") if auth_method == "oauth" else "",
                    "expires_at": openai_oauth.get("expires_at", "") if auth_method == "oauth" else "",
                    "help_text": item["description"],
                    "setup_command": "",
                }
            )
            continue

        if provider == "anthropic":
            block = providers.get("anthropic") or {}
            api_key = str(block.get("apiKey") or block.get("api_key") or "")
            statuses.append(
                {
                    **item,
                    "logged_in": bool(api_key),
                    "status": "connected" if api_key else "not_logged_in",
                    "auth_method": TOKEN_METHOD if api_key else "",
                    "supports_token_input": True,
                    "supports_logout": bool(api_key),
                    "help_text": item["description"],
                    "setup_command": "",
                }
            )
            continue

        statuses.append(
            {
                **item,
                "logged_in": False,
                "status": "not_logged_in",
                "auth_method": "",
                "help_text": item["description"],
                "supports_token_input": False,
                "supports_logout": False,
                "setup_command": "",
            }
        )

    return statuses


def save_provider_token(config_path: Path, provider: str, token: str) -> dict[str, Any]:
    if provider not in {"openai", "anthropic"}:
        raise ValueError(f"provider {provider!r} does not support token login in this launcher")
    raw = load_raw_config(config_path)
    providers = raw.setdefault("providers", {})
    block = providers.get(provider)
    if not isinstance(block, dict):
        block = {}
    block["apiKey"] = token.strip()
    block["authMethod"] = TOKEN_METHOD
    providers[provider] = block
    save_raw_config(config_path, raw)
    return {"status": "ok", "provider": provider, "method": TOKEN_METHOD}


def mark_provider_oauth(config_path: Path, provider: str) -> dict[str, Any]:
    if provider != "openai":
        raise ValueError(f"provider {provider!r} does not support browser oauth in this launcher")
    raw = load_raw_config(config_path)
    providers = raw.setdefault("providers", {})
    block = providers.get(provider)
    if not isinstance(block, dict):
        block = {}
    block["authMethod"] = "oauth"
    providers[provider] = block
    save_raw_config(config_path, raw)
    return {"status": "ok", "provider": provider, "method": "oauth"}


def clear_provider_token(config_path: Path, provider: str) -> dict[str, Any]:
    if provider not in {"openai", "anthropic"}:
        raise ValueError(f"provider {provider!r} cannot be logged out from this launcher")
    raw = load_raw_config(config_path)
    providers = raw.setdefault("providers", {})
    block = providers.get(provider)
    if not isinstance(block, dict):
        block = {}
    block["apiKey"] = ""
    block["authMethod"] = ""
    providers[provider] = block
    save_raw_config(config_path, raw)
    if provider == "openai":
        delete_openai_oauth_token()
    return {"status": "ok", "provider": provider}


def detect_openai_codex_status() -> dict[str, Any]:
    return load_openai_oauth_status()
