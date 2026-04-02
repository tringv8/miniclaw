from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from miniclaw.config.loader import load_config
from miniclaw.utils.helpers import safe_filename


def _session_paths(config_path: Path, session_id: str) -> list[Path]:
    cfg = load_config(config_path)
    safe_key = safe_filename(session_id.replace(":", "_"))
    workspace_path = cfg.workspace_path / "sessions" / f"{safe_key}.jsonl"
    legacy_path = Path.home() / ".miniclaw" / "sessions" / f"{safe_key}.jsonl"
    return [workspace_path, legacy_path]


def _parse_session_file(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None

    metadata: dict[str, Any] = {}
    messages: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            payload = json.loads(line)
            if payload.get("_type") == "metadata":
                metadata = payload
            else:
                messages.append(payload)

    key = str(metadata.get("key") or path.stem.replace("_", ":", 1))
    created = metadata.get("created_at") or metadata.get("created") or ""
    updated = metadata.get("updated_at") or metadata.get("updated") or ""
    summary = str((metadata.get("metadata") or {}).get("summary") or metadata.get("summary") or "")
    return {
        "id": key,
        "created": created,
        "updated": updated,
        "summary": summary,
        "messages": messages,
        "path": path,
    }


def _user_preview(messages: list[dict[str, Any]]) -> str:
    for message in messages:
        if message.get("role") == "user" and str(message.get("content") or "").strip():
            return str(message.get("content") or "").strip()
    return ""


def _message_count(messages: list[dict[str, Any]]) -> int:
    return sum(
        1
        for message in messages
        if message.get("role") in {"user", "assistant"} and str(message.get("content") or "").strip()
    )


def list_sessions(config_path: Path, offset: int = 0, limit: int = 20) -> list[dict[str, Any]]:
    cfg = load_config(config_path)
    candidates = [cfg.workspace_path / "sessions", Path.home() / ".miniclaw" / "sessions"]
    seen: set[str] = set()
    items: list[dict[str, Any]] = []

    for directory in candidates:
        if not directory.exists():
            continue
        for path in directory.glob("*.jsonl"):
            parsed = _parse_session_file(path)
            if not parsed or parsed["id"] in seen:
                continue
            seen.add(parsed["id"])
            preview = _user_preview(parsed["messages"])
            title = (parsed["summary"] or preview or "(empty)").strip()
            items.append(
                {
                    "id": parsed["id"],
                    "title": title[:60],
                    "preview": (preview or "(empty)")[:60],
                    "message_count": _message_count(parsed["messages"]),
                    "created": parsed["created"],
                    "updated": parsed["updated"],
                }
            )

    items.sort(key=lambda item: str(item.get("updated") or item.get("created") or ""), reverse=True)
    return items[offset : offset + limit]


def get_session_detail(config_path: Path, session_id: str) -> dict[str, Any] | None:
    for path in _session_paths(config_path, session_id):
        parsed = _parse_session_file(path)
        if not parsed:
            continue
        return {
            "id": parsed["id"],
            "messages": [
                {
                    "role": str(message.get("role") or ""),
                    "content": str(message.get("content") or ""),
                }
                for message in parsed["messages"]
                if message.get("role") in {"user", "assistant"} and str(message.get("content") or "").strip()
            ],
            "summary": parsed["summary"],
            "created": parsed["created"],
            "updated": parsed["updated"],
        }
    return None


def delete_session(config_path: Path, session_id: str) -> bool:
    removed = False
    for path in _session_paths(config_path, session_id):
        if path.exists():
            path.unlink()
            removed = True
    return removed
