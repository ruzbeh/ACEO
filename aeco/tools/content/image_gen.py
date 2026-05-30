"""Text-to-image for reel scene backgrounds.

Primary: Google Imagen 4 Fast (paid, reliable, native 9:16) via the Gemini API.
Fallback: Pollinations (free, Flux) if the Google key is missing or Imagen fails.

Returns absolute paths to saved JPEGs; the caller base64-encodes them into the
Remotion props as `imageSrc`.
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import logging
import os
import urllib.parse
from pathlib import Path
from typing import Optional

import httpx

from aeco.config import settings

logger = logging.getLogger(__name__)

_IMG_DIR = Path(__file__).resolve().parents[3] / "workspace" / "content" / "images"
_IMG_DIR.mkdir(parents=True, exist_ok=True)
_IMAGEN_URL = "https://generativelanguage.googleapis.com/v1beta/models/imagen-4.0-fast-generate-001:predict"
_POLL_URL = "https://image.pollinations.ai/prompt/"

STYLE_SUFFIX = (
    ", cinematic painterly illustration, teal and warm amber color palette, "
    "soft volumetric light, dramatic rim lighting, shallow depth of field, "
    "premium biohacking aesthetic, highly detailed, vertical 9:16 composition, "
    "no text, no words, no letters, no captions, no watermark, no logos, "
    "no product labels, no jars or bottles with text, no signage"
)


def _google_key() -> Optional[str]:
    return os.environ.get("GOOGLE_API_KEY") or settings.google_api_key


async def _imagen(prompt: str, *, timeout: float) -> Optional[bytes]:
    key = _google_key()
    if not key:
        return None
    body = {"instances": [{"prompt": prompt}],
            "parameters": {"sampleCount": 1, "aspectRatio": "9:16"}}
    try:
        async with httpx.AsyncClient(timeout=timeout) as c:
            r = await c.post(_IMAGEN_URL, params={"key": key}, json=body)
        if r.status_code == 200:
            preds = r.json().get("predictions", [])
            if preds and preds[0].get("bytesBase64Encoded"):
                return base64.b64decode(preds[0]["bytesBase64Encoded"])
            logger.warning("imagen: no image (safety filter?) %s", str(r.json())[:160])
        else:
            logger.warning("imagen %s: %s", r.status_code, r.text[:160])
    except Exception as e:  # noqa: BLE001
        logger.warning("imagen error: %s", str(e)[:140])
    return None


async def _pollinations(prompt: str, *, seed: int, width: int, height: int, timeout: float) -> Optional[bytes]:
    params = {"width": width, "height": height, "nologo": "true", "model": "flux", "seed": seed}
    url = _POLL_URL + urllib.parse.quote(prompt)
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as c:
            r = await c.get(url, params=params)
        if r.status_code == 200 and "image" in r.headers.get("content-type", "") and len(r.content) > 2000:
            return r.content
        logger.warning("pollinations %s %s", r.status_code, r.headers.get("content-type"))
    except Exception as e:  # noqa: BLE001
        logger.warning("pollinations error: %s", str(e)[:140])
    return None


async def generate_image(
    prompt: str, *, width: int = 1080, height: int = 1920,
    seed: Optional[int] = None, timeout: float = 120.0, attempts: int = 2,
) -> Optional[str]:
    """Generate one scene image (Imagen primary, Pollinations fallback). Returns path or None."""
    full = prompt.strip() + STYLE_SUFFIX
    if seed is None:
        seed = int(hashlib.md5(full.encode()).hexdigest()[:6], 16)
    data: Optional[bytes] = None
    for attempt in range(1, attempts + 1):
        data = await _imagen(full, timeout=timeout)
        if data:
            break
        if attempt < attempts:
            await asyncio.sleep(2.0 * attempt)
    if not data:  # fall back to the free provider
        data = await _pollinations(full, seed=seed, width=width, height=height, timeout=timeout)
    if data:
        out = _IMG_DIR / f"img-{hashlib.md5((full + str(seed)).encode()).hexdigest()[:12]}.jpg"
        out.write_bytes(data)
        return str(out)
    return None


async def generate_images_batch(
    prompts: list[str], *, base_seed: int = 0, concurrency: int = 3
) -> list[Optional[str]]:
    """Generate one image per prompt. Order preserved. Imagen (paid) tolerates concurrency."""
    sem = asyncio.Semaphore(max(1, concurrency))

    async def one(i: int, p: str):
        async with sem:
            return await generate_image(p, seed=(base_seed + i * 7919) % 1_000_000)

    return await asyncio.gather(*(one(i, p) for i, p in enumerate(prompts)))
