"""Runway ML image-to-video client — Gen-4 Turbo.

Endpoints used:
    POST https://api.dev.runwayml.com/v1/image_to_video  — create task
    GET  https://api.dev.runwayml.com/v1/tasks/{id}      — poll task

Returns a local MP4 path when a task completes.

Usage:
    from aeco.tools.video.runway import image_to_video
    path = await image_to_video(
        image_path="/path/to/headshot.jpg",
        prompt_text="Subtle head turn, professional confidence, cinematic studio lighting",
        duration=5,
        ratio="720:1280",
    )
"""
from __future__ import annotations

import asyncio
import base64
import logging
import mimetypes
import os
import uuid
from pathlib import Path
from typing import Any, Optional

import httpx

from aeco.config import settings

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.dev.runwayml.com/v1"
_VERSION_HEADER = "2024-11-06"

# Local output dir for Runway-generated clips
_AECO_ROOT = Path(__file__).resolve().parents[3]
_RUNWAY_DIR = _AECO_ROOT / "workspace" / "reels" / "runway"
_RUNWAY_DIR.mkdir(parents=True, exist_ok=True)


class RunwayError(RuntimeError):
    """Raised when Runway returns an error or times out."""


def _api_key() -> str:
    key = os.environ.get("RUNWAY_API_KEY") or getattr(settings, "runway_api_key", None)
    if not key:
        raise RunwayError(
            "RUNWAY_API_KEY not set. Add it to .env or export it — see aeco/config.py."
        )
    return key


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {_api_key()}",
        "X-Runway-Version": _VERSION_HEADER,
        "Content-Type": "application/json",
    }


def _image_to_data_uri(path: Path) -> str:
    mime, _ = mimetypes.guess_type(str(path))
    mime = mime or "image/jpeg"
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{data}"


async def image_to_video(
    image_path: str | Path,
    prompt_text: str = "Subtle professional motion, cinematic studio lighting, natural expression",
    *,
    duration: int = 5,
    ratio: str = "720:1280",
    model: str = "gen4_turbo",
    poll_interval_sec: float = 4.0,
    timeout_sec: float = 240.0,
    output_dir: Path | None = None,
) -> str:
    """Create an image-to-video task, poll to completion, download to local disk.

    Args:
        image_path: Local path to the input image (or an http(s) URL).
        prompt_text: Motion/style prompt. Keep under ~200 chars.
        duration: Seconds of video. Runway Gen-4 Turbo supports 5 or 10.
        ratio: Output aspect, as "WIDTH:HEIGHT". Use "720:1280" for 9:16 Reels.
        model: "gen4_turbo" is fast + cheap; "gen4.5" gives higher fidelity.
        poll_interval_sec: Seconds between task-status polls.
        timeout_sec: Give up after this many seconds.
        output_dir: Where to save the MP4 (defaults to workspace/reels/runway).

    Returns:
        Absolute filesystem path to the downloaded MP4.
    """
    image_path = Path(image_path) if not str(image_path).startswith(("http://", "https://")) else image_path
    output_dir = output_dir or _RUNWAY_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    # If local path, convert to data URI. Runway accepts both URLs and data: URIs.
    if isinstance(image_path, Path):
        if not image_path.exists():
            raise FileNotFoundError(str(image_path))
        prompt_image = _image_to_data_uri(image_path)
    else:
        prompt_image = str(image_path)

    payload = {
        "model": model,
        "promptImage": prompt_image,
        "promptText": prompt_text,
        "ratio": ratio,
        "duration": duration,
    }

    logger.info("Runway: creating image_to_video task (model=%s, %ds, %s)", model, duration, ratio)

    async with httpx.AsyncClient(timeout=60) as client:
        create_resp = await client.post(
            f"{_BASE_URL}/image_to_video",
            json=payload,
            headers=_headers(),
        )
        if create_resp.status_code >= 400:
            raise RunwayError(
                f"Create failed ({create_resp.status_code}): {create_resp.text[:500]}"
            )
        created = create_resp.json()
        task_id = created.get("id")
        if not task_id:
            raise RunwayError(f"No task id in response: {created}")
        logger.info("Runway: task %s created, polling...", task_id)

        # Poll
        elapsed = 0.0
        while elapsed < timeout_sec:
            await asyncio.sleep(poll_interval_sec)
            elapsed += poll_interval_sec

            status_resp = await client.get(
                f"{_BASE_URL}/tasks/{task_id}",
                headers=_headers(),
            )
            if status_resp.status_code >= 400:
                logger.warning(
                    "Runway: poll %s → %d, retrying", task_id, status_resp.status_code
                )
                continue
            task = status_resp.json()
            status = task.get("status", "UNKNOWN")
            logger.info("Runway: task %s → %s (%.0fs)", task_id, status, elapsed)

            if status in ("SUCCEEDED", "SUCCESS"):
                output_urls = task.get("output") or []
                if not output_urls:
                    raise RunwayError(f"Task {task_id} SUCCEEDED but no output: {task}")
                video_url = output_urls[0]
                out_path = output_dir / f"runway-{uuid.uuid4()}.mp4"

                # Download MP4
                async with httpx.AsyncClient(timeout=120) as dl:
                    r = await dl.get(video_url)
                    r.raise_for_status()
                    out_path.write_bytes(r.content)

                logger.info(
                    "Runway: downloaded %.1f MB → %s",
                    out_path.stat().st_size / 1e6,
                    out_path,
                )
                return str(out_path)

            if status in ("FAILED", "CANCELLED"):
                raise RunwayError(
                    f"Task {task_id} status={status}: {task.get('failure') or task}"
                )

        raise RunwayError(f"Task {task_id} timed out after {timeout_sec}s")


