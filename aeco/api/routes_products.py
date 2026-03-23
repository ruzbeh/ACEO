"""Product management API routes."""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aeco.db.session import get_session
from aeco.models.product import Product, ProductMetricsSnapshot

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/products", tags=["products"])


# --- Request/Response models ---

class CreateProductRequest(BaseModel):
    name: str
    slug: str
    url: Optional[str] = None
    workspace_path: Optional[str] = None
    fb_pixel_id: Optional[str] = None
    fb_page_id: Optional[str] = None
    fb_campaign_ids: list[str] = []
    funnel_steps: list[dict] = []
    currency: str = "USD"
    pricing_tiers: list[dict] = []


class ProductResponse(BaseModel):
    id: str
    name: str
    slug: str
    url: Optional[str]
    workspace_path: Optional[str]
    fb_pixel_id: Optional[str]
    fb_page_id: Optional[str]
    fb_campaign_ids: list
    funnel_steps: list
    currency: str
    pricing_tiers: list
    created_at: str

    model_config = {"from_attributes": True}


# --- Endpoints ---

@router.get("", response_model=list[ProductResponse])
async def list_products(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Product).order_by(Product.name))
    return [_to_response(p) for p in result.scalars()]


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(product_id: str, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Product).where(Product.id == product_id))
    product = result.scalars().first()
    if not product:
        # Try by slug
        result = await session.execute(select(Product).where(Product.slug == product_id))
        product = result.scalars().first()
    if not product:
        raise HTTPException(404, "Product not found")
    return _to_response(product)


@router.post("", response_model=ProductResponse, status_code=201)
async def create_product(req: CreateProductRequest, session: AsyncSession = Depends(get_session)):
    product = Product(
        name=req.name,
        slug=req.slug,
        url=req.url,
        workspace_path=req.workspace_path,
        fb_pixel_id=req.fb_pixel_id,
        fb_page_id=req.fb_page_id,
        fb_campaign_ids=req.fb_campaign_ids,
        funnel_steps=req.funnel_steps,
        currency=req.currency,
        pricing_tiers=req.pricing_tiers,
    )
    session.add(product)
    await session.commit()
    await session.refresh(product)
    return _to_response(product)


@router.put("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: str, req: CreateProductRequest, session: AsyncSession = Depends(get_session)
):
    result = await session.execute(select(Product).where(Product.id == product_id))
    product = result.scalars().first()
    if not product:
        raise HTTPException(404, "Product not found")
    for field in ["name", "slug", "url", "workspace_path", "fb_pixel_id", "fb_page_id",
                  "fb_campaign_ids", "funnel_steps", "currency", "pricing_tiers"]:
        setattr(product, field, getattr(req, field))
    await session.commit()
    await session.refresh(product)
    return _to_response(product)


@router.get("/{product_id}/metrics")
async def get_product_metrics_history(
    product_id: str, limit: int = 30, session: AsyncSession = Depends(get_session)
):
    """Get metrics snapshot history for a product."""
    result = await session.execute(
        select(ProductMetricsSnapshot)
        .where(ProductMetricsSnapshot.product_id == product_id)
        .order_by(ProductMetricsSnapshot.captured_at.desc())
        .limit(limit)
    )
    snapshots = result.scalars().all()
    return [
        {
            "id": s.id,
            "captured_at": s.captured_at.isoformat(),
            "period": s.period,
            "spend": s.spend,
            "impressions": s.impressions,
            "clicks": s.clicks,
            "leads": s.leads,
            "purchases": s.purchases,
            "revenue": s.revenue,
            "cpm": s.cpm,
            "ctr": s.ctr,
            "cost_per_purchase": s.cost_per_purchase,
            "roas": s.roas,
            "funnel_data": s.funnel_data,
            "dropoffs": s.dropoffs,
        }
        for s in snapshots
    ]


def _to_response(product: Product) -> dict:
    return {
        "id": product.id,
        "name": product.name,
        "slug": product.slug,
        "url": product.url,
        "workspace_path": product.workspace_path,
        "fb_pixel_id": product.fb_pixel_id,
        "fb_page_id": product.fb_page_id,
        "fb_campaign_ids": product.fb_campaign_ids or [],
        "funnel_steps": product.funnel_steps or [],
        "currency": product.currency,
        "pricing_tiers": product.pricing_tiers or [],
        "created_at": product.created_at.isoformat() if product.created_at else "",
    }
