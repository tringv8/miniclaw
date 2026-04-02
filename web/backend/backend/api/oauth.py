from __future__ import annotations

import json
import secrets
import threading
from datetime import datetime, timedelta, timezone
from html import escape
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from backend.utils.model_store import sync_provider_auth_state
from backend.utils.oauth_native import (
    build_openai_authorize_url,
    exchange_openai_code_for_token,
    generate_pkce,
    generate_state,
    openai_provider_config,
    poll_openai_device_code_once,
    request_openai_device_code,
    save_openai_oauth_token,
    start_openai_callback_server,
)
from backend.utils.oauth_store import (
    BROWSER_METHOD,
    DEVICE_CODE_METHOD,
    TOKEN_METHOD,
    clear_provider_token,
    list_provider_statuses,
    mark_provider_oauth,
    save_provider_token,
)

router = APIRouter()

FLOW_PENDING = "pending"
FLOW_SUCCESS = "success"
FLOW_ERROR = "error"
FLOW_EXPIRED = "expired"

BROWSER_FLOW_TTL = timedelta(minutes=10)
DEVICE_FLOW_TTL = timedelta(minutes=15)
TERMINAL_FLOW_GC = timedelta(minutes=30)

oauth_now = lambda: datetime.now(timezone.utc)
oauth_generate_pkce = generate_pkce
oauth_generate_state = generate_state
oauth_build_authorize_url = build_openai_authorize_url
oauth_request_device_code = request_openai_device_code
oauth_poll_device_code_once = poll_openai_device_code_once
oauth_exchange_code_for_tokens = exchange_openai_code_for_token
oauth_save_openai_token = save_openai_oauth_token
oauth_mark_provider_oauth = mark_provider_oauth
oauth_openai_provider_config = openai_provider_config
oauth_start_openai_callback_server = start_openai_callback_server


def _flow_store(request: Request) -> dict[str, dict[str, Any]]:
    if not hasattr(request.app.state, "oauth_flows"):
        request.app.state.oauth_flows = {}
    return request.app.state.oauth_flows


def _state_store(request: Request) -> dict[str, str]:
    if not hasattr(request.app.state, "oauth_states"):
        request.app.state.oauth_states = {}
    return request.app.state.oauth_states


def _callback_server_store(request: Request) -> dict[str, Any]:
    if not hasattr(request.app.state, "oauth_callback_servers"):
        request.app.state.oauth_callback_servers = {}
    return request.app.state.oauth_callback_servers


def _normalize_provider(raw: str) -> str:
    provider = raw.strip().lower()
    if provider == "antigravity":
        return "google-antigravity"
    return provider


def _provider_methods(provider: str) -> set[str]:
    if provider == "openai":
        return {BROWSER_METHOD, DEVICE_CODE_METHOD, TOKEN_METHOD}
    if provider == "anthropic":
        return {TOKEN_METHOD}
    if provider == "google-antigravity":
        return {BROWSER_METHOD}
    return set()


def _new_flow_id() -> str:
    return secrets.token_hex(16)


def _gc_flows(request: Request) -> None:
    now = oauth_now()
    flows = _flow_store(request)
    states = _state_store(request)
    for flow_id, flow in list(flows.items()):
        expires_at = _parse_iso_datetime(str(flow.get("expires_at") or ""))
        updated_at = _parse_iso_datetime(str(flow.get("updated_at") or flow.get("created_at") or ""))
        if flow.get("status") == FLOW_PENDING and expires_at and now > expires_at:
            flow["status"] = FLOW_EXPIRED
            flow["error"] = "flow expired"
            flow["updated_at"] = now.isoformat()
            state = str(flow.get("oauth_state") or "")
            if state:
                states.pop(state, None)
        if flow.get("status") != FLOW_PENDING and updated_at and now - updated_at > TERMINAL_FLOW_GC:
            state = str(flow.get("oauth_state") or "")
            if state:
                states.pop(state, None)
            flows.pop(flow_id, None)


