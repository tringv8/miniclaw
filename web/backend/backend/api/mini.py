from __future__ import annotations

import hmac
import secrets
import uuid
from typing import Any

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect, status

from backend.middleware.launcher_dashboard_auth import COOKIE_NAME
from backend.utils.channels_catalog import web_channel_enabled

router = APIRouter()


def _forwarded_proto(request: Request) -> str:
    raw = request.headers.get("x-forwarded-proto", "").split(",", 1)[0].strip().lower()
    if raw in {"https", "wss"}:
        return "wss"
    if raw in {"http", "ws"}:
        return "ws"
    return "wss" if request.url.scheme == "https" else "ws"


def _forwarded_host(request: Request) -> str:
    raw = request.headers.get("x-forwarded-host", "").split(",", 1)[0].strip()
    if raw:
        return raw
    host = request.headers.get("host", "").strip()
    if host:
        return host
    return request.url.netloc or "localhost"


def _build_ws_url(request: Request) -> str:
    return f"{_forwarded_proto(request)}://{_forwarded_host(request)}/mini/ws"


def _websocket_protocols(websocket: WebSocket) -> list[str]:
    raw = websocket.headers.get("sec-websocket-protocol", "")
    return [item.strip() for item in raw.split(",") if item.strip()]


def _authorize_websocket(websocket: WebSocket) -> tuple[bool, str | None]:
    context = websocket.app.state.launcher_context
    cookie = websocket.cookies.get(COOKIE_NAME, "")
    if cookie and hmac.compare_digest(cookie, context.dashboard_session_cookie):
        protocols = _websocket_protocols(websocket)
        return True, protocols[0] if protocols else None

    for protocol in _websocket_protocols(websocket):
        if protocol.startswith("token.") and hmac.compare_digest(protocol[6:], context.chat_ws_token):
            return True, protocol
    return False, None


async def _send_ws_event(websocket: WebSocket, session_id: str, event: dict[str, Any]) -> None:
    payload = dict(event)
    payload["session_id"] = session_id
    await websocket.send_json(payload)


@router.get("/api/mini/token")
async def get_mini_token(request: Request):
    context = request.app.state.launcher_context
    enabled = web_channel_enabled(context.config_path)
    return {
        "token": context.chat_ws_token,
        "ws_url": _build_ws_url(request),
        "enabled": enabled,
    }


@router.post("/api/mini/token")
async def regen_mini_token(request: Request):
    context = request.app.state.launcher_context
    context.chat_ws_token = secrets.token_urlsafe(24)
    enabled = web_channel_enabled(context.config_path)
    return {
        "token": context.chat_ws_token,
        "ws_url": _build_ws_url(request),
        "enabled": enabled,
    }


@router.post("/api/mini/setup")
async def setup_mini(request: Request):
    context = request.app.state.launcher_context
    enabled = web_channel_enabled(context.config_path)
    return {
        "token": context.chat_ws_token,
        "ws_url": _build_ws_url(request),
        "enabled": enabled,
        "changed": False,
    }


@router.websocket("/mini/ws")
async def mini_websocket(websocket: WebSocket):
    authorized, selected_subprotocol = _authorize_websocket(websocket)
    if not authorized:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    context = websocket.app.state.launcher_context
    if not web_channel_enabled(context.config_path):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="web channel disabled")
        return

    await websocket.accept(subprotocol=selected_subprotocol)
    session_id = websocket.query_params.get("session_id", "").strip() or str(uuid.uuid4())

    try:
        while True:
            payload = await websocket.receive_json()
            if not isinstance(payload, dict):
                await _send_ws_event(
                    websocket,
                    session_id,
                    {
                        "type": "error",
                        "payload": {"message": "Invalid WebSocket payload."},
                    },
                )
                continue

            message_type = str(payload.get("type") or "")
            if message_type == "ping":
                await _send_ws_event(websocket, session_id, {"type": "pong"})
                continue

            if message_type != "message.send":
                await _send_ws_event(
                    websocket,
                    session_id,
                    {
                        "type": "error",
                        "payload": {"message": f"Unsupported message type: {message_type or 'unknown'}"},
                    },
                )
                continue

            message_payload = payload.get("payload")
            content = ""
            if isinstance(message_payload, dict):
                content = str(message_payload.get("content") or "").strip()

            if not content:
                await _send_ws_event(
                    websocket,
                    session_id,
                    {
                        "type": "error",
                        "payload": {"message": "Message content is required."},
                    },
                )
                continue

            await context.chat_runtime.stream_message(
                session_id=session_id,
                content=content,
                send_event=lambda event: _send_ws_event(websocket, session_id, event),
            )
    except WebSocketDisconnect:
        return
    except RuntimeError:
        return
