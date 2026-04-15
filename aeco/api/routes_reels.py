"""Reels API: create, render, list, publish video ads.

POST   /api/reels/images       — upload a source image, returns {path, url}
POST   /api/reels               — create a draft reel + kick off render (async)
GET    /api/reels               — list all reels (newest first)
GET    /api/reels/{id}          — get one reel (status, progress_log, mp4_url)
POST   /api/reels/{id}/publish  — upload the rendered MP4 to FB as PAUSED ad
DELETE /api/reels/{id}          — soft remove from UI (keeps files)

The actual render + publish pipeline lives in aeco/tools/video/{composer,publisher}.
This module just orchestrates + persists state + emits WS progress.
"""
from __future__ import annotations

import asyncio
import base64
import logging
import mimetypes
import shutil
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aeco.db.session import async_session_factory
from aeco.models.reel import Reel, ReelStatus
from aeco.tools.video.composer import render_reel
from aeco.tools.video.publisher import create_video_ad, upload_video_to_facebook
from aeco.tools.video.runway import (
    RunwayError,
    image_to_videos_batch,
    motion_prompt_for,
)
from aeco.tools.video.script_writer import ReelScript, write_scripts

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/reels", tags=["reels"])

# Storage — under the AECO repo, not the headshot-studio workspace
_AECO_ROOT = Path(__file__).resolve().parents[2]
_REELS_DIR = _AECO_ROOT / "workspace" / "reels"
_UPLOADS_DIR = _REELS_DIR / "uploads"
_OUTPUT_DIR = _REELS_DIR / "output"
_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Defaults that match the active FB ad + winning adset
DEFAULT_ADSET_ID = "120243930512770566"  # US Broad — Registration — 1700/day
DEFAULT_PAGE_ID = "1091699287351335"
DEFAULT_LINK = "https://www.headshot-generators.com/lp"

# Event bus hook (set from main.py if available). Emits {reel_id, stage, message}.
_event_bus = None


def set_dependencies(event_bus=None):
    global _event_bus
    _event_bus = event_bus


def _emit(reel_id: str, stage: str, message: str) -> None:
    if _event_bus is not None:
        try:
            _event_bus.emit("reel.progress", {"reel_id": reel_id, "stage": stage, "message": message})
        except Exception:  # don't let WS failures block the render
            logger.exception("event_bus.emit failed")


async def _append_log(session: AsyncSession, reel: Reel, stage: str, message: str) -> None:
    """Append a structured entry to the reel's progress_log and persist."""
    logger.info("reel=%s %s: %s", reel.id, stage, message)
    log = list(reel.progress_log or [])
    log.append({"ts": datetime.now(timezone.utc).isoformat(), "stage": stage, "message": message})
    reel.progress_log = log
    await session.flush()
    await session.commit()
    _emit(str(reel.id), stage, message)


def _to_data_uri(path: Path) -> str:
    mime, _ = mimetypes.guess_type(str(path))
    mime = mime or "image/jpeg"
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{data}"


# ──────────────────────────────────────────────────────────────────────────────
# Schemas
# ──────────────────────────────────────────────────────────────────────────────


class ImageUploadResponse(BaseModel):
    id: str
    path: str   # absolute path on disk
    url: str    # URL the UI can use (/media/reels/uploads/<file>)


class CreateReelRequest(BaseModel):
    title: Optional[str] = None
    before_image_path: str
    after_image_paths: List[str] = Field(..., min_length=3, max_length=6)
    headline: Optional[str] = None
    subheadline: Optional[str] = None
    cta_text: Optional[str] = None
    brand: Optional[str] = None
    brief: Optional[str] = None
    composition: str = "BeforeAfterReel"
    auto_script: bool = False  # if true, LLM-generate script from brief
    use_runway: bool = False  # Phase 2: run each after image through Runway img2vid first


class PublishRequest(BaseModel):
    adset_id: Optional[str] = None
    page_id: Optional[str] = None
    link: Optional[str] = None


class ReelResponse(BaseModel):
    id: str
    title: str
    status: str
    headline: str
    subheadline: str
    cta_text: str
    brand: str
    before_image_url: Optional[str] = None
    after_image_urls: List[str] = []
    mp4_url: Optional[str] = None
    duration_sec: Optional[float] = None
    use_runway: bool = False
    fb_ad_id: Optional[str] = None
    fb_ads_manager_url: Optional[str] = None
    fb_adset_id: Optional[str] = None
    progress_log: list = []
    last_error: Optional[str] = None
    created_at: str
    updated_at: str


def _abs_to_upload_url(abs_path: str) -> Optional[str]:
    p = Path(abs_path)
    try:
        rel = p.relative_to(_REELS_DIR)
    except ValueError:
        return None
    return f"/media/reels/{rel.as_posix()}"


