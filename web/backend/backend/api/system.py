from __future__ import annotations

import platform

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.launcherconfig.config import LauncherConfig, load, save

router = APIRouter()


def _launcher_payload(cfg: LauncherConfig) -> dict[str, object]:
    return {
        "port": cfg.port,
        "public": cfg.public,
        "allowed_cidrs": cfg.allowed_cidrs,
    }


@router.get("/api/system/autostart")
async def get_autostart():
    return {
        "enabled": False,
        "supported": False,
        "platform": platform.system().lower(),
        "message": "Autostart is not implemented in the Python launcher.",
    }


@router.put("/api/system/autostart")
async def set_autostart():
    return JSONResponse(
        {"error": "autostart is not implemented in the Python launcher"},
        status_code=400,
    )


@router.get("/api/system/launcher-config")
async def get_launcher_config(request: Request):
    context = request.app.state.launcher_context
    return _launcher_payload(load(context.launcher_config_path, fallback=LauncherConfig()))


@router.put("/api/system/launcher-config")
async def set_launcher_config(request: Request):
    context = request.app.state.launcher_context
    payload = await request.json()
    try:
        default_cfg = LauncherConfig()
        cfg = LauncherConfig(
            port=int(payload.get("port", default_cfg.port)),
            public=bool(payload.get("public", False)),
            allowed_cidrs=[str(item) for item in (payload.get("allowed_cidrs") or [])],
        )
        saved = save(context.launcher_config_path, cfg)
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    return _launcher_payload(saved)
