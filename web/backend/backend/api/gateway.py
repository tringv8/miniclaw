from __future__ import annotations

import hashlib
import json
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.utils.config_store import load_raw_config, normalize_payload
from backend.utils.model_store import load_model_store, response_models
from backend.utils.oauth_store import list_provider_statuses

router = APIRouter()


def _oauth_status_map(config_path) -> dict[str, bool]:
    result: dict[str, bool] = {}
    for item in list_provider_statuses(config_path):
        provider = str(item.get("provider", "")).replace("-", "_")
        logged_in = bool(item.get("logged_in"))
        result[provider] = logged_in
        if provider == "openai" and str(item.get("auth_method") or "") == "oauth":
            result["openai_codex"] = logged_in
    return result


def _config_default_model(raw: dict[str, Any]) -> str:
    defaults = ((raw.get("agents") or {}).get("defaults") or {})
    return str(defaults.get("modelName") or defaults.get("model") or "").strip()


def _config_signature(raw: dict[str, Any]) -> str:
    normalized = normalize_payload(raw)
    payload = json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _gateway_start_ready(context) -> tuple[bool, str]:
    status = context.runtime.status().status
    if status in {"running", "starting", "restarting", "stopping"}:
        return False, "gateway is already active"

    store = load_model_store(context.models_store_path, context.config_path)
    oauth_status = _oauth_status_map(context.config_path)
    models = response_models(store, oauth_status=oauth_status)["models"]
    default_model = str(store.get("default_model") or "")
    if not default_model and models:
        default_model = str(models[0].get("model_name") or "")

    if not default_model:
        raw = load_raw_config(context.config_path)
        default_model = _config_default_model(raw)

    if not default_model:
        return False, "no default model is configured"

    for item in models:
        if str(item.get("model_name")) == default_model and not bool(item.get("configured")):
            return False, "default model is not configured"

    return True, ""


def _status_payload(context) -> dict[str, Any]:
    raw = load_raw_config(context.config_path)
    runtime_state = context.runtime.status()
    current_signature = _config_signature(raw)
    start_allowed, start_reason = _gateway_start_ready(context)

    payload: dict[str, Any] = {
        "gateway_status": runtime_state.status,
        "gateway_start_allowed": start_allowed,
        "gateway_restart_required": (
            runtime_state.status == "running"
            and bool(runtime_state.boot_signature)
            and runtime_state.boot_signature != current_signature
        ),
        "config_default_model": _config_default_model(raw),
    }
    if start_reason:
        payload["gateway_start_reason"] = start_reason
    if runtime_state.pid is not None:
        payload["pid"] = runtime_state.pid
    if runtime_state.boot_default_model:
        payload["boot_default_model"] = runtime_state.boot_default_model
    if runtime_state.last_error:
        payload["last_error"] = runtime_state.last_error
    return payload


@router.get("/api/gateway/status")
async def gateway_status(request: Request):
    context = request.app.state.launcher_context
    return _status_payload(context)


@router.get("/api/gateway/logs")
async def gateway_logs(request: Request, log_offset: int = 0, log_run_id: int | None = None):
    context = request.app.state.launcher_context
    return context.runtime.logs.snapshot(offset=log_offset, run_id=log_run_id)


@router.post("/api/gateway/logs/clear")
async def clear_gateway_logs(request: Request):
    context = request.app.state.launcher_context
    context.runtime.logs.reset()
    return {
        "status": "cleared",
        "log_total": 0,
        "log_run_id": context.runtime.logs.run_id,
    }


@router.post("/api/gateway/start")
async def start_gateway(request: Request):
    context = request.app.state.launcher_context
    ready, reason = _gateway_start_ready(context)
    if not ready:
        return JSONResponse({"error": reason}, status_code=400)

    raw = load_raw_config(context.config_path)
    try:
        data = context.runtime.start(
            boot_default_model=_config_default_model(raw),
            boot_signature=_config_signature(raw),
        )
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)
    return data


@router.post("/api/gateway/stop")
async def stop_gateway(request: Request):
    context = request.app.state.launcher_context
    try:
        return context.runtime.stop()
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@router.post("/api/gateway/restart")
async def restart_gateway(request: Request):
    context = request.app.state.launcher_context
    raw = load_raw_config(context.config_path)
    try:
        return context.runtime.restart(
            boot_default_model=_config_default_model(raw),
            boot_signature=_config_signature(raw),
        )
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)
