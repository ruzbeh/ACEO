"""One-time YouTube OAuth helper — mints a refresh token for uploads.

Run this once. It opens a Google consent page in your browser, you grant the
upload + read + analytics permissions, and it prints a refresh token to paste
into .env as YOUTUBE_OAUTH_REFRESH_TOKEN. (Read + analytics scopes are needed so
scripts/yt_analytics.py can pull views/watch-time/retention, not just upload.)

Prereqs (in Google Cloud Console, one time):
  1. Create a project; enable "YouTube Data API v3".
  2. Configure the OAuth consent screen (External; add yourself as a Test user).
  3. Create an OAuth client ID of type "Desktop app". Download the JSON.

Usage:
  python scripts/youtube_oauth.py --client-secrets-file ~/Downloads/client_secret.json
  # or
  python scripts/youtube_oauth.py --client-id XXX --client-secret YYY

Desktop-app clients allow loopback redirects (http://localhost:<port>) on any
port without pre-registering it, so no redirect-URI setup is needed.
"""
from __future__ import annotations

import argparse
import json
import socket
import sys
import threading
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

import httpx

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPE = (
    "https://www.googleapis.com/auth/youtube.upload "
    "https://www.googleapis.com/auth/youtube.readonly "
    "https://www.googleapis.com/auth/yt-analytics.readonly"
)


def _load_creds(args) -> tuple[str, str]:
    if args.client_secrets_file:
        with open(args.client_secrets_file) as f:
            data = json.load(f)
        node = data.get("installed") or data.get("web") or {}
        cid = node.get("client_id")
        csecret = node.get("client_secret")
        if not cid or not csecret:
            sys.exit("client_secrets file missing client_id/client_secret")
        return cid, csecret
    if args.client_id and args.client_secret:
        return args.client_id, args.client_secret
    sys.exit("Provide --client-secrets-file OR --client-id and --client-secret")


def _free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class _Handler(BaseHTTPRequestHandler):
    code: str | None = None
    error: str | None = None

    def do_GET(self):  # noqa: N802
        qs = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(qs)
        _Handler.code = params.get("code", [None])[0]
        _Handler.error = params.get("error", [None])[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        msg = "Authorization complete. You can close this tab." if _Handler.code else (
            f"Authorization failed: {_Handler.error}"
        )
        self.wfile.write(f"<html><body><h2>{msg}</h2></body></html>".encode())

    def log_message(self, *_args):  # silence the default stderr logging
        pass


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--client-secrets-file")
    ap.add_argument("--client-id")
    ap.add_argument("--client-secret")
    args = ap.parse_args()

    client_id, client_secret = _load_creds(args)
    port = _free_port()
    redirect_uri = f"http://localhost:{port}/"

    auth_url = AUTH_URL + "?" + urllib.parse.urlencode(
        {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": SCOPE,
            "access_type": "offline",
            "prompt": "consent",  # force a refresh_token even on re-auth
        }
    )

    server = HTTPServer(("127.0.0.1", port), _Handler)
    t = threading.Thread(target=server.handle_request, daemon=True)
    t.start()

    print("\nOpening your browser to authorize YouTube upload access…")
    print("If it doesn't open, paste this URL:\n")
    print(auth_url + "\n")
    webbrowser.open(auth_url)

    t.join(timeout=300)
    server.server_close()

    if _Handler.error:
        sys.exit(f"\nAuthorization failed: {_Handler.error}")
    if not _Handler.code:
        sys.exit("\nTimed out waiting for authorization (5 min).")

    resp = httpx.post(
        TOKEN_URL,
        data={
            "code": _Handler.code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        },
        timeout=30,
    )
    if resp.status_code >= 400:
        sys.exit(f"\nToken exchange failed ({resp.status_code}): {resp.text}")

    tok = resp.json()
    refresh = tok.get("refresh_token")
    if not refresh:
        sys.exit(
            "\nNo refresh_token returned. Revoke the app's access at "
            "https://myaccount.google.com/permissions and re-run."
        )

    print("\n" + "=" * 64)
    print("SUCCESS — add these to your .env:")
    print("=" * 64)
    print(f"YOUTUBE_OAUTH_CLIENT_ID={client_id}")
    print(f"YOUTUBE_OAUTH_CLIENT_SECRET={client_secret}")
    print(f"YOUTUBE_OAUTH_REFRESH_TOKEN={refresh}")
    print("=" * 64)


if __name__ == "__main__":
    main()
