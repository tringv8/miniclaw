from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.utils.config_store import (
    command_pattern_result,
    load_raw_config,
    merge_patch,
    normalize_payload,
    save_raw_config,
)

router = APIRouter()


def _validation_error(exc: Exception):
    return JSONResponse(
        {
            "status": "validation_error",
            "errors": [str(exc)],
        },
        status_code=400,
    )


@router.get("/api/config")
async def get_config(request: Request):
    context = request.app.state.launcher_context
    return normalize_payload(load_raw_config(context.config_path))


@router.put("/api/config")
async def put_config(request: Request):
    context = request.app.state.launcher_context
    payload = await request.json()
    try:
        save_raw_config(context.config_path, payload)
    except Exception as exc:
        return _validation_error(exc)
    return {"status": "ok"}


@router.patch("/api/config")
async def patch_config(request: Request):
    context = request.app.state.launcher_context
    patch = await request.json()
    try:
        base = load_raw_config(context.config_path)
        save_raw_config(context.config_path, merge_patch(base, patch))
    except Exception as exc:
        return _validation_error(exc)
    return {"status": "ok"}


@router.post("/api/config/test-command-patterns")
async def test_command_patterns(request: Request):
    payload = await request.json()
    return command_pattern_result(
        command=str(payload.get("command", "")),
        allow_patterns=[str(item) for item in payload.get("allow_patterns", [])],
        deny_patterns=[str(item) for item in payload.get("deny_patterns", [])],
    )
