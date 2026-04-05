from __future__ import annotations

import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Callable

SUCCESS_HTML = """<!doctype html><html><body><h2>Login completed</h2><p>You can return to the CLI.</p></body></html>"""


class _OAuthHandler(BaseHTTPRequestHandler):
    server_version = "OAuthCliKit/1.0"
    protocol_version = "HTTP/1.1"

    def do_GET(self) -> None:  # noqa: N802
        try:
            url = urllib.parse.urlparse(self.path)
            if url.path != "/auth/callback":
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"Not found")
                return

            qs = urllib.parse.parse_qs(url.query)
            code = qs.get("code", [None])[0]
            state = qs.get("state", [None])[0]
            if state != self.server.expected_state:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"State mismatch")
                return
            if not code:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"Missing code")
                return

            self.server.code = code
            try:
                if getattr(self.server, "on_code", None):
                    self.server.on_code(code)
            except Exception:
                pass

            body = SUCCESS_HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(body)
            try:
                self.wfile.flush()
            except Exception:
                pass
            self.close_connection = True
        except Exception:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(b"Internal error")

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        return


class _OAuthServer(HTTPServer):
    def __init__(
        self,
        server_address: tuple[str, int],
        expected_state: str,
        on_code: Callable[[str], None] | None = None,
    ):
        super().__init__(server_address, _OAuthHandler)
        self.expected_state = expected_state
        self.code: str | None = None
        self.on_code = on_code


def _start_local_server(
    state: str,
    on_code: Callable[[str], None] | None = None,
) -> tuple[_OAuthServer | None, str | None]:
    # Bind to 0.0.0.0 so Docker port forwarding (which connects via bridge network)
    # can reach this server. Binding to "localhost"/127.0.0.1 only accepts loopback
    # connections, which blocks Docker's proxy from forwarding host:1455 -> container:1455.
    # Security is maintained via the cryptographic `state` parameter validation.
    try:
        server = _OAuthServer(("0.0.0.0", 1455), state, on_code=on_code)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        return server, None
    except OSError as exc:
        return None, f"Local callback server failed to start: {exc}"
