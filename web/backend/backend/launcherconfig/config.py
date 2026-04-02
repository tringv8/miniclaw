from __future__ import annotations

import base64
import ipaddress
import json
import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path

FILE_NAME = "launcher-config.json"
DEFAULT_PORT = 18801
SESSION_MAX_AGE_SECONDS = 7 * 24 * 3600
_SIGNING_KEY_BYTES = 32
_TOKEN_BYTES = 32
_TOKEN_ENV = "MINICLAW_LAUNCHER_TOKEN"


@dataclass(slots=True)
class LauncherConfig:
    port: int = DEFAULT_PORT
    public: bool = False
    allowed_cidrs: list[str] = field(default_factory=list)


def normalize_cidrs(cidrs: list[str] | None) -> list[str]:
    if not cidrs:
        return []
    seen: set[str] = set()
    result: list[str] = []
    for item in cidrs:
        value = str(item).strip()
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def validate(cfg: LauncherConfig) -> None:
    if cfg.port < 1 or cfg.port > 65535:
        raise ValueError(f"port {cfg.port} is out of range (1-65535)")
    for cidr in cfg.allowed_cidrs:
        ipaddress.ip_network(cidr, strict=False)


def path_for_app_config(app_config_path: Path) -> Path:
    return app_config_path.parent / FILE_NAME


def load(path: Path, fallback: LauncherConfig | None = None) -> LauncherConfig:
    cfg = fallback or LauncherConfig()
    if not path.exists():
        return cfg

    data = json.loads(path.read_text(encoding="utf-8-sig"))
    loaded = LauncherConfig(
        port=int(data.get("port", cfg.port)),
        public=bool(data.get("public", cfg.public)),
        allowed_cidrs=normalize_cidrs(data.get("allowed_cidrs", cfg.allowed_cidrs)),
    )
    validate(loaded)
    return loaded


def save(path: Path, cfg: LauncherConfig) -> LauncherConfig:
    cfg.allowed_cidrs = normalize_cidrs(cfg.allowed_cidrs)
    validate(cfg)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "port": cfg.port,
        "public": cfg.public,
        "allowed_cidrs": cfg.allowed_cidrs,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return cfg


def ensure_dashboard_secrets() -> tuple[str, bytes, bool]:
    token = os.environ.get(_TOKEN_ENV, "").strip()
    signing_key = secrets.token_bytes(_SIGNING_KEY_BYTES)
    if token:
        return token, signing_key, False
    generated = base64.urlsafe_b64encode(secrets.token_bytes(_TOKEN_BYTES)).decode("ascii").rstrip("=")
    return generated, signing_key, True
