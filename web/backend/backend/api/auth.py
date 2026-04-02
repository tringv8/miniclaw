from __future__ import annotations

import hmac

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.launcherconfig.config import SESSION_MAX_AGE_SECONDS
from backend.middleware.launcher_dashboard_auth import COOKIE_NAME, secure_cookie

router = APIRouter()


@router.post("/api/auth/login")
async def login(request: Request):
    body = await request.json()
    token = str(body.get("token", "")).strip()
    context = request.app.state.launcher_context
    if not token or not hmac.compare_digest(token, context.dashboard_token):
        return JSONResponse({"error": "invalid token"}, status_code=401)

    response = JSONResponse({"status": "ok"})
    response.set_cookie(
        COOKIE_NAME,
        context.dashboard_session_cookie,
        httponly=True,
        samesite="lax",
        secure=secure_cookie(request),
        path="/",
        max_age=SESSION_MAX_AGE_SECONDS,
    )
    return response


@router.post("/api/auth/logout")
async def logout(request: Request):
    response = JSONResponse({"status": "ok"})
    response.delete_cookie(COOKIE_NAME, path="/")
    return response


@router.get("/api/auth/status")
async def status(request: Request):
    context = request.app.state.launcher_context
    authenticated = request.cookies.get(COOKIE_NAME) == context.dashboard_session_cookie
    if authenticated:
        return {"authenticated": True}
    return {
        "authenticated": False,
        "token_help": {
            "env_var_name": "MINICLAW_LAUNCHER_TOKEN",
            "tray_copy_menu": False,
            "console_stdout": True,
        },
    }
