"""Maps Facebook campaigns to AECO products/workspaces."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, String

from aeco.db.base import Base


class CampaignProduct(Base):
    """Associates a Facebook campaign with an AECO product/workspace."""

    __tablename__ = "campaign_products"

    campaign_id = Column(String, primary_key=True)  # Facebook campaign ID
    product_name = Column(String, nullable=False)  # e.g. "Headshot AI"
    workspace_path = Column(String, nullable=True)  # e.g. "/path/to/headshot-studio"
    ad_account_id = Column(String, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
