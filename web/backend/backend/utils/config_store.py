from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from miniclaw.config.loader import get_config_path
from miniclaw.config.schema import Config


def resolve_config_path(explicit: str | None = None) -> Path:
    return Path(explicit).expanduser().resolve() if explicit else get_config_path().resolve()


def default_config_payload() -> dict[str, Any]:
    return Config().model_dump(mode="json", by_alias=True)


def _migrate_data(data: dict[str, Any]) -> dict[str, Any]:
    tools = data.get("tools", {})
    exec_cfg = tools.get("exec", {})
    if "restrictToWorkspace" in exec_cfg and "restrictToWorkspace" not in tools:
        tools["restrictToWorkspace"] = exec_cfg.pop("restrictToWorkspace")
    return data


def load_raw_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        return default_config_payload()
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError("config file must contain a JSON object")
    return _migrate_data(data)


def validate_payload(payload: dict[str, Any]) -> Config:
    return Config.model_validate(payload)


def normalize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return validate_payload(payload).model_dump(mode="json", by_alias=True)


def save_raw_config(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_payload(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(normalized, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return normalized


def merge_patch(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    result = json.loads(json.dumps(base))
    _merge_patch_into(result, patch)
    return result


def _merge_patch_into(target: dict[str, Any], patch: dict[str, Any]) -> None:
    for key, value in patch.items():
        if value is None:
            target.pop(key, None)
            continue
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _merge_patch_into(target[key], value)
            continue
        target[key] = value


def command_pattern_result(
    command: str,
    allow_patterns: list[str] | None = None,
    deny_patterns: list[str] | None = None,
) -> dict[str, Any]:
    lowered = command.strip().lower()
    response = {
        "allowed": False,
        "blocked": False,
        "matched_whitelist": None,
        "matched_blacklist": None,
    }

    for pattern in allow_patterns or []:
        try:
            if re.compile(pattern).search(lowered):
                response["allowed"] = True
                response["matched_whitelist"] = pattern
                return response
        except re.error:
            continue

    for pattern in deny_patterns or []:
        try:
            if re.compile(pattern).search(lowered):
                response["blocked"] = True
                response["matched_blacklist"] = pattern
                break
        except re.error:
            continue

    return response
