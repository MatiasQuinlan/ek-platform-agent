from __future__ import annotations

import base64
import hashlib
import http.server
import json
import os
import secrets
import threading
import urllib.parse
import urllib.request
import webbrowser
from typing import Any

DEFAULT_REGION = "us-east-1"
DEFAULT_USER_POOL_CLIENT = "3pauvl8f3ba4tstu3114ojuuj0"
DEFAULT_DOMAIN = "ek-platform-859464365973-production"
CALLBACK = "http://127.0.0.1:8765/callback"


def login() -> str:
    region = os.environ.get("EK_COGNITO_REGION", DEFAULT_REGION)
    client_id = os.environ.get("EK_COGNITO_CLIENT_ID", DEFAULT_USER_POOL_CLIENT)
    domain = os.environ.get("EK_COGNITO_DOMAIN", DEFAULT_DOMAIN)
    verifier = secrets.token_urlsafe(64)
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    )
    result: dict[str, str] = {}

    class Callback(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            result["code"] = query.get("code", [""])[0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"<h2>EK Platform conectado. Puedes cerrar esta ventana.</h2>")

        def log_message(self, *_args: Any) -> None:
            return

    server = http.server.HTTPServer(("127.0.0.1", 8765), Callback)
    thread = threading.Thread(target=server.handle_request, daemon=True)
    thread.start()
    params = urllib.parse.urlencode(
        {
            "client_id": client_id,
            "response_type": "code",
            "scope": "openid email profile",
            "redirect_uri": CALLBACK,
            "code_challenge_method": "S256",
            "code_challenge": challenge,
        }
    )
    webbrowser.open(f"https://{domain}.auth.{region}.amazoncognito.com/oauth2/authorize?{params}")
    thread.join(timeout=300)
    server.server_close()
    if not result.get("code"):
        raise RuntimeError("No se completó el login de EK Platform")
    token_request = urllib.parse.urlencode(
        {
            "grant_type": "authorization_code",
            "client_id": client_id,
            "code": result["code"],
            "redirect_uri": CALLBACK,
            "code_verifier": verifier,
        }
    ).encode()
    request = urllib.request.Request(
        f"https://{domain}.auth.{region}.amazoncognito.com/oauth2/token",
        data=token_request,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read())
    token = payload.get("access_token")
    if not isinstance(token, str) or not token:
        raise RuntimeError("Cognito no devolvió un access token")
    return token
