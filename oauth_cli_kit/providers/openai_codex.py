from __future__ import annotations

from oauth_cli_kit.models import OAuthProviderConfig


OPENAI_CODEX_PROVIDER = OAuthProviderConfig(
    client_id="app_EMoamEEZ73f0CkXaXp7hrann",
    authorize_url="https://auth.openai.com/oauth/authorize",
    token_url="https://auth.openai.com/oauth/token",
    redirect_uri="http://localhost:1455/auth/callback",
    scope="openid profile email offline_access",
    jwt_claim_path="https://api.openai.com/auth",
    account_id_claim="chatgpt_account_id",
    default_originator="miniclaw",
    token_filename="codex.json",
    device_code_url="https://auth.openai.com/api/accounts/deviceauth/usercode",
    device_verify_url="https://auth.openai.com/codex/device",
)
