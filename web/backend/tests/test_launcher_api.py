from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[3]
LAUNCHER_ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(LAUNCHER_ROOT) not in sys.path:
    sys.path.insert(0, str(LAUNCHER_ROOT))

from backend.main import create_app
from backend.api import oauth as oauth_api
from oauth_cli_kit.models import OAuthToken


class DummyOAuthServer:
    def shutdown(self) -> None:
        return

    def server_close(self) -> None:
        return


def _base_config(workspace: Path) -> dict:
    return {
        "agents": {
            "defaults": {
                "workspace": str(workspace),
                "restrictToWorkspace": False,
                "modelName": "test-default",
                "model": "openai/test-default",
                "provider": "openai",
                "maxTokens": 8192,
                "contextWindowTokens": 131072,
                "temperature": 0.7,
                "maxToolIterations": 20,
                "summarizeMessageThreshold": 20,
                "summarizeTokenPercent": 75,
                "splitOnMarker": False,
                "toolFeedback": {"enabled": False, "max_args_length": 300},
                "reasoningEffort": None,
                "timezone": "UTC",
            }
        },
        "channels": {
            "sendProgress": True,
            "sendToolHints": False,
            "sendMaxRetries": 3,
            "telegram": {
                "enabled": True,
                "token": "telegram-token",
                "allowFrom": ["*"],
                "streaming": True,
            },
        },
        "providers": {
            "openai": {"apiKey": "", "apiBase": None, "extraHeaders": None},
            "gemini": {"apiKey": "", "apiBase": None, "extraHeaders": None},
            "groq": {"apiKey": "", "apiBase": None, "extraHeaders": None},
        },
        "gateway": {
            "host": "0.0.0.0",
            "port": 18790,
            "heartbeat": {
                "enabled": True,
                "intervalS": 1800,
                "keepRecentMessages": 8,
            },
        },
        "tools": {
            "web": {
                "proxy": None,
                "search": {
                    "provider": "brave",
                    "apiKey": "",
                    "baseUrl": "",
                    "maxResults": 5,
                },
            },
            "exec": {"enable": True, "timeout": 60, "pathAppend": ""},
            "restrictToWorkspace": False,
            "mcpServers": {},
        },
    }


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    home = tmp_path / "home"
    workspace = tmp_path / "workspace"
    config_dir = home / ".miniclaw"
    config_path = config_dir / "config.json"
    workspace.mkdir(parents=True)
    config_dir.mkdir(parents=True)
    config_path.write_text(
        json.dumps(_base_config(workspace), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("MINICLAW_CONFIG", str(config_path))
    monkeypatch.setenv("MINICLAW_LAUNCHER_TOKEN", "launcher-token")

    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


def _login(client: TestClient) -> None:
    response = client.post("/api/auth/login", json={"token": "launcher-token"})
    assert response.status_code == 200


def test_auth_flow(client: TestClient) -> None:
    response = client.get("/api/auth/status")
    assert response.status_code == 200
    assert response.json()["authenticated"] is False

    bad = client.post("/api/auth/login", json={"token": "wrong"})
    assert bad.status_code == 401

    _login(client)

    status = client.get("/api/auth/status")
    assert status.status_code == 200
    assert status.json()["authenticated"] is True

    logout = client.post("/api/auth/logout", json={})
    assert logout.status_code == 200


def test_config_and_tools(client: TestClient) -> None:
    _login(client)

    config = client.get("/api/config")
    assert config.status_code == 200
    assert config.json()["agents"]["defaults"]["workspace"]

    patch = client.patch(
        "/api/config",
        json={"tools": {"exec": {"enable": False, "timeout": 25}}},
    )
    assert patch.status_code == 200

    tools = client.get("/api/tools")
    assert tools.status_code == 200
    exec_tool = next(item for item in tools.json()["tools"] if item["name"] == "exec")
    assert exec_tool["status"] == "disabled"

    toggle = client.put("/api/tools/exec/state", json={"enabled": True})
    assert toggle.status_code == 200


def test_channels_catalog_includes_web_and_telegram(client: TestClient) -> None:
    _login(client)

    response = client.get("/api/channels/catalog")
    assert response.status_code == 200
    payload = response.json()["channels"]
    names = [item["name"] for item in payload]
    assert names == ["web", "telegram"]
    web = next(item for item in payload if item["name"] == "web")
    telegram = next(item for item in payload if item["name"] == "telegram")
    assert web["defaults"]["enabled"] is True
    assert telegram["defaults"]["base_url"] == "https://api.telegram.org"


def test_gateway_status_uses_miniclaw_model_store(client: TestClient) -> None:
    _login(client)

    context = client.app.state.launcher_context
    assert Path(context.models_store_path).name == "miniclaw-launcher-models.json"

    response = client.get("/api/gateway/status")
    assert response.status_code == 200
    assert "gateway_status" in response.json()


def test_models_crud(client: TestClient) -> None:
    _login(client)

    listed = client.get("/api/models")
    assert listed.status_code == 200
    assert listed.json()["models"]

    added = client.post(
        "/api/models",
        json={
            "model_name": "gemini-fast",
            "model": "gemini/gemini-2.5-flash",
            "api_key": "gem-key",
            "auth_method": "token",
        },
    )
    assert added.status_code == 200
    assert added.json()["status"] == "ok"

    make_default = client.post("/api/models/default", json={"model_name": "gemini-fast"})
    assert make_default.status_code == 200
    assert make_default.json()["default_model"] == "gemini-fast"

    updated = client.put(
        "/api/models/1",
        json={
            "model_name": "gemini-fast",
            "model": "gemini/gemini-2.5-flash",
            "api_base": "https://example.invalid/v1",
        },
    )
    assert updated.status_code == 200

    deleted = client.delete("/api/models/1")
    assert deleted.status_code == 200
    assert deleted.json()["status"] == "ok"


def test_skills_and_sessions(client: TestClient, tmp_path: Path) -> None:
    _login(client)

    config = client.get("/api/config").json()
    workspace = Path(config["agents"]["defaults"]["workspace"])

    skill_dir = workspace / "skills" / "hello-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: hello-skill\ndescription: Hello test skill\n---\n\n# Hello\n",
        encoding="utf-8",
    )

    session_dir = workspace / "sessions"
    session_dir.mkdir(parents=True, exist_ok=True)
    session_path = session_dir / "cli_test.jsonl"
    session_path.write_text(
        "\n".join(
            [
                json.dumps({"_type": "metadata", "key": "cli:test", "summary": "CLI test"}),
                json.dumps({"role": "user", "content": "hello"}),
                json.dumps({"role": "assistant", "content": "world"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    skills = client.get("/api/skills")
    assert skills.status_code == 200
    assert any(item["name"] == "hello-skill" for item in skills.json()["skills"])

    skill_detail = client.get("/api/skills/hello-skill")
    assert skill_detail.status_code == 200
    assert "Hello" in skill_detail.json()["content"]

    sessions = client.get("/api/sessions")
    assert sessions.status_code == 200
    assert any(item["id"] == "cli:test" for item in sessions.json())

    detail = client.get("/api/sessions/cli%3Atest")
    assert detail.status_code == 200
    assert len(detail.json()["messages"]) == 2

    deleted = client.delete("/api/sessions/cli%3Atest")
    assert deleted.status_code == 204


def test_oauth_provider_status_and_token_login(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _login(client)

    providers = client.get("/api/oauth/providers")
    assert providers.status_code == 200
    provider_map = {
        item["provider"]: item for item in providers.json()["providers"]
    }
    assert {"openai", "anthropic", "google-antigravity"} <= set(provider_map)

    login = client.post(
        "/api/oauth/login",
        json={"provider": "anthropic", "method": "token", "token": "anthropic-token"},
    )
    assert login.status_code == 200

    providers_after = client.get("/api/oauth/providers").json()["providers"]
    anthropic = next(
        item for item in providers_after if item["provider"] == "anthropic"
    )
    assert anthropic["logged_in"] is True

    monkeypatch.setattr(
        oauth_api,
        "oauth_generate_pkce",
        lambda: ("verifier-1", "challenge-1"),
    )
    monkeypatch.setattr(oauth_api, "oauth_generate_state", lambda: "state-1")
    monkeypatch.setattr(
        oauth_api,
        "oauth_build_authorize_url",
        lambda **kwargs: "https://auth.openai.test/oauth/authorize?state=state-1",
    )
    monkeypatch.setattr(
        oauth_api,
        "oauth_start_openai_callback_server",
        lambda state, on_code=None: (DummyOAuthServer(), None),
    )
    browser = client.post(
        "/api/oauth/login",
        json={"provider": "openai", "method": "browser"},
    )
    assert browser.status_code == 200
    browser_payload = browser.json()
    assert browser_payload["flow_id"]
    assert browser_payload["auth_url"]

    monkeypatch.setattr(
        oauth_api,
        "oauth_request_device_code",
        lambda: {
            "device_auth_id": "device-auth-1",
            "user_code": "ABCD-EFGH",
            "verify_url": "https://auth.openai.test/device",
            "interval": 2,
        },
    )
    device = client.post(
        "/api/oauth/login",
        json={"provider": "openai", "method": "device_code"},
    )
    assert device.status_code == 200
    device_payload = device.json()
    assert device_payload["flow_id"]
    assert device_payload["user_code"] == "ABCD-EFGH"


def test_oauth_browser_callback_persists_openai_login(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _login(client)

    monkeypatch.setattr(
        oauth_api,
        "oauth_generate_pkce",
        lambda: ("verifier-1", "challenge-1"),
    )
    monkeypatch.setattr(oauth_api, "oauth_generate_state", lambda: "state-1")
    monkeypatch.setattr(
        oauth_api,
        "oauth_build_authorize_url",
        lambda **kwargs: "https://auth.openai.test/oauth/authorize?state=state-1",
    )
    monkeypatch.setattr(
        oauth_api,
        "oauth_start_openai_callback_server",
        lambda state, on_code=None: (DummyOAuthServer(), None),
    )
    monkeypatch.setattr(
        oauth_api,
        "oauth_exchange_code_for_tokens",
        lambda **kwargs: OAuthToken(
            access="access-token",
            refresh="refresh-token",
            expires=4102444800000,
            account_id="acct-123",
        ),
    )

    login = client.post(
        "/api/oauth/login",
        json={"provider": "openai", "method": "browser"},
    )
    assert login.status_code == 200
    flow_id = login.json()["flow_id"]

    callback = client.get("/oauth/callback?state=state-1&code=code-123")
    assert callback.status_code == 200
    assert "Authentication successful" in callback.text

    flow = client.get(f"/api/oauth/flows/{flow_id}")
    assert flow.status_code == 200
    assert flow.json()["status"] == "success"

    providers = client.get("/api/oauth/providers").json()["providers"]
    openai = next(item for item in providers if item["provider"] == "openai")
    assert openai["logged_in"] is True
    assert openai["auth_method"] == "oauth"
    assert openai["account_id"] == "acct-123"

    models = client.get("/api/models").json()
    assert models["default_model"] == "gpt-5.1-codex"
    default_model = next(item for item in models["models"] if item["is_default"])
    assert default_model["model"] == "openai-codex/gpt-5.1-codex"
    assert default_model["auth_method"] == "oauth"
    assert default_model["configured"] is True


def test_oauth_device_code_poll_persists_openai_login(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _login(client)

    monkeypatch.setattr(
        oauth_api,
        "oauth_request_device_code",
        lambda: {
            "device_auth_id": "device-auth-1",
            "user_code": "ABCD-EFGH",
            "verify_url": "https://auth.openai.test/device",
            "interval": 2,
        },
    )
    monkeypatch.setattr(
        oauth_api,
        "oauth_poll_device_code_once",
        lambda device_auth_id, user_code: OAuthToken(
            access="access-token",
            refresh="refresh-token",
            expires=4102444800000,
            account_id="acct-device",
        ),
    )

    login = client.post(
        "/api/oauth/login",
        json={"provider": "openai", "method": "device_code"},
    )
    assert login.status_code == 200
    flow_id = login.json()["flow_id"]

    poll = client.post(f"/api/oauth/flows/{flow_id}/poll")
    assert poll.status_code == 200
    assert poll.json()["status"] == "success"

    providers = client.get("/api/oauth/providers").json()["providers"]
    openai = next(item for item in providers if item["provider"] == "openai")
    assert openai["logged_in"] is True
    assert openai["auth_method"] == "oauth"


def test_oauth_logout_clears_openai_oauth_state(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _login(client)

    monkeypatch.setattr(
        oauth_api,
        "oauth_generate_pkce",
        lambda: ("verifier-1", "challenge-1"),
    )
    monkeypatch.setattr(oauth_api, "oauth_generate_state", lambda: "state-1")
    monkeypatch.setattr(
        oauth_api,
        "oauth_build_authorize_url",
        lambda **kwargs: "https://auth.openai.test/oauth/authorize?state=state-1",
    )
    monkeypatch.setattr(
        oauth_api,
        "oauth_start_openai_callback_server",
        lambda state, on_code=None: (DummyOAuthServer(), None),
    )
    monkeypatch.setattr(
        oauth_api,
        "oauth_exchange_code_for_tokens",
        lambda **kwargs: OAuthToken(
            access="access-token",
            refresh="refresh-token",
            expires=4102444800000,
            account_id="acct-logout",
        ),
    )

    login = client.post(
        "/api/oauth/login",
        json={"provider": "openai", "method": "browser"},
    )
    assert login.status_code == 200
    callback = client.get("/oauth/callback?state=state-1&code=code-123")
    assert callback.status_code == 200

    logout = client.post("/api/oauth/logout", json={"provider": "openai"})
    assert logout.status_code == 200

    providers = client.get("/api/oauth/providers").json()["providers"]
    openai = next(item for item in providers if item["provider"] == "openai")
    assert openai["logged_in"] is False

    models = client.get("/api/models").json()["models"]
    codex_model = next(item for item in models if item["model"] == "openai-codex/gpt-5.1-codex")
    assert codex_model["auth_method"] == ""
    assert codex_model["configured"] is False


def test_miniclaw_token_and_websocket_chat(client: TestClient) -> None:
    _login(client)

    token_response = client.get("/api/mini/token")
    assert token_response.status_code == 200
    token_payload = token_response.json()
    assert token_payload["enabled"] is True
    assert token_payload["ws_url"].endswith("/mini/ws")

    regen_response = client.post("/api/mini/token")
    assert regen_response.status_code == 200
    regen_payload = regen_response.json()
    assert regen_payload["token"] != token_payload["token"]

    setup_response = client.post("/api/mini/setup")
    assert setup_response.status_code == 200
    assert setup_response.json()["enabled"] is True

    captured: list[tuple[str, str]] = []

    class FakeChatRuntime:
        async def stream_message(self, *, session_id: str, content: str, send_event) -> None:
            captured.append((session_id, content))
            await send_event({"type": "typing.start", "timestamp": 1})
            await send_event(
                {
                    "type": "message.create",
                    "timestamp": 2,
                    "payload": {
                        "message_id": "assistant-1",
                        "content": "partial",
                    },
                }
            )
            await send_event(
                {
                    "type": "message.update",
                    "timestamp": 3,
                    "payload": {
                        "message_id": "assistant-1",
                        "content": "partial reply",
                    },
                }
            )
            await send_event({"type": "typing.stop", "timestamp": 4})

    client.app.state.launcher_context.chat_runtime = FakeChatRuntime()
    session_id = "session-123"

    with client.websocket_connect(
        f"/mini/ws?session_id={session_id}",
        subprotocols=[f"token.{regen_payload['token']}"],
    ) as websocket:
        websocket.send_json(
            {
                "type": "message.send",
                "id": "user-1",
                "payload": {"content": "hello"},
            }
        )
        first = websocket.receive_json()
        second = websocket.receive_json()
        third = websocket.receive_json()
        fourth = websocket.receive_json()

    assert captured == [(session_id, "hello")]
    assert [first["type"], second["type"], third["type"], fourth["type"]] == [
        "typing.start",
        "message.create",
        "message.update",
        "typing.stop",
    ]
    assert second["session_id"] == session_id
    assert third["payload"]["content"] == "partial reply"


def test_config_with_utf8_bom(client: TestClient) -> None:
    _login(client)

    response = client.get("/api/config")
    config_path = Path(client.app.state.launcher_context.config_path)
    original = config_path.read_text(encoding="utf-8")
    config_path.write_text(original, encoding="utf-8-sig")

    bom_response = client.get("/api/config")
    assert bom_response.status_code == 200
    assert bom_response.json()["agents"]["defaults"]["workspace"]
