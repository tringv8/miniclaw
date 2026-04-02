from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse

from backend.launcherconfig.config import LauncherConfig, load
from backend.middleware.access_control import client_allowed
from backend.middleware.launcher_dashboard_auth import (
    canonical_path,
    is_public_path,
    query_token_redirect,
    reject_auth,
    valid_auth,
)


async def referrer_policy_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    return response


async def access_control_middleware(request: Request, call_next):
    context = request.app.state.launcher_context
    fallback = LauncherConfig()
    launcher_cfg = load(context.launcher_config_path, fallback=fallback)
    if not client_allowed(request.client.host if request.client else None, launcher_cfg.allowed_cidrs):
        return JSONResponse({"error": "forbidden"}, status_code=403)
    return await call_next(request)


async def dashboard_auth_middleware(request: Request, call_next):
    context = request.app.state.launcher_context
    path = canonical_path(request.url.path)

    redirected = query_token_redirect(
        request,
        path,
        expected_cookie=context.dashboard_session_cookie,
        dashboard_token=context.dashboard_token,
    )
    if redirected is not None:
        return redirected

    if is_public_path(request.method, path):
        return await call_next(request)

    if valid_auth(request, context.dashboard_session_cookie, context.dashboard_token):
        return await call_next(request)

    return reject_auth(path)
