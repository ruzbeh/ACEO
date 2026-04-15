"""Reel model — a video ad produced by the AECO video harness.

Lifecycle:
    draft   — created, images uploaded, not yet rendered
    rendering — Remotion is rendering the MP4
    rendered — MP4 on disk, not published
    publishing — uploading to FB, creating creative + ad
    published — FB ad created (PAUSED by default; user activates)
    failed   — any step errored; see last_error
"""
import enum
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import JSON, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from aeco.db.base import Base


class ReelStatus(str, enum.Enum):
    DRAFT = "draft"
    RENDERING = "rendering"
    RENDERED = "rendered"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    FAILED = "failed"


class Reel(Base):
    """A video ad: source images + script + rendered MP4 + optional FB ad IDs."""

    __tablename__ = "reels"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(255), default="Untitled reel")

    # Source images (absolute paths under workspace/reels/uploads/*)
    before_image_path: Mapped[str] = mapped_column(Text)
    after_image_paths: Mapped[list] = mapped_column(JSON, default=list)

    # Script copy (renders into the composition)
    headline: Mapped[str] = mapped_column(String(255), default="")
    subheadline: Mapped[str] = mapped_column(String(255), default="")
    cta_text: Mapped[str] = mapped_column(String(255), default="")
    brand: Mapped[str] = mapped_column(String(255), default="headshot-generators.com")
    brief: Mapped[str] = mapped_column(Text, default="")

    composition: Mapped[str] = mapped_column(String(100), default="BeforeAfterReel")

    # Phase 2: Runway image-to-video motion on the after headshots
    use_runway: Mapped[bool] = mapped_column(default=False)
    # {image_path: mp4_path} for after-image → Runway clip. Populated on render.
    runway_clips: Mapped[dict] = mapped_column(JSON, default=dict)

    # Phase 3: ElevenLabs voiceover narration
    use_voiceover: Mapped[bool] = mapped_column(default=False)
    voiceover_text: Mapped[str] = mapped_column(Text, default="")
    voiceover_voice: Mapped[str] = mapped_column(String(100), default="narrator")
    voiceover_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    voiceover_duration_sec: Mapped[Optional[float]] = mapped_column(default=None, nullable=True)

    # Output
    mp4_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    duration_sec: Mapped[Optional[float]] = mapped_column(default=None, nullable=True)

    # FB publishing
    fb_video_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    fb_creative_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    fb_ad_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    fb_ads_manager_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    fb_adset_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    status: Mapped[str] = mapped_column(String(50), default=ReelStatus.DRAFT.value)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    progress_log: Mapped[list] = mapped_column(JSON, default=list)  # list of {ts, stage, message}

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