def _parse_iso_datetime(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _store_flow(request: Request, flow: dict[str, Any]) -> None:
    _gc_flows(request)
    _flow_store(request)[flow["flow_id"]] = flow
    oauth_state = str(flow.get("oauth_state") or "")
    if oauth_state:
        _state_store(request)[oauth_state] = flow["flow_id"]


def _get_flow(request: Request, flow_id: str) -> dict[str, Any] | None:
    _gc_flows(request)
    flow = _flow_store(request).get(flow_id)
    if not flow:
        return None
    return dict(flow)


def _get_flow_by_state(request: Request, state: str) -> dict[str, Any] | None:
    _gc_flows(request)
    flow_id = _state_store(request).get(state)
    if not flow_id:
        return None
    flow = _flow_store(request).get(flow_id)
    if not flow:
        _state_store(request).pop(state, None)
        return None
    return dict(flow)


def _replace_flow(request: Request, flow: dict[str, Any]) -> None:
    _flow_store(request)[flow["flow_id"]] = flow


def _shutdown_callback_server(request: Request, flow_id: str) -> None:
    server = _callback_server_store(request).pop(flow_id, None)
    if server is None:
        return

    def _close_server() -> None:
        try:
            server.shutdown()
        except Exception:
            pass
        try:
            server.server_close()
        except Exception:
            pass

    threading.Thread(target=_close_server, daemon=True).start()


def _set_flow_success(request: Request, flow_id: str) -> dict[str, Any] | None:
    flow = _get_flow(request, flow_id)
    if not flow:
        return None
    flow["status"] = FLOW_SUCCESS
    flow["error"] = ""
    flow["updated_at"] = oauth_now().isoformat()
    oauth_state = str(flow.get("oauth_state") or "")
    if oauth_state:
        _state_store(request).pop(oauth_state, None)
    _replace_flow(request, flow)
    _shutdown_callback_server(request, flow_id)
    return flow


def _set_flow_error(request: Request, flow_id: str, error: str) -> dict[str, Any] | None:
    flow = _get_flow(request, flow_id)
    if not flow:
        return None
    flow["status"] = FLOW_ERROR
    flow["error"] = error
    flow["updated_at"] = oauth_now().isoformat()
    oauth_state = str(flow.get("oauth_state") or "")
    if oauth_state:
        _state_store(request).pop(oauth_state, None)
    _replace_flow(request, flow)
    _shutdown_callback_server(request, flow_id)
    return flow


def _flow_response(flow: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "flow_id": flow["flow_id"],
        "provider": flow["provider"],
        "method": flow["method"],
        "status": flow["status"],
        "expires_at": flow.get("expires_at", ""),
        "error": flow.get("error", ""),
    }
    if flow.get("method") == DEVICE_CODE_METHOD:
        payload["user_code"] = flow.get("user_code", "")
        payload["verify_url"] = flow.get("verify_url", "")
        payload["interval"] = flow.get("interval", 0)
    return payload


def _persist_oauth_login(context, provider: str, auth_method: str, token) -> None:
    if provider != "openai":
        raise ValueError(f"provider {provider!r} does not support native oauth in this launcher")
    oauth_save_openai_token(token)
    oauth_mark_provider_oauth(context.config_path, provider)
    sync_provider_auth_state(
        context.config_path,
        context.models_store_path,
        provider,
        auth_method,
    )


def _render_callback_page(flow_id: str, status: str, title: str, error: str = "") -> HTMLResponse:
    payload = {
        "type": "miniclaw-oauth-result",
        "flowId": flow_id,
        "status": status,
    }
    if error:
        payload["error"] = error
    payload_json = json.dumps(payload, ensure_ascii=True)
    message = f"{title}: {error}" if error else title
    body = (
        "<!doctype html><html><head><meta charset=\"utf-8\"><title>Miniclaw OAuth</title></head>"
        "<body><script>(function(){var payload="
        + payload_json
        + ";var hasOpener=false;try{if(window.opener&&!window.opener.closed){window.opener.postMessage(payload,window.location.origin);hasOpener=true}}catch(e){}"
        + "var target='/credentials?oauth_flow_id='+encodeURIComponent(payload.flowId||'')+'&oauth_status='+encodeURIComponent(payload.status||'');"
        + "setTimeout(function(){if(hasOpener){window.close();return}window.location.replace(target)},800)})();</script>"
        + '<div style="font-family:Inter,system-ui,sans-serif;padding:24px">'
        + f"<h2>{escape(title)}</h2><p>{escape(message)}</p><p>You can close this window.</p></div></body></html>"
    )
    return HTMLResponse(body, status_code=200 if status == FLOW_SUCCESS else 400)


@router.get("/api/oauth/providers")
async def oauth_providers(request: Request):
    context = request.app.state.launcher_context
    return {"providers": list_provider_statuses(context.config_path)}


@router.post("/api/oauth/login")
async def oauth_login(request: Request):
    context = request.app.state.launcher_context
    payload = await request.json()
    provider = _normalize_provider(str(payload.get("provider") or ""))
    method = str(payload.get("method") or "").strip().lower()
    token = str(payload.get("token") or "").strip()

    if not provider:
        return JSONResponse({"error": "provider is required"}, status_code=400)
    if method not in _provider_methods(provider):
        return JSONResponse(
            {"error": f"unsupported login method {method!r} for provider {provider!r}"},
            status_code=400,
        )

    if method == TOKEN_METHOD:
        if not token:
            return JSONResponse({"error": "token is required"}, status_code=400)
        try:
            response = save_provider_token(context.config_path, provider, token)
        except ValueError as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
        sync_provider_auth_state(
            context.config_path,
            context.models_store_path,
            provider,
            TOKEN_METHOD,
        )
        return response

    if provider == "openai" and method == DEVICE_CODE_METHOD:
        try:
            device_flow = oauth_request_device_code()
        except Exception as exc:
            return JSONResponse({"error": str(exc)}, status_code=500)

        now = oauth_now()
        flow = {
            "flow_id": _new_flow_id(),
            "provider": provider,
            "method": method,
            "status": FLOW_PENDING,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "expires_at": (now + DEVICE_FLOW_TTL).isoformat(),
            "device_auth_id": device_flow["device_auth_id"],
            "user_code": device_flow["user_code"],
            "verify_url": device_flow["verify_url"],
            "interval": int(device_flow.get("interval") or 5),
        }
        _store_flow(request, flow)
        return {
            "status": "ok",
            "provider": provider,
            "method": method,
            "flow_id": flow["flow_id"],
            "user_code": flow["user_code"],
            "verify_url": flow["verify_url"],
            "interval": flow["interval"],
            "expires_at": flow["expires_at"],
        }

    if provider == "openai" and method == BROWSER_METHOD:
        verifier, challenge = oauth_generate_pkce()
        state = oauth_generate_state()
        redirect_uri = str(oauth_openai_provider_config().redirect_uri)
        auth_url = oauth_build_authorize_url(
            redirect_uri=redirect_uri,
            code_challenge=challenge,
            state=state,
        )
        now = oauth_now()
        flow = {
            "flow_id": _new_flow_id(),
            "provider": provider,
            "method": method,
            "status": FLOW_PENDING,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "expires_at": (now + BROWSER_FLOW_TTL).isoformat(),
            "code_verifier": verifier,
            "oauth_state": state,
            "redirect_uri": redirect_uri,
        }

        def _handle_browser_code(code: str) -> None:
            try:
                token = oauth_exchange_code_for_tokens(
                    code=code,
                    verifier=verifier,
                    redirect_uri=redirect_uri,
                )
                _persist_oauth_login(context, "openai", "oauth", token)
            except Exception as exc:
                _set_flow_error(request, flow["flow_id"], str(exc))
                return
            _set_flow_success(request, flow["flow_id"])

        server, server_error = oauth_start_openai_callback_server(
            state,
            on_code=_handle_browser_code,
        )
        if not server:
            return JSONResponse(
                {"error": server_error or "failed to start local OAuth callback server"},
                status_code=500,
            )

        _store_flow(request, flow)
        _callback_server_store(request)[flow["flow_id"]] = server
        return {
            "status": "ok",
            "provider": provider,
            "method": method,
            "flow_id": flow["flow_id"],
            "auth_url": auth_url,
            "expires_at": flow["expires_at"],
        }

    if provider == "google-antigravity" and method == BROWSER_METHOD:
        return JSONResponse(
            {"error": "Google Antigravity browser OAuth is not wired into miniclaw runtime yet."},
            status_code=400,
        )

    return JSONResponse({"error": "unsupported login method"}, status_code=400)


@router.get("/api/oauth/flows/{flow_id}")
async def get_oauth_flow(flow_id: str, request: Request):
    flow = _get_flow(request, flow_id)
    if not flow:
        return JSONResponse({"error": "flow not found"}, status_code=404)
    return _flow_response(flow)


@router.post("/api/oauth/flows/{flow_id}/poll")
async def poll_oauth_flow(flow_id: str, request: Request):
    context = request.app.state.launcher_context
    flow = _get_flow(request, flow_id)
    if not flow:
        return JSONResponse({"error": "flow not found"}, status_code=404)
    if flow["method"] != DEVICE_CODE_METHOD:
        return JSONResponse({"error": "flow does not support polling"}, status_code=400)
    if flow["status"] != FLOW_PENDING:
        return _flow_response(flow)

    try:
        token = oauth_poll_device_code_once(
            str(flow.get("device_auth_id") or ""),
            str(flow.get("user_code") or ""),
        )
    except Exception as exc:
        updated = _set_flow_error(request, flow_id, str(exc))
        return _flow_response(updated or flow)

    if token is None:
        updated = _get_flow(request, flow_id) or flow
        return _flow_response(updated)

    try:
        _persist_oauth_login(context, "openai", "oauth", token)
    except Exception as exc:
        updated = _set_flow_error(request, flow_id, str(exc))
        return _flow_response(updated or flow)

    updated = _set_flow_success(request, flow_id) or flow
    return _flow_response(updated)


@router.post("/api/oauth/logout")
async def oauth_logout(request: Request):
    context = request.app.state.launcher_context
    payload = await request.json()
    provider = _normalize_provider(str(payload.get("provider") or ""))
    if not provider:
        return JSONResponse({"error": "provider is required"}, status_code=400)
    try:
        result = clear_provider_token(context.config_path, provider)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    sync_provider_auth_state(
        context.config_path,
        context.models_store_path,
        provider,
        "",
    )
    return result


@router.get("/oauth/callback", name="oauth_callback")
async def oauth_callback(request: Request):
    state = str(request.query_params.get("state") or "").strip()
    if not state:
        return _render_callback_page("", FLOW_ERROR, "Missing state", "missing_state")

    flow = _get_flow_by_state(request, state)
    if not flow:
        return _render_callback_page("", FLOW_ERROR, "OAuth flow not found", "flow_not_found")
    if flow["status"] != FLOW_PENDING:
        return _render_callback_page(
            flow["flow_id"],
            flow["status"],
            "Flow already completed",
            str(flow.get("error") or ""),
        )

    error = str(request.query_params.get("error") or "").strip()
    if error:
        description = str(request.query_params.get("error_description") or "").strip()
        message = f"{error}: {description}" if description else error
        _set_flow_error(request, flow["flow_id"], message)
        return _render_callback_page(flow["flow_id"], FLOW_ERROR, "Authorization failed", message)

    code = str(request.query_params.get("code") or "").strip()
    if not code:
        _set_flow_error(request, flow["flow_id"], "missing authorization code")
        return _render_callback_page(
            flow["flow_id"],
            FLOW_ERROR,
            "Missing authorization code",
            "missing_code",
        )

    context = request.app.state.launcher_context
    try:
        token = oauth_exchange_code_for_tokens(
            code=code,
            verifier=str(flow.get("code_verifier") or ""),
            redirect_uri=str(flow.get("redirect_uri") or ""),
        )
        _persist_oauth_login(context, "openai", "oauth", token)
    except Exception as exc:
        _set_flow_error(request, flow["flow_id"], str(exc))
        return _render_callback_page(flow["flow_id"], FLOW_ERROR, "Token exchange failed", str(exc))

    _set_flow_success(request, flow["flow_id"])
    return _render_callback_page(flow["flow_id"], FLOW_SUCCESS, "Authentication successful")
