from __future__ import annotations

from fastapi import APIRouter, File, Request, UploadFile
from fastapi.responses import JSONResponse

from miniclaw.config.loader import load_config

from backend.utils.skills_store import delete_skill, get_skill, import_skill, list_skills

router = APIRouter()


def _workspace_path(config_path):
    return load_config(config_path).workspace_path


@router.get("/api/skills")
async def skills(request: Request):
    context = request.app.state.launcher_context
    return {"skills": list_skills(_workspace_path(context.config_path))}


@router.get("/api/skills/{name}")
async def skill_detail(name: str, request: Request):
    context = request.app.state.launcher_context
    detail = get_skill(_workspace_path(context.config_path), name)
    if not detail:
        return JSONResponse({"error": "skill not found"}, status_code=404)
    return detail


@router.post("/api/skills/import")
async def import_skill_route(request: Request, file: UploadFile = File(...)):
    context = request.app.state.launcher_context
    if not file.filename:
        return JSONResponse({"error": "file name is required"}, status_code=400)
    try:
        item = import_skill(
            _workspace_path(context.config_path),
            file.filename,
            await file.read(),
        )
    except FileExistsError as exc:
        return JSONResponse({"error": str(exc)}, status_code=409)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    return {"status": "ok", **item}


@router.delete("/api/skills/{name}")
async def delete_skill_route(name: str, request: Request):
    context = request.app.state.launcher_context
    if not delete_skill(_workspace_path(context.config_path), name):
        return JSONResponse({"error": "skill not found"}, status_code=404)
    return {"status": "ok", "name": name}
