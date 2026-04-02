from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.utils.sessions import delete_session, get_session_detail, list_sessions

router = APIRouter()


@router.get("/api/sessions")
async def sessions(request: Request, offset: int = 0, limit: int = 20):
    context = request.app.state.launcher_context
    return list_sessions(context.config_path, offset=offset, limit=limit)


@router.get("/api/sessions/{session_id:path}")
async def session_detail(session_id: str, request: Request):
    context = request.app.state.launcher_context
    detail = get_session_detail(context.config_path, session_id)
    if not detail:
        return JSONResponse({"error": "session not found"}, status_code=404)
    return detail


@router.delete("/api/sessions/{session_id:path}")
async def remove_session(session_id: str, request: Request):
    context = request.app.state.launcher_context
    if not delete_session(context.config_path, session_id):
        return JSONResponse({"error": "session not found"}, status_code=404)
    return JSONResponse(status_code=204, content=None)
