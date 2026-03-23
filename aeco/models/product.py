"""Product model — stores per-product config, funnel, and metrics history.

Each product (Headshot AI, LandingQube, etc.) has its own:
- Workspace path and URL
- Facebook campaign IDs
- Funnel step definitions (pixel events)
- Metrics snapshots over time
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import JSON, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from aeco.db.base import Base


class Product(Base):
    """A product managed by AECO."""

    __tablename__ = "products"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String, unique=True, nullable=False)  # e.g. "headshot-ai"
    url: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # e.g. "https://www.headshot-generators.com"
    workspace_path: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Facebook config
    fb_pixel_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    fb_page_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    fb_campaign_ids: Mapped[Optional[list]] = mapped_column(JSON, default=list)  # linked campaign IDs

    # Funnel definition — list of steps with pixel event mappings
    # Each step: {"name": "...", "key": "...", "alt_keys": [...], "source": "action|metric", "description": "..."}
    funnel_steps: Mapped[Optional[list]] = mapped_column(JSON, default=list)

    # Pricing info (for ROAS calculation)
    currency: Mapped[str] = mapped_column(String, default="USD")
    pricing_tiers: Mapped[Optional[list]] = mapped_column(JSON, default=list)  # [{"name": "Basic", "price": 9}, ...]

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class ProductMetricsSnapshot(Base):
    """Point-in-time metrics snapshot for a product — stored daily/on-demand."""

    __tablename__ = "product_metrics_snapshots"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    product_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    period: Mapped[str] = mapped_column(String, default="7d")  # 7d, 30d, lifetime

    # Raw funnel numbers
    funnel_data: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    # [{"name": "Ad Impression", "value": 24943}, {"name": "Ad Click", "value": 945}, ...]

    # Summary metrics
    spend: Mapped[float] = mapped_column(Float, default=0.0)
    impressions: Mapped[int] = mapped_column(Integer, default=0)
    clicks: Mapped[int] = mapped_column(Integer, default=0)
    leads: Mapped[int] = mapped_column(Integer, default=0)
    purchases: Mapped[int] = mapped_column(Integer, default=0)
    revenue: Mapped[float] = mapped_column(Float, default=0.0)
    cpm: Mapped[float] = mapped_column(Float, default=0.0)
    ctr: Mapped[float] = mapped_column(Float, default=0.0)
    cost_per_purchase: Mapped[float] = mapped_column(Float, default=0.0)
    roas: Mapped[float] = mapped_column(Float, default=0.0)

    # Drop-off analysis
    dropoffs: Mapped[Optional[list]] = mapped_column(JSON, default=list)
