"""Filesystem-backed event mailbox for web chat sessions."""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable

from loguru import logger

from miniclaw.utils.helpers import safe_filename


@dataclass(slots=True)
class PendingWebEvent:
    path: Path
    event: dict[str, Any]


class WebEventMailbox:
    """Share outbound web-session events across processes via the workspace."""

    def __init__(self, workspace: Path):
        self.workspace = Path(workspace)

    def _session_dir(self, session_id: str) -> Path:
        safe_key = safe_filename(session_id.replace(":", "_"))
        return self.workspace / "web-mailbox" / safe_key

    def enqueue(self, session_id: str, event: dict[str, Any]) -> None:
        directory = self._session_dir(session_id)
        directory.mkdir(parents=True, exist_ok=True)
        stem = f"{time.time_ns()}-{uuid.uuid4().hex}"
        tmp_path = directory / f"{stem}.tmp"
        final_path = directory / f"{stem}.json"
        tmp_path.write_text(json.dumps(event, ensure_ascii=False), encoding="utf-8")
        tmp_path.replace(final_path)

    def list_pending(self, session_id: str, limit: int = 100) -> list[PendingWebEvent]:
        directory = self._session_dir(session_id)
        if not directory.exists():
            return []

        pending: list[PendingWebEvent] = []
        for path in sorted(directory.glob("*.json"))[:limit]:
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except Exception as exc:
                logger.warning("Dropping unreadable web mailbox event {}: {}", path, exc)
                self.ack(path)
                continue
            if not isinstance(payload, dict):
                logger.warning("Dropping malformed web mailbox event {}", path)
                self.ack(path)
                continue
            pending.append(PendingWebEvent(path=path, event=payload))
        return pending

    def ack(self, path: Path) -> None:
        try:
            path.unlink(missing_ok=True)
        except TypeError:
            if path.exists():
                path.unlink()


async def deliver_pending_events(
    mailbox: WebEventMailbox,
    session_id: str,
    send_event: Callable[[dict[str, Any]], Awaitable[None]],
    *,
    limit: int = 100,
) -> int:
    """Deliver and ack all currently pending events for one web session."""

    delivered = 0
    for item in mailbox.list_pending(session_id, limit=limit):
        await send_event(item.event)
        mailbox.ack(item.path)
        delivered += 1
    return delivered
