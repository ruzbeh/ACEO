"""Publish a rendered MP4 to FB/IG as a PAUSED video ad.

Flow:
    1. Upload the MP4 → /act_{id}/advideos → video_id
    2. Wait for encoding → poll /video_id?fields=status
    3. Capture a thumbnail (first frame) → /advideos/{id}/thumbnails
    4. Create ad creative with video_data pointing at video_id + thumbnail
    5. Create ad under the given adset in PAUSED status

The user toggles the ad to ACTIVE in Meta Ads Manager after reviewing.
"""
from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

import httpx

from aeco.config import settings

logger = logging.getLogger(__name__)

_BASE_URL = "https://graph.facebook.com/v19.0"


def _token() -> str:
    tok = getattr(settings, "facebook_access_token", None)
    if not tok:
        raise RuntimeError("FACEBOOK_ACCESS_TOKEN not configured")
    return tok


def _account_id() -> str:
    aid = getattr(settings, "facebook_ad_account_id", "")
    return aid.replace("act_", "") if aid else ""


async def upload_video_to_facebook(
    video_path: str,
    name: str = "AECO reel",
    *,
    timeout: int = 300,
) -> dict[str, Any]:
    """Upload an MP4 to the ad account.

    Meta supports "non-resumable" upload via multipart form for videos under
    ~1GB. For our 25s reels (~4-8 MB) this is plenty.

    Returns: {"id": video_id, "status": "ready" | "processing" | ...}
    """
    path = Path(video_path)
    if not path.exists():
        raise FileNotFoundError(video_path)

    async with httpx.AsyncClient(timeout=timeout) as client:
        with open(path, "rb") as fh:
            files = {"source": (path.name, fh.read(), "video/mp4")}
        data = {"name": name, "access_token": _token()}
        resp = await client.post(
            f"{_BASE_URL}/act_{_account_id()}/advideos",
            data=data,
            files=files,
        )
        if resp.status_code >= 400:
            logger.error("upload_video failed: %s", resp.text)
        resp.raise_for_status()
        body = resp.json()
        video_id = body.get("id")
        if not video_id:
            raise RuntimeError(f"No video_id in response: {body}")

        # Poll for encoding completion
        status = "processing"
        deadline = asyncio.get_event_loop().time() + timeout
        while status not in {"ready", "error"} and asyncio.get_event_loop().time() < deadline:
            await asyncio.sleep(4)
            poll = await client.get(
                f"{_BASE_URL}/{video_id}",
                params={"fields": "status", "access_token": _token()},
            )
            if poll.status_code >= 400:
                continue
            status_obj = poll.json().get("status", {})
            status = status_obj.get("video_status") or status_obj.get("processing_progress") or "processing"

        return {"id": video_id, "status": status}


async def _first_thumbnail(video_id: str) -> str | None:
    """Return the default thumbnail URI Meta generated for this video."""
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.get(
            f"{_BASE_URL}/{video_id}/thumbnails",
            params={"access_token": _token()},
        )
        if resp.status_code >= 400:
            return None
        data = resp.json().get("data", [])
        if not data:
            return None
        # Prefer is_preferred=true; fall back to first
        for t in data:
            if t.get("is_preferred"):
                return t.get("uri")
        return data[0].get("uri")


async def create_video_ad(
    video_id: str,
    adset_id: str,
    page_id: str,
    *,
    ad_name: str,
    message: str,           # Primary text above video
    headline: str,          # Bold headline under video
    description: str,       # Smaller description
    link: str,              # Destination URL
    call_to_action: str = "LEARN_MORE",
    status: str = "PAUSED",
) -> dict[str, Any]:
    """Create an ad creative + ad for a video, under the given adset, PAUSED by default."""
    thumb = await _first_thumbnail(video_id)

    object_story_spec = {
        "page_id": page_id,
        "video_data": {
            "video_id": video_id,
            "title": headline,
            "message": message,
            "call_to_action": {
                "type": call_to_action,
                "value": {"link": link},
            },
            "link_description": description,
            **({"image_url": thumb} if thumb else {}),
        },
    }

    async with httpx.AsyncClient(timeout=120) as client:
        # 1) Creative
        creative_resp = await client.post(
            f"{_BASE_URL}/act_{_account_id()}/adcreatives",
            data={
                "name": f"{ad_name} — Creative",
                "object_story_spec": json.dumps(object_story_spec),
                "access_token": _token(),
            },
        )
        if creative_resp.status_code >= 400:
            logger.error("creative failed: %s", creative_resp.text)
        creative_resp.raise_for_status()
        creative_id = creative_resp.json()["id"]

        # 2) Ad
        ad_resp = await client.post(
            f"{_BASE_URL}/act_{_account_id()}/ads",
            data={
                "name": ad_name,
                "adset_id": adset_id,
                "creative": json.dumps({"creative_id": creative_id}),
                "status": status,
                "access_token": _token(),
            },
        )
        if ad_resp.status_code >= 400:
            logger.error("ad failed: %s", ad_resp.text)
        ad_resp.raise_for_status()
        ad_id = ad_resp.json()["id"]

    return {
        "video_id": video_id,
        "creative_id": creative_id,
        "ad_id": ad_id,
        "status": status,
        "ads_manager_url": (
            f"https://business.facebook.com/adsmanager/manage/ads"
            f"?act={_account_id()}&selected_ad_ids={ad_id}"
        ),
    }