# Short, style-tagged prompts tuned for pro-headshot motion. Keep the subject
# calm and frontal — Runway amplifies motion, so asking for "head turn" can
# produce jittery results; subtle framing + environment motion works best.
STYLE_MOTION_PROMPTS: dict[str, str] = {
    "corporate": (
        "Professional confident posture, subtle eye movement, soft camera push-in, "
        "warm studio lighting, shallow depth of field, cinematic 4K"
    ),
    "startup": (
        "Founder confidence, slight micro-expression shift, natural environmental "
        "light, subtle camera drift, modern office background softly out of focus"
    ),
    "creative": (
        "Creative professional, subtle breathing motion, moody editorial lighting, "
        "slow push-in, rich color grading, textured background"
    ),
    "casual": (
        "Natural candid expression, soft micro-motion, daylight, gentle camera "
        "drift, clean background with shallow depth"
    ),
    "formal": (
        "Executive poise, steady gaze, elegant key light, minimal motion, "
        "formal attire crisp, neutral background"
    ),
    "editorial": (
        "Editorial portrait, cinematic slow motion, moody high-contrast lighting, "
        "fashion-magazine composition, subtle ambient motion"
    ),
    "medical": (
        "Trusted clinical portrait, calm presence, soft clinical lighting, "
        "subtle motion, professional wardrobe, clean background"
    ),
    "default": (
        "Subtle professional motion, natural expression, cinematic studio lighting, "
        "soft camera push-in, shallow depth of field"
    ),
}


def motion_prompt_for(style_key: str | None) -> str:
    """Pick a motion prompt by loose style name (falls back to 'default')."""
    if not style_key:
        return STYLE_MOTION_PROMPTS["default"]
    key = style_key.lower()
    for name, prompt in STYLE_MOTION_PROMPTS.items():
        if name in key:
            return prompt
    return STYLE_MOTION_PROMPTS["default"]


async def image_to_videos_batch(
    image_paths: list[str | Path],
    prompts: list[str] | None = None,
    *,
    duration: int = 5,
    ratio: str = "720:1280",
    model: str = "gen4_turbo",
    concurrency: int = 4,
) -> list[Optional[str]]:
    """Generate videos for many images concurrently.

    Returns one MP4 path per input (or None if that item failed). Order is preserved.
    """
    if prompts is None:
        prompts = [STYLE_MOTION_PROMPTS["default"]] * len(image_paths)
    if len(prompts) != len(image_paths):
        raise ValueError("image_paths and prompts must be the same length")

    sem = asyncio.Semaphore(concurrency)

    async def one(idx: int, img: Any, prompt: str) -> Optional[str]:
        async with sem:
            try:
                return await image_to_video(
                    img, prompt, duration=duration, ratio=ratio, model=model
                )
            except Exception as e:  # noqa: BLE001
                logger.exception("Runway failed for image %d: %s", idx, e)
                return None

    return await asyncio.gather(
        *[one(i, img, p) for i, (img, p) in enumerate(zip(image_paths, prompts))]
    )