def _to_response(r: Reel) -> ReelResponse:
    return ReelResponse(
        id=str(r.id),
        title=r.title,
        status=r.status,
        headline=r.headline,
        subheadline=r.subheadline,
        cta_text=r.cta_text,
        brand=r.brand,
        before_image_url=_abs_to_upload_url(r.before_image_path) if r.before_image_path else None,
        after_image_urls=[u for u in (_abs_to_upload_url(p) for p in (r.after_image_paths or [])) if u],
        mp4_url=_abs_to_upload_url(r.mp4_path) if r.mp4_path else None,
        duration_sec=r.duration_sec,
        use_runway=bool(r.use_runway),
        fb_ad_id=r.fb_ad_id,
        fb_ads_manager_url=r.fb_ads_manager_url,
        fb_adset_id=r.fb_adset_id,
        progress_log=r.progress_log or [],
        last_error=r.last_error,
        created_at=r.created_at.isoformat() if r.created_at else "",
        updated_at=r.updated_at.isoformat() if r.updated_at else "",
    )


# ──────────────────────────────────────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────────────────────────────────────


@router.post("/images", response_model=ImageUploadResponse)
async def upload_image(file: UploadFile = File(...)):
    """Accept a single image and store it under workspace/reels/uploads/."""
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")
    ext = Path(file.filename or "img.jpg").suffix or ".jpg"
    image_id = str(uuid.uuid4())
    dst = _UPLOADS_DIR / f"{image_id}{ext.lower()}"
    content = await file.read()
    dst.write_bytes(content)
    logger.info("Saved reel upload %s (%d bytes)", dst, len(content))
    return ImageUploadResponse(id=image_id, path=str(dst), url=_abs_to_upload_url(str(dst)) or "")


@router.post("", response_model=ReelResponse, status_code=202)
async def create_reel(req: CreateReelRequest):
    """Create a draft reel + kick off rendering in the background."""
    # Validate image paths are inside the uploads dir (prevent path traversal)
    before = Path(req.before_image_path).resolve()
    afters = [Path(p).resolve() for p in req.after_image_paths]
    uploads = _UPLOADS_DIR.resolve()
    if not str(before).startswith(str(uploads)) or not all(
        str(a).startswith(str(uploads)) for a in afters
    ):
        raise HTTPException(status_code=400, detail="Image paths must be inside workspace/reels/uploads")
    if not before.exists() or not all(a.exists() for a in afters):
        raise HTTPException(status_code=400, detail="One or more image files not found on disk")

    # If auto_script requested, generate one now; else use provided (or defaults)
    if req.auto_script and req.brief:
        try:
            scripts = await write_scripts(brief=req.brief, n=1)
            script = scripts[0]
        except Exception:
            logger.exception("write_scripts failed; falling back to defaults")
            script = ReelScript(
                headline="8 Pro Headshots in 2 Minutes",
                subheadline="$19 · Money-back guarantee",
                cta_text="Try free at headshot-generators.com",
            )
    else:
        script = ReelScript(
            headline=req.headline or "8 Pro Headshots in 2 Minutes",
            subheadline=req.subheadline or "$19 · Money-back guarantee",
            cta_text=req.cta_text or "Try free at headshot-generators.com",
            brand=req.brand or "headshot-generators.com",
        )

    async with async_session_factory() as session:
        reel = Reel(
            id=uuid.uuid4(),
            title=req.title or script.headline,
            before_image_path=str(before),
            after_image_paths=[str(a) for a in afters],
            headline=script.headline,
            subheadline=script.subheadline,
            cta_text=script.cta_text,
            brand=script.brand,
            brief=req.brief or "",
            composition=req.composition,
            status=ReelStatus.DRAFT.value,
            use_runway=bool(req.use_runway),
            runway_clips={},
            progress_log=[],
        )
        session.add(reel)
        await session.commit()
        await session.refresh(reel)
        response = _to_response(reel)

    # Fire-and-forget the render
    asyncio.create_task(_render_task(reel.id))
    return response


