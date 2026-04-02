from __future__ import annotations

import time
from datetime import datetime, timezone
from collections.abc import Callable
from typing import Any

import httpx

from oauth_cli_kit import build_authorize_url, exchange_code_for_token, refresh_token
from oauth_cli_kit.models import OAuthToken
from oauth_cli_kit.pkce import _create_state, _generate_pkce
from oauth_cli_kit.providers import OPENAI_CODEX_PROVIDER
from oauth_cli_kit.server import _start_local_server
from oauth_cli_kit.storage import FileTokenStorage


def openai_provider_config():
    return OPENAI_CODEX_PROVIDER


def generate_pkce() -> tuple[str, str]:
    return _generate_pkce()


def generate_state() -> str:
    return _create_state()


def build_openai_authorize_url(
    *,
    redirect_uri: str,
    code_challenge: str,
    state: str,
) -> str:
    return build_authorize_url(
        OPENAI_CODEX_PROVIDER,
        redirect_uri=redirect_uri,
        code_challenge=code_challenge,
        state=state,
    )


def start_openai_callback_server(
    state: str,
    on_code: Callable[[str], None] | None = None,
):
    return _start_local_server(state, on_code=on_code)


def request_openai_device_code() -> dict[str, Any]:
    provider = OPENAI_CODEX_PROVIDER
    with httpx.Client(timeout=30.0) as client:
        response = client.post(
            provider.device_code_url,
            json={"client_id": provider.client_id},
            headers={"Content-Type": "application/json"},
        )
    if response.status_code != 200:
        raise RuntimeError(
            f"Device code request failed: {response.status_code} {response.text}"
        )

    payload = response.json()
    device_auth_id = str(
        payload.get("device_auth_id")
        or payload.get("deviceAuthId")
        or payload.get("device_code")
        or ""
    ).strip()
    user_code = str(payload.get("user_code") or payload.get("userCode") or "").strip()
    interval = int(payload.get("interval") or 5)
    if not device_auth_id or not user_code:
        raise RuntimeError("Device code response missing required fields")

    verify_url = str(
        payload.get("verification_uri")
        or payload.get("verification_url")
        or payload.get("verify_url")
        or provider.device_verify_url
    ).strip()
    return {
        "device_auth_id": device_auth_id,
        "user_code": user_code,
        "verify_url": verify_url or provider.device_verify_url,
        "interval": interval,
    }


def poll_openai_device_code_once(device_auth_id: str, user_code: str) -> OAuthToken | None:
    provider = OPENAI_CODEX_PROVIDER
    with httpx.Client(timeout=30.0) as client:
        response = client.post(
            "https://auth.openai.com/api/accounts/deviceauth/token",
            json={
                "client_id": provider.client_id,
                "device_auth_id": device_auth_id,
                "user_code": user_code,
            },
            headers={"Content-Type": "application/json"},
        )

    if response.status_code in {202, 204}:
        return None

    if response.status_code != 200:
        body = response.text.lower()
        if "pending" in body or "authorization_pending" in body:
            return None
        raise RuntimeError(
            f"Device code poll failed: {response.status_code} {response.text}"
        )

    payload = response.json()
    access = payload.get("access_token")
    refresh = payload.get("refresh_token")
    expires_in = payload.get("expires_in")
    if not access or not refresh or not isinstance(expires_in, int):
        raise RuntimeError("Device code token response missing required fields")
    account_id = payload.get("account_id")
    return OAuthToken(
        access=str(access),
        refresh=str(refresh),
        expires=int(time.time() * 1000 + expires_in * 1000),
        account_id=str(account_id) if account_id else None,
    )


def exchange_openai_code_for_token(
    *,
    code: str,
    verifier: str,
    redirect_uri: str,
) -> OAuthToken:
    return exchange_code_for_token(
        code,
        verifier,
        OPENAI_CODEX_PROVIDER,
        redirect_uri=redirect_uri,
    )


def openai_token_storage() -> FileTokenStorage:
    return FileTokenStorage(token_filename=OPENAI_CODEX_PROVIDER.token_filename)


def save_openai_oauth_token(token: OAuthToken) -> OAuthToken:
    storage = openai_token_storage()
    storage.save(token)
    return token


def delete_openai_oauth_token() -> None:
    openai_token_storage().delete()


def load_openai_oauth_status(*, min_ttl_seconds: int = 60) -> dict[str, Any]:
    storage = openai_token_storage()
    token = storage.load()
    if not token:
        return {"logged_in": False, "status": "not_logged_in"}

    now_ms = int(time.time() * 1000)
    if token.expires - now_ms <= min_ttl_seconds * 1000 and token.refresh:
        try:
            token = refresh_token(token.refresh, OPENAI_CODEX_PROVIDER)
            storage.save(token)
        except Exception:
            token = storage.load() or token

    now_ms = int(time.time() * 1000)
    expires_at = datetime.fromtimestamp(token.expires / 1000, tz=timezone.utc).isoformat()
    expired = token.expires <= now_ms
    return {
        "logged_in": not expired,
        "status": "expired" if expired else "connected",
        "account_id": token.account_id or "",
        "expires_at": expires_at,
    }


def token_debug_payload() -> dict[str, Any]:
    token = openai_token_storage().load()
    if not token:
        return {}
    return {
        "access": token.access[:8],
        "refresh": token.refresh[:8],
        "expires": token.expires,
        "account_id": token.account_id,
    }
