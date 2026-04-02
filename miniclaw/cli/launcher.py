from __future__ import annotations

import argparse
import os
import sys
import threading
import time
import webbrowser
from pathlib import Path
from urllib.parse import quote


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _launcher_root() -> Path:
    return _repo_root() / "web" / "backend"


def _ensure_import_paths() -> Path:
    repo_root = _repo_root()
    launcher_root = _launcher_root()
    backend_main = launcher_root / "backend" / "main.py"
    if not backend_main.is_file():
        raise SystemExit(
            f"Launcher backend not found at {backend_main}. "
            "Run this command from the miniclaw source tree."
        )

    repo_text = str(repo_root)
    launcher_text = str(launcher_root)
    if repo_text not in sys.path:
        sys.path.insert(0, repo_text)
    if launcher_text not in sys.path:
        sys.path.insert(0, launcher_text)
    return launcher_root


def _local_ipv4() -> str:
    import socket

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return ""
    finally:
        sock.close()


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="miniclaw-launcher",
        description="Run the miniclaw web launcher dashboard.",
    )
    parser.add_argument("config", nargs="?", help="Path to the miniclaw config file.")
    parser.add_argument("--port", type=int, help="Launcher port override.")
    parser.add_argument(
        "--public",
        action="store_true",
        help="Listen on 0.0.0.0 instead of localhost.",
    )
    parser.add_argument(
        "--private",
        dest="public",
        action="store_false",
        help="Force localhost-only mode.",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not auto-open the browser on startup.",
    )
    parser.set_defaults(public=None)
    return parser.parse_args(argv)


def _resolve_options(args: argparse.Namespace) -> tuple[Path, int, bool]:
    _ensure_import_paths()

    from backend.launcherconfig.config import LauncherConfig, load, path_for_app_config
    from backend.utils.config_store import resolve_config_path

    explicit = None
    if args.config:
        explicit = str(Path(args.config).expanduser().resolve())
        os.environ["MINICLAW_CONFIG"] = explicit

    config_path = resolve_config_path(explicit or os.environ.get("MINICLAW_CONFIG") or None)
    launcher_cfg = load(path_for_app_config(config_path), fallback=LauncherConfig())

    port = args.port if args.port is not None else launcher_cfg.port
    public = launcher_cfg.public if args.public is None else bool(args.public)
    return config_path, port, public


def _print_startup(url: str, token: str, token_from_env: bool, public: bool, port: int) -> None:
    print()
    print("Miniclaw Launcher")
    print()
    print(f"Open {url} in your browser")
    if public:
        lan_ip = _local_ipv4()
        if lan_ip:
            print(f"LAN URL: http://{lan_ip}:{port}")
    print()
    if token_from_env:
        print(f"Dashboard token: {token} (from MINICLAW_LAUNCHER_TOKEN)")
    else:
        print(f"Dashboard token (this run): {token}")
    print()


def _open_when_ready(server, url: str) -> None:
    for _ in range(300):
        if getattr(server, "started", False):
            try:
                webbrowser.open(url)
            except Exception as exc:
                print(f"Warning: failed to auto-open browser: {exc}", file=sys.stderr)
            return
        if getattr(server, "should_exit", False):
            return
        time.sleep(0.1)


def run(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    _config_path, port, public = _resolve_options(args)
    os.environ["MINICLAW_LAUNCHER_SUPPRESS_STARTUP_TOKEN"] = "1"

    from backend.main import create_app
    import uvicorn

    app = create_app()
    context = app.state.launcher_context
    host = "0.0.0.0" if public else "127.0.0.1"
    base_url = f"http://localhost:{port}"
    browser_url = f"{base_url}?token={quote(context.dashboard_token)}"
    token_from_env = bool(os.environ.get("MINICLAW_LAUNCHER_TOKEN", "").strip())

    _print_startup(base_url, context.dashboard_token, token_from_env, public, port)

    config = uvicorn.Config(app=app, host=host, port=port, log_level="info")
    server = uvicorn.Server(config)
    if not args.no_browser:
        threading.Thread(target=_open_when_ready, args=(server, browser_url), daemon=True).start()

    try:
        server.run()
    except KeyboardInterrupt:
        return 130
    return 0


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
