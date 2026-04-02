from __future__ import annotations

import hashlib
import hmac
from urllib.parse import urlencode

from fastapi import Request
from fastapi.responses import JSONResponse, RedirectResponse

COOKIE_NAME = "miniclaw_launcher_auth"
_COOKIE_LABEL = b"miniclaw-launcher-v1"


def session_cookie_value(signing_key: bytes, dashboard_token: str) -> str:
    mac = hmac.new(signing_key, digestmod=hashlib.sha256)
    mac.update(_COOKIE_LABEL)
    mac.update(b"\x00")
    mac.update(dashboard_token.encode("utf-8"))
    return mac.hexdigest()


def secure_cookie(request: Request) -> bool:
    if request.url.scheme == "https":
        return True
    return request.headers.get("x-forwarded-proto", "").lower() == "https"


def canonical_path(path: str) -> str:
    if not path:
        return "/"
    parts = [part for part in path.split("/") if part not in {"", "."}]
    cleaned = []
    for part in parts:
        if part == "..":
            if cleaned:
                cleaned.pop()
            continue
        cleaned.append(part)
    return "/" + "/".join(cleaned)


def is_public_path(method: str, path: str) -> bool:
    if method in {"GET", "HEAD"}:
        if path == "/launcher-login":
            return True
        if path == "/oauth/callback":
            return True
        if path.startswith("/assets/"):
            return True
        if path in {"/favicon.ico", "/favicon.svg", "/site.webmanifest", "/robots.txt"}:
            return True

    if path == "/api/auth/login" and method == "POST":
        return True
    if path == "/api/auth/logout" and method == "POST":
        return True
    if path == "/api/auth/status" and method == "GET":
        return True
    return False


def valid_auth(request: Request, expected_cookie: str, dashboard_token: str) -> bool:
    cookie = request.cookies.get(COOKIE_NAME, "")
    if cookie and hmac.compare_digest(cookie, expected_cookie):
        return True

    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:].strip()
        if token and hmac.compare_digest(token, dashboard_token):
            return True
    return False


def reject_auth(path: str):
    if path.startswith("/api/"):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    return RedirectResponse("/launcher-login", status_code=302)


def query_token_redirect(request: Request, path: str, expected_cookie: str, dashboard_token: str):
    if request.method != "GET" or path.startswith("/api/"):
        return None
    token = request.query_params.get("token", "").strip()
    if not token:
        return None
    if not hmac.compare_digest(token, dashboard_token):
        return reject_auth(path)

    params = dict(request.query_params)
    params.pop("token", None)
    target = path
    if params:
        target += "?" + urlencode(params)
    if path == "/launcher-login":
        target = "/"

    response = RedirectResponse(target, status_code=303)
    response.set_cookie(
        COOKIE_NAME,
        expected_cookie,
        httponly=True,
        samesite="lax",
        secure=secure_cookie(request),
        path="/",
    )
    return response
