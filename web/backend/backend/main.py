from __future__ import annotations

import os
import secrets
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from miniclaw.config.loader import set_config_path

from backend.api.router import router as api_router
from backend.app_runtime import GatewayRuntime
from backend.launcherconfig.config import LauncherConfig, ensure_dashboard_secrets, load, path_for_app_config
from backend.middleware.launcher_dashboard_auth import session_cookie_value
from backend.middleware.middleware import access_control_middleware, dashboard_auth_middleware, referrer_policy_middleware
from backend.utils.config_store import resolve_config_path
from backend.utils.context import LauncherContext
from backend.utils.model_store import model_store_path_for_config
from backend.utils.web_chat import WebChatRuntime


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _build_context() -> LauncherContext:
    project_root = _project_root()
    explicit_config = os.environ.get("MINICLAW_CONFIG", "").strip() or None
    config_path = resolve_config_path(explicit_config)
    launcher_config_path = path_for_app_config(config_path)
    load(launcher_config_path, fallback=LauncherConfig())

    dashboard_token, signing_key, generated = ensure_dashboard_secrets()
    return LauncherContext(
        project_root=project_root,
        config_path=config_path,
        launcher_config_path=launcher_config_path,
        models_store_path=model_store_path_for_config(config_path),
        runtime=GatewayRuntime(config_path=config_path, project_root=project_root),
        dashboard_token=dashboard_token,
        dashboard_session_cookie=session_cookie_value(signing_key, dashboard_token),
        dashboard_token_generated=generated,
        chat_ws_token=secrets.token_urlsafe(24),
        chat_runtime=WebChatRuntime(config_path=config_path),
    )


def _frontend_file(context: LauncherContext, relative_path: str) -> Path | None:
    clean = relative_path.lstrip("/").replace("\\", "/")
    if ".." in clean.split("/"):
        return None
    for dist_dir in context.frontend_dist_candidates:
        candidate = (dist_dir / clean).resolve()
        try:
            candidate.relative_to(dist_dir.resolve())
        except ValueError:
            continue
        if candidate.is_file():
            return candidate
    return None


def _frontend_index(context: LauncherContext) -> Path | None:
    for dist_dir in context.frontend_dist_candidates:
        candidate = dist_dir / "index.html"
        if candidate.is_file():
            return candidate
    return None


def _fallback_login_page() -> str:
    return """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Miniclaw Launcher Login</title>
    <style>
      body { margin: 0; font-family: system-ui, sans-serif; background: #f6f7f9; color: #111827; }
      main { min-height: 100vh; display: grid; place-items: center; padding: 24px; }
      form { width: 100%; max-width: 420px; background: #fff; border-radius: 18px; padding: 24px; box-shadow: 0 16px 40px rgba(15, 23, 42, 0.08); }
      h1 { margin: 0 0 8px; font-size: 24px; }
      p { margin: 0 0 18px; color: #4b5563; }
      input { width: 100%; box-sizing: border-box; padding: 12px 14px; border: 1px solid #d1d5db; border-radius: 12px; font-size: 14px; }
      button { margin-top: 12px; width: 100%; padding: 12px 14px; border: 0; border-radius: 12px; background: #111827; color: #fff; font-weight: 600; cursor: pointer; }
      #error { color: #b91c1c; margin-top: 12px; min-height: 20px; }
      code { background: #f3f4f6; padding: 2px 6px; border-radius: 6px; }
    </style>
  </head>
  <body>
    <main>
      <form id="login-form">
        <h1>Miniclaw Launcher</h1>
        <p>Enter the dashboard token. If you launched this app from the terminal, the token is printed there.</p>
        <input id="token" type="password" autocomplete="current-password" placeholder="Dashboard token" required />
        <button type="submit">Sign in</button>
        <div id="error"></div>
        <p style="margin-top:16px">You can also set <code>MINICLAW_LAUNCHER_TOKEN</code> before starting the launcher.</p>
      </form>
    </main>
    <script>
      document.getElementById("login-form").addEventListener("submit", async function (event) {
        event.preventDefault();
        var token = document.getElementById("token").value.trim();
        var error = document.getElementById("error");
        error.textContent = "";
        var response = await fetch("/api/auth/login", {
          method: "POST",
          credentials: "same-origin",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ token: token })
        });
        if (!response.ok) {
          error.textContent = "Invalid token.";
          return;
        }
        window.location.assign("/");
      });
    </script>
  </body>
</html>
    """.strip()


def _fallback_app_page(context: LauncherContext) -> str:
    return f"""
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Miniclaw Launcher</title>
    <style>
      body {{ margin: 0; font-family: system-ui, sans-serif; background: #f6f7f9; color: #111827; }}
      main {{ max-width: 760px; margin: 0 auto; padding: 32px 24px 48px; }}
      section {{ background: #fff; border-radius: 18px; padding: 24px; box-shadow: 0 16px 40px rgba(15, 23, 42, 0.08); }}
      code {{ background: #f3f4f6; padding: 2px 6px; border-radius: 6px; }}
      ul {{ line-height: 1.7; }}
    </style>
  </head>
  <body>
    <main>
      <section>
        <h1>Miniclaw Python launcher</h1>
        <p>The frontend build was not found, so the launcher is serving a minimal fallback page.</p>
        <ul>
          <li>Config file: <code>{context.config_path}</code></li>
          <li>Launcher config: <code>{context.launcher_config_path}</code></li>
          <li>API root: <code>/api/*</code></li>
          <li>Login page: <code>/launcher-login</code></li>
        </ul>
      </section>
    </main>
  </body>
</html>
    """.strip()


def create_app() -> FastAPI:
    app = FastAPI(title="Miniclaw Python Launcher")
    context = _build_context()
    app.state.launcher_context = context
    app.state.oauth_flows = {}

    @app.on_event("startup")
    async def startup() -> None:
        set_config_path(context.config_path)
        if context.dashboard_token_generated and os.environ.get("MINICLAW_LAUNCHER_SUPPRESS_STARTUP_TOKEN") != "1":
            print(f"Miniclaw launcher token: {context.dashboard_token}")

    app.middleware("http")(referrer_policy_middleware)
    app.middleware("http")(access_control_middleware)
    app.middleware("http")(dashboard_auth_middleware)

    app.include_router(api_router)

    @app.get("/{full_path:path}")
    async def frontend(full_path: str, request: Request):
        path = "/" + full_path.strip("/")
        if path == "/":
            path = "/"
        if path.startswith("/api/") or path.startswith("/oauth/"):
            return JSONResponse({"error": "not found"}, status_code=404)

        static_target = _frontend_file(context, path)
        if static_target:
            return FileResponse(static_target)

        index_file = _frontend_index(context)
        if index_file:
            return FileResponse(index_file)

        if request.url.path == "/launcher-login":
            return HTMLResponse(_fallback_login_page())
        return HTMLResponse(_fallback_app_page(context))

    return app


app = create_app()
