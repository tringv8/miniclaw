from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.utils.config_store import load_raw_config, save_raw_config
from backend.utils.model_store import (
    load_model_store,
    normalize_profile,
    replace_profile_secret,
    response_models,
    save_model_store,
    sync_profile_to_miniclaw_config,
)
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


def _load_store(context) -> dict[str, Any]:
    return load_model_store(context.models_store_path, context.config_path)


def _store_response(context, store: dict[str, Any]) -> dict[str, Any]:
    return response_models(store, oauth_status=_oauth_status_map(context.config_path))


def _clear_miniclaw_default_model(config_path) -> None:
    raw = load_raw_config(config_path)
    agents = raw.setdefault("agents", {})
    defaults = agents.setdefault("defaults", {})
    defaults["modelName"] = ""
    defaults["model"] = ""
    defaults["provider"] = "auto"
    save_raw_config(config_path, raw)


def _validate_profile(profile: dict[str, Any]) -> str | None:
    if not profile["model_name"]:
        return "model_name is required"
    if not profile["model"]:
        return "model is required"
    return None


@router.get("/api/models")
async def list_models(request: Request):
    context = request.app.state.launcher_context
    return _store_response(context, _load_store(context))


@router.post("/api/models")
async def add_model(request: Request):
    context = request.app.state.launcher_context
    payload = await request.json()
    profile = normalize_profile(payload)
    if error := _validate_profile(profile):
        return JSONResponse({"error": error}, status_code=400)

    store = _load_store(context)
    if any(item["model_name"] == profile["model_name"] for item in store["models"]):
        return JSONResponse({"error": "model_name already exists"}, status_code=400)

    store["models"].append(profile)
    if not store["default_model"]:
        store["default_model"] = profile["model_name"]
        sync_profile_to_miniclaw_config(context.config_path, profile)
    save_model_store(context.models_store_path, store)
    return {
        "status": "ok",
        "index": len(store["models"]) - 1,
        "default_model": store["default_model"],
    }


@router.post("/api/models/default")
async def set_default_model(request: Request):
    context = request.app.state.launcher_context
    payload = await request.json()
    model_name = str(payload.get("model_name") or "").strip()
    store = _load_store(context)
    profile = next((item for item in store["models"] if item["model_name"] == model_name), None)
    if not profile:
        return JSONResponse({"error": "model not found"}, status_code=404)

    store["default_model"] = model_name
    save_model_store(context.models_store_path, store)
    sync_profile_to_miniclaw_config(context.config_path, profile)
    return {"status": "ok", "default_model": model_name}


@router.put("/api/models/{index}")
async def update_model(index: int, request: Request):
    context = request.app.state.launcher_context
    store = _load_store(context)
    if index < 0 or index >= len(store["models"]):
        return JSONResponse({"error": "model not found"}, status_code=404)

    payload = await request.json()
    existing = store["models"][index]
    updated = replace_profile_secret(existing, payload)
    if error := _validate_profile(updated):
        return JSONResponse({"error": error}, status_code=400)

    for i, item in enumerate(store["models"]):
        if i != index and item["model_name"] == updated["model_name"]:
            return JSONResponse({"error": "model_name already exists"}, status_code=400)

    store["models"][index] = updated
    if existing["model_name"] == store["default_model"] and updated["model_name"] != existing["model_name"]:
        store["default_model"] = updated["model_name"]
    save_model_store(context.models_store_path, store)

    if updated["model_name"] == store["default_model"]:
        sync_profile_to_miniclaw_config(context.config_path, updated)

    return {"status": "ok", "index": index, "default_model": store["default_model"]}


@router.delete("/api/models/{index}")
async def delete_model(index: int, request: Request):
    context = request.app.state.launcher_context
    store = _load_store(context)
    if index < 0 or index >= len(store["models"]):
        return JSONResponse({"error": "model not found"}, status_code=404)

    removed = store["models"].pop(index)
    if removed["model_name"] == store["default_model"]:
        store["default_model"] = store["models"][0]["model_name"] if store["models"] else ""

    save_model_store(context.models_store_path, store)
    if store["default_model"]:
        profile = next((item for item in store["models"] if item["model_name"] == store["default_model"]), None)
        if profile:
            sync_profile_to_miniclaw_config(context.config_path, profile)
    else:
        _clear_miniclaw_default_model(context.config_path)

    return {"status": "ok", "default_model": store["default_model"]}
