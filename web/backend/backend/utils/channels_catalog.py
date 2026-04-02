from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from backend.utils.config_store import load_raw_config

TELEGRAM_DEFAULTS: dict[str, Any] = {
    "enabled": False,
    "token": "",
    "base_url": "https://api.telegram.org",
    "proxy": "http://127.0.0.1:7890",
    "allow_from": [],
    "typing": {"enabled": False},
    "placeholder": {
        "enabled": False,
        "text": "Thinking...",
    },
}

WEB_DEFAULTS: dict[str, Any] = {
    "enabled": True,
    "ping_interval": 30,
    "read_timeout": 60,
    "write_timeout": 10,
    "max_connections": 100,
    "allow_from": [],
    "placeholder": {
        "enabled": False,
        "text": "Thinking...",
    },
}


def launcher_channel_catalog() -> list[dict[str, Any]]:
    return [
        {
            "name": "web",
            "display_name": "Web",
            "config_key": "web",
            "defaults": deepcopy(WEB_DEFAULTS),
        },
        {
            "name": "telegram",
            "display_name": "Telegram",
            "config_key": "telegram",
            "defaults": deepcopy(TELEGRAM_DEFAULTS),
        },
    ]


def web_channel_enabled(config_path: Path) -> bool:
    raw = load_raw_config(config_path)
    channels = raw.get("channels") or {}
    web = channels.get("web") or {}
    if not isinstance(web, dict):
        return bool(WEB_DEFAULTS["enabled"])
    enabled = web.get("enabled")
    if enabled is None:
        return bool(WEB_DEFAULTS["enabled"])
    return enabled is True