async def _render_task(reel_id: uuid.UUID) -> None:
    """Background: render the reel, update status, emit progress.

    If the reel has use_runway=True, first generate per-image motion clips
    via Runway Gen-4 Turbo, then feed those videos (as {type: "video", src})
    into the Remotion composition. On ANY Runway failure we fall back to
    Ken Burns so the user still gets a reel.
    """
    try:
        async with async_session_factory() as session:
            r = await session.get(Reel, reel_id)
            if r is None:
                logger.error("reel %s vanished before render", reel_id)
                return
            r.status = ReelStatus.RENDERING.value
            await _append_log(session, r, "render.start", "Preparing reel")

            before_uri = _to_data_uri(Path(r.before_image_path))
            after_items: list = []

            if r.use_runway:
                await _append_log(
                    session,
                    r,
                    "runway.start",
                    f"Generating {len(r.after_image_paths)} motion clips via Runway Gen-4 Turbo…",
                )
                prompts = [motion_prompt_for(None)] * len(r.after_image_paths)
                try:
                    results = await image_to_videos_batch(
                        r.after_image_paths,
                        prompts,
                        duration=5,
                        ratio="720:1280",
                        concurrency=3,
                    )
                except RunwayError as e:
                    await _append_log(
                        session, r, "runway.failed", f"{e} — falling back to Ken Burns"
                    )
                    results = [None] * len(r.after_image_paths)
                except Exception as e:  # noqa: BLE001
                    await _append_log(
                        session, r, "runway.failed", f"Unexpected error: {e} — falling back"
                    )
                    results = [None] * len(r.after_image_paths)

                clips_map: dict[str, str] = {}
                for original, mp4 in zip(r.after_image_paths, results):
                    if mp4:
                        clips_map[original] = mp4
                        # URL served via /media/reels/runway/*
                        url = _abs_to_upload_url(mp4)
                        after_items.append(
                            {"type": "video", "src": url or mp4}
                        )
                    else:
                        # Fallback to still image for that slot
                        after_items.append(
                            {"type": "image", "src": _to_data_uri(Path(original))}
                        )
                r.runway_clips = clips_map
                await _append_log(
                    session,
                    r,
                    "runway.done",
                    f"Got {sum(1 for v in results if v)}/{len(results)} Runway clips",
                )
            else:
                # Plain Ken Burns on stills
                after_items = [
                    {"type": "image", "src": _to_data_uri(Path(p))}
                    for p in r.after_image_paths
                ]

            await _append_log(session, r, "remotion.start", "Bundling Remotion composition")
            props = {
                "beforeImage": before_uri,
                "afterImages": after_items,
                "headline": r.headline,
                "subheadline": r.subheadline,
                "ctaText": r.cta_text,
                "brand": r.brand,
            }
            output_path = _OUTPUT_DIR / f"{r.id}.mp4"

            try:
                rendered = await render_reel(
                    composition=r.composition or "BeforeAfterReel",
                    props=props,
                    output_path=str(output_path),
                )
            except Exception as e:
                r.status = ReelStatus.FAILED.value
                r.last_error = f"render failed: {e}"
                await _append_log(session, r, "render.failed", r.last_error)
                return

            r.mp4_path = rendered.path
            r.duration_sec = rendered.duration_sec
            r.status = ReelStatus.RENDERED.value
            await _append_log(
                session,
                r,
                "render.done",
                f"Rendered {rendered.duration_sec:.1f}s MP4" if rendered.duration_sec else "Rendered",
            )
    except Exception:
        logger.exception("reel render task crashed for %s", reel_id)


@router.get("", response_model=List[ReelResponse])
async def list_reels():
    async with async_session_factory() as session:
        rows = (await session.execute(select(Reel).order_by(Reel.created_at.desc()))).scalars().all()
        return [_to_response(r) for r in rows]


@router.get("/{reel_id}", response_model=ReelResponse)
async def get_reel(reel_id: uuid.UUID):
    async with async_session_factory() as session:
        r = await session.get(Reel, reel_id)
        if r is None:
            raise HTTPException(status_code=404, detail="Reel not found")
        return _to_response(r)


@router.post("/{reel_id}/publish", response_model=ReelResponse)
async def publish_reel(reel_id: uuid.UUID, req: PublishRequest):
    """Upload the rendered MP4 to FB as a PAUSED video ad."""
    async with async_session_factory() as session:
        r = await session.get(Reel, reel_id)
        if r is None:
            raise HTTPException(status_code=404, detail="Reel not found")
        if r.status != ReelStatus.RENDERED.value:
            raise HTTPException(
                status_code=409,
                detail=f"Reel must be RENDERED to publish (current status: {r.status})",
            )
        if not r.mp4_path or not Path(r.mp4_path).exists():
            raise HTTPException(status_code=500, detail="MP4 file missing on disk")

        r.status = ReelStatus.PUBLISHING.value
        adset_id = req.adset_id or DEFAULT_ADSET_ID
        page_id = req.page_id or DEFAULT_PAGE_ID
        link = req.link or DEFAULT_LINK
        r.fb_adset_id = adset_id
        await _append_log(session, r, "publish.upload", f"Uploading MP4 to FB ad account")

        try:
            upload = await upload_video_to_facebook(r.mp4_path, name=f"AECO Reel · {r.headline}")
            r.fb_video_id = upload.get("id")
            await _append_log(
                session, r, "publish.uploaded", f"FB video ready (id={r.fb_video_id})"
            )

            message = (
                "Your LinkedIn photo is the first thing recruiters see.\n\n"
                "Upload a selfie. Get 8 studio-quality headshots in 2 minutes — for $19.\n"
                "→ Free preview. Money-back guarantee."
            )
            ad = await create_video_ad(
                video_id=r.fb_video_id,
                adset_id=adset_id,
                page_id=page_id,
                ad_name=f"Reel · {r.headline[:40]}",
                message=message,
                headline=r.headline,
                description=r.subheadline,
                link=link,
            )
            r.fb_creative_id = ad["creative_id"]
            r.fb_ad_id = ad["ad_id"]
            r.fb_ads_manager_url = ad["ads_manager_url"]
            r.status = ReelStatus.PUBLISHED.value
            await _append_log(
                session, r, "publish.done", f"Created PAUSED ad {r.fb_ad_id}"
            )
        except Exception as e:
            r.status = ReelStatus.FAILED.value
            r.last_error = f"publish failed: {e}"
            await _append_log(session, r, "publish.failed", r.last_error)
            logger.exception("publish_reel failed for %s", reel_id)
            raise HTTPException(status_code=502, detail=r.last_error) from e

        return _to_response(r)
