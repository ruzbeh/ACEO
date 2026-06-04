"""YouTube Data API v3 uploader — publishes a vertical MP4 as a Short.

Uses raw httpx (no google-api-python-client dependency):
  1. refresh the OAuth access token from a stored refresh_token
  2. start a resumable upload session (videos.insert, part=snippet,status)
  3. PUT the file bytes to the returned session URL

Auth: a 3-legged OAuth user flow. Mint the refresh_token once with
scripts/youtube_oauth.py, then set YOUTUBE_OAUTH_REFRESH_TOKEN in .env.

A video is treated as a Short by YouTube when it's vertical and <= 60s; we also
append #Shorts to the description as a strong hint.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

import httpx

from aeco.config import settings

logger = logging.getLogger(__name__)

_TOKEN_URL = "https://oauth2.googleapis.com/token"
_RESUMABLE_URL = (
    "https://www.googleapis.com/upload/youtube/v3/videos"
    "?uploadType=resumable&part=snippet,status"
)
# 28 = "Science & Technology"
DEFAULT_CATEGORY_ID = "28"


class YouTubeError(RuntimeError):
    pass


def _cred(name: str, attr: str) -> str:
    val = os.environ.get(name) or getattr(settings, attr, None)
    if not val:
        raise YouTubeError(
            f"{name} not set. Add it to .env (mint the refresh token with "
            "scripts/youtube_oauth.py)."
        )
    return val


async def refresh_access_token(
    *,
    client_id: Optional[str] = None,
    client_secret: Optional[str] = None,
    refresh_token: Optional[str] = None,
    timeout_sec: float = 30.0,
) -> str:
    """Exchange a refresh token for a short-lived access token."""
    client_id = client_id or _cred("YOUTUBE_OAUTH_CLIENT_ID", "youtube_oauth_client_id")
    client_secret = client_secret or _cred(
        "YOUTUBE_OAUTH_CLIENT_SECRET", "youtube_oauth_client_secret"
    )
    refresh_token = refresh_token or _cred(
        "YOUTUBE_OAUTH_REFRESH_TOKEN", "youtube_oauth_refresh_token"
    )

    async with httpx.AsyncClient(timeout=timeout_sec) as client:
        resp = await client.post(
            _TOKEN_URL,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
    if resp.status_code >= 400:
        raise YouTubeError(
            f"Token refresh failed ({resp.status_code}): {resp.text[:400]}. "
            "If this is 'invalid_grant', the refresh token was revoked/expired — "
            "re-run scripts/youtube_oauth.py."
        )
    token = resp.json().get("access_token")
    if not token:
        raise YouTubeError(f"Token refresh returned no access_token: {resp.text[:400]}")
    return token


async def upload_short(
    mp4_path: str | Path,
    *,
    title: str,
    description: str = "",
    tags: Optional[list[str]] = None,
    category_id: str = DEFAULT_CATEGORY_ID,
    privacy: str = "unlisted",  # "private" | "unlisted" | "public"
    made_for_kids: bool = False,
    access_token: Optional[str] = None,
    timeout_sec: float = 600.0,
) -> dict:
    """Upload a vertical MP4 as a YouTube Short. Returns the video resource dict
    (includes 'id'). Adds a watch URL under 'watch_url'.
    """
    path = Path(mp4_path)
    if not path.exists() or path.stat().st_size == 0:
        raise YouTubeError(f"MP4 missing or empty: {path}")

    # YouTube enforces a 100-char title limit; keep #Shorts discoverable in the body.
    title = title.strip()[:100]
    if "#shorts" not in description.lower():
        description = (description.rstrip() + "\n\n#Shorts").strip()
    tags = tags or []

    token = access_token or await refresh_access_token()
    size = path.stat().st_size
    metadata = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": category_id,
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": made_for_kids,
        },
    }

    async with httpx.AsyncClient(timeout=timeout_sec) as client:
        # 1) Initiate the resumable session.
        init = await client.post(
            _RESUMABLE_URL,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json; charset=UTF-8",
                "X-Upload-Content-Type": "video/mp4",
                "X-Upload-Content-Length": str(size),
            },
            json=metadata,
        )
        if init.status_code >= 400:
            raise YouTubeError(
                f"Resumable init failed ({init.status_code}): {init.text[:400]}"
            )
        session_url = init.headers.get("location") or init.headers.get("Location")
        if not session_url:
            raise YouTubeError("Resumable init succeeded but returned no upload URL")

        logger.info("YouTube: uploading %.1f MB → %s", size / 1e6, title)
        # 2) Upload the bytes in one PUT (Shorts are small).
        put = await client.put(
            session_url,
            headers={"Content-Type": "video/mp4", "Content-Length": str(size)},
            content=path.read_bytes(),
        )
    if put.status_code not in (200, 201):
        raise YouTubeError(f"Upload failed ({put.status_code}): {put.text[:400]}")

    data = put.json()
    vid = data.get("id")
    if not vid:
        raise YouTubeError(f"Upload returned no video id: {str(data)[:400]}")
    data["watch_url"] = f"https://www.youtube.com/shorts/{vid}"
    logger.info("YouTube: uploaded %s (%s) → %s", vid, privacy, data["watch_url"])
    return data
