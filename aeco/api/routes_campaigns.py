"""Campaign Manager API: monitor, optimize, and generate creatives for Facebook ads.

POST /api/campaigns/monitor/start — Start scheduled campaign monitoring
POST /api/campaigns/monitor/stop — Stop monitoring
GET  /api/campaigns/monitor/status — Current monitor state
GET  /api/campaigns/report — Latest campaign report (account health + creative analysis)
GET  /api/campaigns/metrics — Full-funnel product metrics (spend → revenue)
POST /api/campaigns/optimize — One-shot: run campaign_manager agent
POST /api/campaigns/generate-creatives — Generate ad copy suggestions
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections import deque
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, distinct

from aeco.config import settings
from aeco.models.campaign_product import CampaignProduct
from aeco.db.session import async_session_factory

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/campaigns", tags=["campaigns"])

# Set by main.py
_registry = None
_audit_logger = None
_scheduler = None

# In-memory state
_monitor_active = False
_monitor_job_id: str | None = None
_reports: deque[dict] = deque(maxlen=24)
_optimize_tasks: Dict[str, dict] = {}


def set_campaign_deps(registry, audit_logger, scheduler):
    global _registry, _audit_logger, _scheduler
    _registry = registry
    _audit_logger = audit_logger
    _scheduler = scheduler


# --- Models ---

class GenerateCreativesRequest(BaseModel):
    product: str = Field(default="AI headshot generator for professionals", description="Product description")
    audience: str = Field(default="US professionals, LinkedIn users, job seekers", description="Target audience")
    style: str = Field(default="direct_response", description="Style: direct_response, social_proof, urgency, benefit_led, problem_agitation")
    count: int = Field(default=5, ge=1, le=10, description="Number of variations")


class CreateAdRequest(BaseModel):
    headline: str = Field(..., description="Ad headline")
    primary_text: str = Field(..., description="Ad primary text / message")
    description: str = Field(default="", description="Ad description")
    cta_type: str = Field(default="SHOP_NOW", description="Call-to-action type")
    link: str = Field(default="https://www.headshot-generators.com", description="Destination URL")
    product_name: str = Field(default="Headshot AI", description="Product this ad belongs to")


# --- Monitor endpoints ---

@router.post("/monitor/start")
async def start_monitor():
    """Start scheduled campaign monitoring (every 4 hours)."""
    global _monitor_active, _monitor_job_id

    if _scheduler is None:
        raise HTTPException(status_code=503, detail="Scheduler not initialized")
    if _monitor_active:
        return {"status": "already_running", "job_id": _monitor_job_id}

    job = _scheduler.add_job(
        name="campaign_monitor",
        cron_expression="0 */4 * * *",  # Every 4 hours
        callback=_run_monitor_check,
    )
    _monitor_job_id = job.job_id
    _monitor_active = True

    # Run immediately on start
    asyncio.create_task(_run_monitor_check())

    logger.info(f"Campaign monitor started (job_id={job.job_id})")
    return {"status": "started", "job_id": job.job_id, "schedule": "every 4 hours"}


@router.post("/monitor/stop")
async def stop_monitor():
    """Stop campaign monitoring."""
    global _monitor_active, _monitor_job_id

    if not _monitor_active:
        return {"status": "not_running"}

    if _scheduler and _monitor_job_id:
        _scheduler.remove_job(_monitor_job_id)

    _monitor_active = False
    _monitor_job_id = None
    logger.info("Campaign monitor stopped")
    return {"status": "stopped"}


@router.get("/monitor/status")
async def monitor_status():
    """Get current monitor state."""
    last_report = _reports[-1] if _reports else None
    return {
        "active": _monitor_active,
        "job_id": _monitor_job_id,
        "last_check": last_report.get("timestamp") if last_report else None,
        "next_check": None,  # TODO: calculate from scheduler
        "reports_count": len(_reports),
        "last_report_summary": last_report.get("summary") if last_report else None,
    }


# --- Product detection helpers ---

# Known product prefixes for auto-detection from campaign names.
_PRODUCT_PREFIXES = [
    "Headshot AI",
    "LandingQube",
    "Collagen",
]


def _detect_product_from_name(campaign_name: str) -> str | None:
    """Try to detect a product name from a campaign/ad name."""
    if not campaign_name:
        return None
    name_lower = campaign_name.lower()
    for prefix in _PRODUCT_PREFIXES:
        if prefix.lower() in name_lower:
            return prefix
    return None


async def _get_product_campaign_ids(product: str, ad_account: str) -> set[str]:
    """Get campaign IDs mapped to a product from the database."""
    async with async_session_factory() as session:
        result = await session.execute(
            select(CampaignProduct.campaign_id).where(
                CampaignProduct.product_name == product,
                CampaignProduct.ad_account_id == ad_account,
            )
        )
        return {row[0] for row in result.fetchall()}


async def _save_product_mapping(
    campaign_id: str, product_name: str, ad_account_id: str, workspace_path: str = "",
) -> None:
    """Save a campaign-to-product mapping (upsert)."""
    async with async_session_factory() as session:
        existing = await session.get(CampaignProduct, campaign_id)
        if existing is None:
            session.add(CampaignProduct(
                campaign_id=campaign_id,
                product_name=product_name,
                ad_account_id=ad_account_id,
                workspace_path=workspace_path,
            ))
            await session.commit()


async def _auto_detect_and_save(
    ads_raw: list, ad_account: str,
) -> dict[str, str]:
    """Auto-detect products from ad/campaign names and persist mappings.

    Returns a dict mapping campaign_id -> product_name for all detected items.
    """
    detected: dict[str, str] = {}
    for ad in ads_raw:
        ad_name = ad.get("name", "")
        campaign_id = ad.get("campaign_id", "")
        if not campaign_id:
            continue
        product = _detect_product_from_name(ad_name)
        if product and campaign_id not in detected:
            detected[campaign_id] = product
            await _save_product_mapping(campaign_id, product, ad_account)
    return detected


# --- Product Metrics endpoint ---

def _mock_product_metrics(product: str | None, period: str) -> dict:
    """Return realistic mock funnel metrics for Headshot AI."""
    return {
        "product": product or "All Products",
        "period": period,
        "funnel": {
            "impressions": 24943,
            "reach": 18720,
            "clicks": 1102,
            "link_clicks": 945,
            "landing_page_views": 619,
            "leads": 47,
            "add_to_cart": 12,
            "initiate_checkout": 5,
            "purchases": 0,
            "revenue": 0,
        },
        "rates": {
            "click_through_rate": 3.79,
            "landing_rate": 65.5,
            "lead_rate": 7.59,
            "checkout_rate": 0.81,
            "purchase_rate": 0,
            "overall_conversion_rate": 0,
        },
        "economics": {
            "spend": 187.43,
            "cpm": 7.51,
            "cpc": 0.17,
            "cost_per_link_click": 0.20,
            "cost_per_landing_view": 0.30,
            "cost_per_lead": 3.99,
            "cost_per_purchase": 0,
            "roas": 0,
            "revenue": 0,
            "profit": -187.43,
        },
        "dropoffs": [
            {"from": "Impressions", "to": "Link Clicks", "drop_percent": 96.2, "lost": 23998, "severity": "critical"},
            {"from": "Link Clicks", "to": "Landing Views", "drop_percent": 34.5, "lost": 326, "severity": "ok"},
            {"from": "Landing Views", "to": "Checkout Initiated", "drop_percent": 99.2, "lost": 614, "severity": "critical"},
            {"from": "Checkout Initiated", "to": "Purchase", "drop_percent": 100.0, "lost": 5, "severity": "critical"},
        ],
    }


def _mock_campaign_breakdown_metrics(product: str | None, period: str) -> dict:
    """Return mock per-campaign funnel breakdown with 2-3 campaigns."""
    campaigns = [
        {
            "campaign_id": "120243888605780566",
            "campaign_name": f"{product or 'Headshot AI'} — US Conversions — March 2026",
            "status": "ACTIVE",
            "funnel": {
                "impressions": 18200, "reach": 14100, "clicks": 820,
                "link_clicks": 710, "landing_page_views": 480,
                "leads": 38, "add_to_cart": 9, "initiate_checkout": 4,
                "purchases": 0, "revenue": 0,
            },
            "rates": {
                "click_through_rate": 3.90, "landing_rate": 67.6,
                "lead_rate": 7.92, "checkout_rate": 0.83,
                "purchase_rate": 0, "overall_conversion_rate": 0,
            },
            "economics": {
                "spend": 142.10, "cpm": 7.81, "cpc": 0.17,
                "cost_per_link_click": 0.20, "cost_per_landing_view": 0.30,
                "cost_per_lead": 3.74, "cost_per_purchase": 0,
                "roas": 0, "revenue": 0, "profit": -142.10,
            },
            "dropoffs": [
                {"from": "Impressions", "to": "Link Clicks", "drop_percent": 96.1, "lost": 17490, "severity": "critical"},
                {"from": "Link Clicks", "to": "Landing Views", "drop_percent": 32.4, "lost": 230, "severity": "ok"},
                {"from": "Landing Views", "to": "Checkout Initiated", "drop_percent": 99.2, "lost": 476, "severity": "critical"},
                {"from": "Checkout Initiated", "to": "Purchase", "drop_percent": 100.0, "lost": 4, "severity": "critical"},
            ],
        },
        {
            "campaign_id": "120243169905460566",
            "campaign_name": f"First {product or 'Headshot AI'}",
            "status": "PAUSED",
            "funnel": {
                "impressions": 5200, "reach": 3800, "clicks": 210,
                "link_clicks": 175, "landing_page_views": 105,
                "leads": 7, "add_to_cart": 2, "initiate_checkout": 1,
                "purchases": 0, "revenue": 0,
            },
            "rates": {
                "click_through_rate": 3.37, "landing_rate": 60.0,
                "lead_rate": 6.67, "checkout_rate": 0.95,
                "purchase_rate": 0, "overall_conversion_rate": 0,
            },
            "economics": {
                "spend": 35.20, "cpm": 6.77, "cpc": 0.17,
                "cost_per_link_click": 0.20, "cost_per_landing_view": 0.34,
                "cost_per_lead": 5.03, "cost_per_purchase": 0,
                "roas": 0, "revenue": 0, "profit": -35.20,
            },
            "dropoffs": [
                {"from": "Impressions", "to": "Link Clicks", "drop_percent": 96.6, "lost": 5025, "severity": "critical"},
                {"from": "Link Clicks", "to": "Landing Views", "drop_percent": 40.0, "lost": 70, "severity": "ok"},
                {"from": "Landing Views", "to": "Checkout Initiated", "drop_percent": 99.0, "lost": 104, "severity": "critical"},
                {"from": "Checkout Initiated", "to": "Purchase", "drop_percent": 100.0, "lost": 1, "severity": "critical"},
            ],
        },
        {
            "campaign_id": "120244002305780566",
            "campaign_name": f"{product or 'Headshot AI'} — Retargeting — April 2026",
            "status": "ACTIVE",
            "funnel": {
                "impressions": 1543, "reach": 820, "clicks": 72,
                "link_clicks": 60, "landing_page_views": 34,
                "leads": 2, "add_to_cart": 1, "initiate_checkout": 0,
                "purchases": 0, "revenue": 0,
            },
            "rates": {
                "click_through_rate": 3.89, "landing_rate": 56.7,
                "lead_rate": 5.88, "checkout_rate": 0,
                "purchase_rate": 0, "overall_conversion_rate": 0,
            },
            "economics": {
                "spend": 10.13, "cpm": 6.57, "cpc": 0.14,
                "cost_per_link_click": 0.17, "cost_per_landing_view": 0.30,
                "cost_per_lead": 5.07, "cost_per_purchase": 0,
                "roas": 0, "revenue": 0, "profit": -10.13,
            },
            "dropoffs": [
                {"from": "Impressions", "to": "Link Clicks", "drop_percent": 96.1, "lost": 1483, "severity": "critical"},
                {"from": "Link Clicks", "to": "Landing Views", "drop_percent": 43.3, "lost": 26, "severity": "ok"},
                {"from": "Landing Views", "to": "Checkout Initiated", "drop_percent": 100.0, "lost": 34, "severity": "critical"},
            ],
        },
    ]
    mock_totals = _mock_product_metrics(product, period)
    return {
        "product": product or "All Products",
        "period": period,
        "breakdown": "campaign",
        "campaigns": campaigns,
        "totals": {
            "funnel": mock_totals["funnel"],
            "rates": mock_totals["rates"],
            "economics": mock_totals["economics"],
            "dropoffs": mock_totals["dropoffs"],
        },
    }


def _build_funnel_from_insights(acct: dict) -> dict:
    """Build funnel, rates, economics, and dropoffs from a single insights row."""
    actions = acct.get("actions", [])
    cost_per = acct.get("cost_per_action_type", [])
    action_values = acct.get("action_values", [])

    def get_action(action_type: str) -> int:
        for a in actions:
            if a.get("action_type") == action_type:
                return int(a.get("value", 0))
        return 0

    def get_cost_per_val(action_type: str) -> float:
        for a in cost_per:
            if a.get("action_type") == action_type:
                return float(a.get("value", 0))
        return 0.0

    def get_value(action_type: str) -> float:
        for a in action_values:
            if a.get("action_type") == action_type:
                return float(a.get("value", 0))
        return 0.0

    spend = float(acct.get("spend", 0))
    impressions = int(acct.get("impressions", 0))
    reach = int(acct.get("reach", 0))
    clicks = int(acct.get("clicks", 0))
    link_clicks = get_action("link_click")
    landing_views = get_action("landing_page_view")
    leads = (
        get_action("lead")
        + get_action("offsite_conversion.fb_pixel_lead")
        + get_action("complete_registration")
        + get_action("offsite_conversion.fb_pixel_complete_registration")
    )
    add_to_cart = get_action("offsite_conversion.fb_pixel_add_to_cart")
    initiate_checkout = get_action("offsite_conversion.fb_pixel_initiate_checkout")
    purchases = get_action("offsite_conversion.fb_pixel_purchase") + get_action("purchase")
    revenue = get_value("offsite_conversion.fb_pixel_purchase") + get_value("purchase")

    funnel = {
        "impressions": impressions, "reach": reach, "clicks": clicks,
        "link_clicks": link_clicks, "landing_page_views": landing_views,
        "leads": leads, "add_to_cart": add_to_cart,
        "initiate_checkout": initiate_checkout,
        "purchases": purchases, "revenue": revenue,
    }

    rates = {
        "click_through_rate": round(link_clicks / impressions * 100, 2) if impressions > 0 else 0,
        "landing_rate": round(landing_views / link_clicks * 100, 2) if link_clicks > 0 else 0,
        "lead_rate": round(leads / landing_views * 100, 2) if landing_views > 0 else 0,
        "checkout_rate": round(initiate_checkout / landing_views * 100, 2) if landing_views > 0 else 0,
        "purchase_rate": round(purchases / initiate_checkout * 100, 2) if initiate_checkout > 0 else 0,
        "overall_conversion_rate": round(purchases / link_clicks * 100, 2) if link_clicks > 0 else 0,
    }

    economics = {
        "spend": spend,
        "cpm": float(acct.get("cpm", 0)),
        "cpc": float(acct.get("cpc", 0)),
        "cost_per_link_click": round(spend / link_clicks, 2) if link_clicks > 0 else 0,
        "cost_per_landing_view": round(spend / landing_views, 2) if landing_views > 0 else 0,
        "cost_per_lead": get_cost_per_val("lead") or (round(spend / leads, 2) if leads > 0 else 0),
        "cost_per_purchase": get_cost_per_val("offsite_conversion.fb_pixel_purchase") or (round(spend / purchases, 2) if purchases > 0 else 0),
        "roas": round(revenue / spend, 2) if spend > 0 else 0,
        "revenue": revenue,
        "profit": round(revenue - spend, 2),
    }

    dropoffs: list[dict] = []
    steps = [
        ("Impressions", impressions),
        ("Link Clicks", link_clicks),
        ("Landing Views", landing_views),
        ("Checkout Initiated", initiate_checkout),
        ("Purchase", purchases),
    ]
    for i in range(1, len(steps)):
        prev_name, prev_val = steps[i - 1]
        curr_name, curr_val = steps[i]
        if prev_val > 0:
            drop_pct = round((1 - curr_val / prev_val) * 100, 1)
            dropoffs.append({
                "from": prev_name, "to": curr_name,
                "drop_percent": drop_pct, "lost": prev_val - curr_val,
                "severity": "critical" if drop_pct > 90 else "warning" if drop_pct > 70 else "ok",
            })

    return {"funnel": funnel, "rates": rates, "economics": economics, "dropoffs": dropoffs}


@router.get("/metrics")
async def get_product_metrics(
    product: Optional[str] = None,
    period: str = "7d",
    breakdown: Optional[str] = None,
):
    """Get full-funnel metrics for a product, optionally broken down by campaign."""
    import httpx

    token = settings.facebook_access_token
    ad_account_raw = settings.facebook_ad_account_id or ""
    ad_account = ad_account_raw if ad_account_raw.startswith("act_") else f"act_{ad_account_raw}"

    if not token or not ad_account_raw:
        logger.warning("Facebook credentials missing — returning mock product metrics")
        if breakdown == "campaign":
            return _mock_campaign_breakdown_metrics(product, period)
        return _mock_product_metrics(product, period)

    # Map period parameter to Facebook date_preset
    period_map = {"7d": "last_7d", "30d": "last_30d", "lifetime": "maximum"}
    date_preset = period_map.get(period, "last_7d")

    # --- Campaign breakdown mode ---
    if breakdown == "campaign":
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                # Fetch campaigns with inline insights
                fields = (
                    "id,name,status,"
                    f"insights.date_preset({date_preset})"
                    "{spend,impressions,reach,clicks,cpm,ctr,cpc,actions,cost_per_action_type,action_values}"
                )
                params: dict[str, Any] = {
                    "fields": fields,
                    "access_token": token,
                    "limit": 100,
                }
                resp = await client.get(
                    f"https://graph.facebook.com/v21.0/{ad_account}/campaigns",
                    params=params,
                )
                resp_json = resp.json()
                campaigns_raw = resp_json.get("data", [])

            # Filter by product name prefix if set
            if product:
                product_lower = product.lower()
                campaigns_raw = [
                    c for c in campaigns_raw
                    if product_lower in c.get("name", "").lower()
                ]

            campaign_results: list[dict] = []
            for camp in campaigns_raw:
                insights_data = camp.get("insights", {}).get("data", [])
                acct_row = insights_data[0] if insights_data else {}
                built = _build_funnel_from_insights(acct_row)
                campaign_results.append({
                    "campaign_id": camp.get("id", ""),
                    "campaign_name": camp.get("name", ""),
                    "status": camp.get("status", "UNKNOWN"),
                    **built,
                })

            # Build totals from account-level insights (same as non-breakdown)
            async with httpx.AsyncClient(timeout=30) as client:
                acct_params: dict[str, Any] = {
                    "fields": "spend,impressions,reach,clicks,cpm,ctr,cpc,actions,cost_per_action_type,action_values",
                    "date_preset": date_preset,
                    "access_token": token,
                }
                if product:
                    acct_params["filtering"] = json.dumps([
                        {"field": "campaign.name", "operator": "CONTAIN", "value": product}
                    ])
                resp = await client.get(
                    f"https://graph.facebook.com/v21.0/{ad_account}/insights",
                    params=acct_params,
                )
                data = resp.json().get("data", [{}])
                acct_totals = data[0] if data else {}
            totals = _build_funnel_from_insights(acct_totals)

            return {
                "product": product or "All Products",
                "period": period,
                "breakdown": "campaign",
                "campaigns": campaign_results,
                "totals": totals,
            }

        except Exception as e:
            logger.error(f"Campaign breakdown fetch failed, falling back to mock: {e}")
            return _mock_campaign_breakdown_metrics(product, period)

    # --- Account-level mode (default, backwards compatible) ---
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            params: dict[str, Any] = {
                "fields": "spend,impressions,reach,clicks,cpm,ctr,cpc,actions,cost_per_action_type,action_values",
                "date_preset": date_preset,
                "access_token": token,
            }
            if product:
                params["filtering"] = json.dumps([
                    {"field": "campaign.name", "operator": "CONTAIN", "value": product}
                ])
            resp = await client.get(
                f"https://graph.facebook.com/v21.0/{ad_account}/insights",
                params=params,
            )
            data = resp.json().get("data", [{}])
            acct = data[0] if data else {}

        built = _build_funnel_from_insights(acct)

        return {
            "product": product or "All Products",
            "period": period,
            **built,
        }

    except Exception as e:
        logger.error(f"Product metrics fetch failed, falling back to mock: {e}")
        return _mock_product_metrics(product, period)


# --- Report endpoint ---

def _extract_conversions(actions: list | None) -> int:
    """Count ONLY purchase conversions — not leads, likes, or other actions."""
    if not actions:
        return 0
    purchase_types = {"offsite_conversion.fb_pixel_purchase", "purchase"}
    return sum(int(a.get("value", 0)) for a in actions if a.get("action_type") in purchase_types)


def _extract_cost_per_conversion(cost_per_action: list | None) -> float:
    """Get cost per purchase from cost_per_action_type list."""
    if not cost_per_action:
        return 0.0
    purchase_types = {"offsite_conversion.fb_pixel_purchase", "purchase"}
    for entry in cost_per_action:
        if entry.get("action_type") in purchase_types:
            return float(entry.get("value", 0))
    return 0.0


def _grade_creative(ctr: float, cpm: float, conversions: int) -> str:
    """Assign a performance grade based on CTR, CPM, and conversions."""
    score = 0
    if ctr >= 2.0:
        score += 3
    elif ctr >= 1.0:
        score += 2
    elif ctr >= 0.5:
        score += 1
    if cpm <= 10:
        score += 2
    elif cpm <= 20:
        score += 1
    if conversions >= 5:
        score += 3
    elif conversions >= 1:
        score += 2
    if score >= 7:
        return "A"
    if score >= 5:
        return "B"
    if score >= 3:
        return "C"
    return "F"


def _summarize_targeting(targeting: dict | None) -> str:
    """Build a human-readable targeting summary string."""
    if not targeting:
        return "Advantage+ (broad)"
    parts = []
    geo = targeting.get("geo_locations", {})
    countries = geo.get("countries", [])
    if countries:
        parts.append(", ".join(countries))
    age_min = targeting.get("age_min")
    age_max = targeting.get("age_max")
    if age_min or age_max:
        parts.append(f"{age_min or 18}-{age_max or 65}")
    if targeting.get("flexible_spec"):
        parts.append("Interest targeting")
    if targeting.get("publisher_platforms"):
        parts.append(", ".join(targeting["publisher_platforms"]))
    if not parts:
        parts.append("Advantage+ (broad)")
    return ", ".join(parts)


def _generate_recommendations(health: dict, creatives: list, targeting: list) -> list[dict]:
    """Generate actionable recommendations based on report data."""
    recs = []

    # High CPM → suggest broader targeting or new creatives
    cpm = health.get("cpm", 0)
    if cpm > 30:
        recs.append({
            "id": "high_cpm",
            "text": f"CPM is ${cpm:.0f} — too high. Consider broadening targeting or testing new creatives.",
            "action_type": "initiative",
            "action_label": "Create new ad variants",
            "action_payload": {
                "title": "Reduce CPM by testing new ad creatives",
                "goal": f"Current CPM is ${cpm:.0f} which is too high. Generate and test 3 new ad creative variants with different angles (social proof, urgency, benefit-led) to find one that resonates better with the audience.",
            },
        })
    elif cpm > 20:
        recs.append({
            "id": "elevated_cpm",
            "text": f"CPM is ${cpm:.2f} — consider narrowing audience or switching placements.",
            "action_type": "initiative",
            "action_label": "Optimize placements",
            "action_payload": {
                "title": "Reduce CPM by optimizing ad placements",
                "goal": f"CPM is ${cpm:.2f} which is above the $20 threshold. Review placement performance and narrow to top-performing placements.",
            },
        })

    # Low CTR → suggest new copy
    ctr = health.get("ctr", 0)
    if ctr < 1.0 and health.get("impressions", 0) > 500:
        recs.append({
            "id": "low_ctr",
            "text": f"CTR is {ctr:.2f}% — below 1%. Ad copy isn't compelling enough.",
            "action_type": "initiative",
            "action_label": "Generate better ad copy",
            "action_payload": {
                "title": "Improve ad copy to increase CTR",
                "goal": f"CTR is only {ctr:.2f}%. Generate new ad copy variants focusing on stronger hooks, clearer value props, and more urgency.",
            },
        })

    # Frequency > 3 → ad fatigue
    freq = health.get("frequency", 0)
    if freq > 3:
        recs.append({
            "id": "ad_fatigue",
            "text": f"Frequency is {freq:.1f} — audience is seeing ads too often. Refresh creatives.",
            "action_type": "initiative",
            "action_label": "Refresh creatives",
            "action_payload": {
                "title": "Refresh ad creatives to combat ad fatigue",
                "goal": f"Ad frequency is {freq:.1f} which means people see the same ad too many times. Create fresh creative variants.",
            },
        })

    # Underperforming ads → pause them
    for c in creatives:
        if c.get("performance_grade") == "F" and c.get("status") == "ACTIVE":
            recs.append({
                "id": f"pause_{c['ad_id']}",
                "text": f"Ad '{c.get('ad_name', c['ad_id'])}' is grade F — wasting budget.",
                "action_type": "instant",
                "action_label": "Pause this ad",
                "action_payload": {
                    "action": "pause_ad",
                    "ad_id": c["ad_id"],
                },
            })

    # Good ads with low budget → suggest increase
    for t in targeting:
        if t.get("conversions", 0) > 0 and t.get("daily_budget", 0) < 2000:
            recs.append({
                "id": f"increase_budget_{t['ad_set_id']}",
                "text": f"Ad set '{t.get('ad_set_name', '')}' is converting. Consider increasing budget.",
                "action_type": "instant",
                "action_label": "Increase to $25/day",
                "action_payload": {
                    "action": "update_budget",
                    "ad_set_id": t["ad_set_id"],
                    "new_daily_budget": 210000,
                },
            })

    # No conversions at all
    conversions = health.get("conversions", 0)
    spend = health.get("spend_7d", 0)
    if conversions == 0 and spend > 10:
        recs.append({
            "id": "zero_conversions",
            "text": f"Spent ${spend:.0f} with zero conversions. Landing page or offer may need work.",
            "action_type": "initiative",
            "action_label": "Audit landing page",
            "action_payload": {
                "title": "Audit and fix landing page conversion",
                "goal": "Zero conversions despite ad spend. Review the landing page for trust signals, clear CTA, page speed, and checkout flow issues.",
            },
        })

    # Performing well → scale
    if conversions > 5 and cpm < 20:
        recs.append({
            "id": "performing_well",
            "text": "Campaign is performing well! Consider scaling budget gradually.",
            "action_type": "instant",
            "action_label": "Scale budget 20%",
            "action_payload": {
                "action": "scale_budget",
                "scale_factor": 1.2,
            },
        })

    if not recs:
        recs.append({
            "id": "no_data",
            "text": "Not enough data yet. Let the campaign run for 2-3 days before making changes.",
            "action_type": "none",
            "action_label": "",
            "action_payload": {},
        })

    return recs


def _mock_report() -> dict:
    """Return realistic mock data when Facebook API is unavailable."""
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "is_mock": True,
        "account_health": {
            "spend_7d": 187.43,
            "impressions": 14820,
            "clicks": 312,
            "cpm": 12.65,
            "ctr": 2.11,
            "conversions": 8,
            "cost_per_conversion": 23.43,
            "frequency": 2.4,
            "roas": 3.2,
        },
        "creative_performance": [
            {
                "ad_id": "mock_001",
                "ad_name": "Headshot AI — Professional Look",
                "status": "ACTIVE",
                "creative_body": "Get a studio-quality professional headshot in minutes with AI. No photographer needed.",
                "creative_title": "Professional AI Headshots",
                "image_url": "",
                "targeting_summary": "US, 25-65, Interest targeting",
                "ad_set_name": "US Professionals Broad",
                "spend": 94.21,
                "impressions": 7410,
                "clicks": 187,
                "ctr": 2.52,
                "cpm": 12.71,
                "conversions": 5,
                "cost_per_conversion": 18.84,
                "performance_grade": "A",
            },
            {
                "ad_id": "mock_002",
                "ad_name": "Headshot AI — LinkedIn Ready",
                "status": "ACTIVE",
                "creative_body": "Upgrade your LinkedIn profile with an AI-generated headshot that looks like it was taken in a studio.",
                "creative_title": "LinkedIn-Ready Headshots",
                "image_url": "",
                "targeting_summary": "US, 25-55, Interest targeting",
                "ad_set_name": "LinkedIn Job Seekers",
                "spend": 62.80,
                "impressions": 5100,
                "clicks": 89,
                "ctr": 1.75,
                "cpm": 12.31,
                "conversions": 3,
                "cost_per_conversion": 20.93,
                "performance_grade": "B",
            },
            {
                "ad_id": "mock_003",
                "ad_name": "Headshot AI — Quick & Easy",
                "status": "PAUSED",
                "creative_body": "Upload a selfie, get a headshot. It's that simple.",
                "creative_title": "Selfie to Headshot",
                "image_url": "",
                "targeting_summary": "US, CA, 18-45, Advantage+",
                "ad_set_name": "Broad Advantage+",
                "spend": 30.42,
                "impressions": 2310,
                "clicks": 36,
                "ctr": 1.56,
                "cpm": 13.17,
                "conversions": 0,
                "cost_per_conversion": 0,
                "performance_grade": "C",
            },
        ],
        "targeting_breakdown": [
            {
                "ad_set_id": "mock_adset_001",
                "ad_set_name": "US Professionals Broad",
                "targeting": {"countries": ["US"], "age_min": 25, "age_max": 65},
                "optimization_goal": "OFFSITE_CONVERSIONS",
                "daily_budget": 25.0,
                "spend": 94.21,
                "cpm": 12.71,
                "conversions": 5,
                "ads_count": 1,
            },
            {
                "ad_set_id": "mock_adset_002",
                "ad_set_name": "LinkedIn Job Seekers",
                "targeting": {"countries": ["US"], "age_min": 25, "age_max": 55},
                "optimization_goal": "OFFSITE_CONVERSIONS",
                "daily_budget": 15.0,
                "spend": 62.80,
                "cpm": 12.31,
                "conversions": 3,
                "ads_count": 1,
            },
            {
                "ad_set_id": "mock_adset_003",
                "ad_set_name": "Broad Advantage+",
                "targeting": {"countries": ["US", "CA"], "age_min": 18, "age_max": 45},
                "optimization_goal": "OFFSITE_CONVERSIONS",
                "daily_budget": 10.0,
                "spend": 30.42,
                "cpm": 13.17,
                "conversions": 0,
                "ads_count": 1,
            },
        ],
        "recommendations": [
            {
                "id": "mock_pause_003",
                "text": "Ad \"Quick & Easy\" has 0 conversions — consider pausing and reallocating budget.",
                "action_type": "instant",
                "action_label": "Pause this ad",
                "action_payload": {"action": "pause_ad", "ad_id": "mock_003"},
            },
            {
                "id": "mock_frequency_ok",
                "text": "Frequency is 2.4 which is acceptable, but monitor weekly for ad fatigue.",
                "action_type": "none",
                "action_label": "",
                "action_payload": {},
            },
            {
                "id": "mock_duplicate_top",
                "text": "Top performer \"Professional Look\" has a 2.52% CTR — duplicate and test variations.",
                "action_type": "initiative",
                "action_label": "Create variations",
                "action_payload": {
                    "title": "Duplicate and test variations of top-performing ad",
                    "goal": "The \"Professional Look\" ad has a 2.52% CTR. Create 3 variations with different angles to find even better performers.",
                },
            },
            {
                "id": "mock_new_creatives",
                "text": "Test new creatives targeting job seekers with urgency-style copy.",
                "action_type": "initiative",
                "action_label": "Generate urgency copy",
                "action_payload": {
                    "title": "Generate urgency-style ad copy for job seekers",
                    "goal": "Create new ad creatives with urgency-style copy specifically targeting job seekers who need professional headshots quickly.",
                },
            },
            {
                "id": "mock_increase_budget_001",
                "text": "Ad set 'US Professionals Broad' is converting well. Consider increasing budget.",
                "action_type": "instant",
                "action_label": "Increase to $35/day",
                "action_payload": {"action": "update_budget", "ad_set_id": "mock_adset_001", "new_daily_budget": 3500},
            },
        ],
        "generated_creatives": [],
    }


@router.get("/report")
async def get_campaign_report(product: Optional[str] = None):
    """Get enriched campaign report: account health, creative+targeting combos, and recommendations.

    Pass ?product=Headshot+AI to filter to a single product's campaigns.
    """
    import httpx

    token = settings.facebook_access_token
    ad_account_raw = settings.facebook_ad_account_id or ""
    ad_account = ad_account_raw if ad_account_raw.startswith("act_") else f"act_{ad_account_raw}"

    if not token or not ad_account_raw:
        logger.warning("Facebook credentials missing — returning mock report")
        mock = _mock_report()
        _reports.append(mock)
        return mock

    fb_base = "https://graph.facebook.com/v21.0"

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            # Fire all three requests concurrently
            insights_req = client.get(
                f"{fb_base}/{ad_account}/insights",
                params={
                    "fields": "spend,impressions,clicks,cpm,ctr,actions,cost_per_action_type,frequency",
                    "date_preset": "last_7d",
                    "access_token": token,
                },
            )
            ads_req = client.get(
                f"{fb_base}/{ad_account}/ads",
                params={
                    "fields": (
                        "id,name,status,effective_status,"
                        "creative{id,name,body,title,image_url,thumbnail_url,link_url},"
                        "insights.date_preset(last_7d){spend,impressions,clicks,cpm,ctr,actions,cost_per_action_type},"
                        "adset_id,campaign_id"
                    ),
                    "access_token": token,
                },
            )
            adsets_req = client.get(
                f"{fb_base}/{ad_account}/adsets",
                params={
                    "fields": (
                        "id,name,status,targeting,daily_budget,optimization_goal,"
                        "insights.date_preset(last_7d){spend,impressions,clicks,cpm,ctr,actions}"
                    ),
                    "access_token": token,
                },
            )

            insights_resp, ads_resp, adsets_resp = await asyncio.gather(
                insights_req, ads_req, adsets_req,
            )

        # --- Parse account-level insights ---
        insights_data = insights_resp.json().get("data", [{}])
        acct = insights_data[0] if insights_data else {}
        acct_actions = acct.get("actions", [])
        acct_cost_per = acct.get("cost_per_action_type", [])
        acct_spend = float(acct.get("spend", 0))
        acct_conversions = _extract_conversions(acct_actions)
        acct_cpc = _extract_cost_per_conversion(acct_cost_per)
        acct_roas = round(acct_conversions * acct_cpc / acct_spend, 2) if acct_spend > 0 and acct_cpc > 0 else 0

        account_health = {
            "spend_7d": acct_spend,
            "impressions": int(acct.get("impressions", 0)),
            "clicks": int(acct.get("clicks", 0)),
            "cpm": float(acct.get("cpm", 0)),
            "ctr": float(acct.get("ctr", 0)),
            "conversions": acct_conversions,
            "cost_per_conversion": acct_cpc,
            "frequency": float(acct.get("frequency", 0)),
            "roas": acct_roas,
        }

        # --- Parse ad sets (targeting) ---
        adsets_raw = adsets_resp.json().get("data", [])
        adset_map: Dict[str, dict] = {}  # adset_id -> adset info
        targeting_breakdown = []
        for adset in adsets_raw:
            adset_id = adset.get("id", "")
            targeting = adset.get("targeting", {})
            adset_insights = adset.get("insights", {}).get("data", [{}])
            ai = adset_insights[0] if adset_insights else {}
            adset_convs = _extract_conversions(ai.get("actions"))
            entry = {
                "ad_set_id": adset_id,
                "ad_set_name": adset.get("name", ""),
                "targeting": {
                    "countries": targeting.get("geo_locations", {}).get("countries", []),
                    "age_min": targeting.get("age_min", 18),
                    "age_max": targeting.get("age_max", 65),
                },
                "optimization_goal": adset.get("optimization_goal", ""),
                "daily_budget": float(adset.get("daily_budget", 0)) / 100,  # FB returns cents
                "spend": float(ai.get("spend", 0)),
                "cpm": float(ai.get("cpm", 0)),
                "conversions": adset_convs,
                "ads_count": 0,
            }
            adset_map[adset_id] = {
                "name": adset.get("name", ""),
                "targeting_summary": _summarize_targeting(targeting),
                "targeting": targeting,
            }
            targeting_breakdown.append(entry)

        # --- Parse ads (creative performance) ---
        ads_raw = ads_resp.json().get("data", [])

        # Auto-detect products from ad names and persist mappings
        auto_detected = await _auto_detect_and_save(ads_raw, ad_account)

        # Build product filter sets if a product filter was requested
        allowed_campaign_ids: set[str] | None = None
        if product:
            # Get explicitly-mapped campaign IDs from DB
            db_campaign_ids = await _get_product_campaign_ids(product, ad_account)
            # Merge with auto-detected ones
            detected_ids = {cid for cid, pname in auto_detected.items() if pname == product}
            allowed_campaign_ids = db_campaign_ids | detected_ids

        creative_performance = []
        adset_ad_counts: Dict[str, int] = {}
        # Track which adset_ids belong to matching ads (for filtering targeting_breakdown)
        matched_adset_ids: set[str] = set()

        for ad in ads_raw:
            ad_id = ad.get("id", "")
            campaign_id = ad.get("campaign_id", "")

            # --- Product filtering ---
            if allowed_campaign_ids is not None:
                # Include if campaign is in the allowed set OR ad name matches product
                in_allowed = campaign_id in allowed_campaign_ids
                name_match = product and product.lower() in ad.get("name", "").lower()
                if not in_allowed and not name_match:
                    continue

            creative = ad.get("creative", {})
            ad_insights = ad.get("insights", {}).get("data", [{}])
            ai = ad_insights[0] if ad_insights else {}
            ad_conversions = _extract_conversions(ai.get("actions"))
            ad_spend = float(ai.get("spend", 0))
            ad_ctr = float(ai.get("ctr", 0))
            ad_cpm = float(ai.get("cpm", 0))
            ad_cost_per = _extract_cost_per_conversion(ai.get("cost_per_action_type"))
            adset_id = ad.get("adset_id", "")
            adset_info = adset_map.get(adset_id, {})
            adset_ad_counts[adset_id] = adset_ad_counts.get(adset_id, 0) + 1
            matched_adset_ids.add(adset_id)

            creative_performance.append({
                "ad_id": ad_id,
                "ad_name": ad.get("name", ""),
                "status": ad.get("effective_status", ad.get("status", "UNKNOWN")),
                "creative_body": creative.get("body", ""),
                "creative_title": creative.get("title", ""),
                "image_url": creative.get("thumbnail_url", "") or creative.get("image_url", ""),
                "targeting_summary": adset_info.get("targeting_summary", ""),
                "ad_set_name": adset_info.get("name", ""),
                "spend": ad_spend,
                "impressions": int(ai.get("impressions", 0)),
                "clicks": int(ai.get("clicks", 0)),
                "ctr": ad_ctr,
                "cpm": ad_cpm,
                "conversions": ad_conversions,
                "cost_per_conversion": ad_cost_per,
                "performance_grade": _grade_creative(ad_ctr, ad_cpm, ad_conversions),
            })

        # Update ads_count on targeting breakdown and filter to matched ad sets
        for tb in targeting_breakdown:
            tb["ads_count"] = adset_ad_counts.get(tb["ad_set_id"], 0)

        if allowed_campaign_ids is not None:
            targeting_breakdown = [tb for tb in targeting_breakdown if tb["ad_set_id"] in matched_adset_ids]

        # Recompute account health from filtered ads when product filter is active
        if allowed_campaign_ids is not None and creative_performance:
            filtered_spend = sum(c["spend"] for c in creative_performance)
            filtered_impressions = sum(c["impressions"] for c in creative_performance)
            filtered_clicks = sum(c["clicks"] for c in creative_performance)
            filtered_conversions = sum(c["conversions"] for c in creative_performance)
            account_health = {
                "spend_7d": filtered_spend,
                "impressions": filtered_impressions,
                "clicks": filtered_clicks,
                "cpm": (filtered_spend / filtered_impressions * 1000) if filtered_impressions > 0 else 0,
                "ctr": (filtered_clicks / filtered_impressions * 100) if filtered_impressions > 0 else 0,
                "conversions": filtered_conversions,
                "cost_per_conversion": (filtered_spend / filtered_conversions) if filtered_conversions > 0 else 0,
                "frequency": account_health.get("frequency", 0),  # keep original, can't recompute
                "roas": account_health.get("roas", 0),
            }

        recommendations = _generate_recommendations(account_health, creative_performance, targeting_breakdown)

        report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "is_mock": False,
            "account_health": account_health,
            "creative_performance": creative_performance,
            "targeting_breakdown": targeting_breakdown,
            "recommendations": recommendations,
            "generated_creatives": [],
        }

        _reports.append(report)
        return report

    except Exception as e:
        logger.error(f"Campaign report failed, falling back to mock: {e}")
        mock = _mock_report()
        _reports.append(mock)
        return mock


# --- Execute instant action endpoint ---

@router.post("/execute-action")
async def execute_campaign_action(action: dict):
    """Execute an instant campaign action (pause ad, update budget, etc.)."""
    import httpx

    token = settings.facebook_access_token
    if not token:
        raise HTTPException(400, "Facebook token not configured")

    action_type = action.get("action")

    if action_type == "pause_ad":
        ad_id = action["ad_id"]
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"https://graph.facebook.com/v21.0/{ad_id}",
                data={"status": "PAUSED", "access_token": token},
            )
            if resp.status_code != 200:
                raise HTTPException(502, f"Failed to pause ad: {resp.text}")
            return {"status": "ok", "action": "paused", "ad_id": ad_id}

    elif action_type == "update_budget":
        ad_set_id = action["ad_set_id"]
        new_budget = action["new_daily_budget"]
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"https://graph.facebook.com/v21.0/{ad_set_id}",
                data={"daily_budget": str(new_budget), "access_token": token},
            )
            if resp.status_code != 200:
                raise HTTPException(502, f"Failed to update budget: {resp.text}")
            return {"status": "ok", "action": "budget_updated", "ad_set_id": ad_set_id, "new_budget": new_budget}

    elif action_type == "scale_budget":
        factor = action.get("scale_factor", 1.2)
        ad_account = settings.facebook_ad_account_id
        if not ad_account.startswith("act_"):
            ad_account = f"act_{ad_account}"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"https://graph.facebook.com/v21.0/{ad_account}/adsets",
                params={"fields": "id,daily_budget,status", "access_token": token},
            )
            ad_sets = resp.json().get("data", [])
            scaled = []
            for adset in ad_sets:
                if adset.get("status") == "ACTIVE" and adset.get("daily_budget"):
                    new_budget = int(float(adset["daily_budget"]) * factor)
                    update_resp = await client.post(
                        f"https://graph.facebook.com/v21.0/{adset['id']}",
                        data={"daily_budget": str(new_budget), "access_token": token},
                    )
                    if update_resp.status_code == 200:
                        scaled.append(adset["id"])
            return {"status": "ok", "action": "scaled", "scaled_adsets": scaled, "factor": factor}

    raise HTTPException(400, f"Unknown action: {action_type}")


# --- Optimize endpoint ---

@router.post("/optimize")
async def optimize_campaigns():
    """Run the campaign_manager agent for a full analysis + recommendations."""
    if _registry is None or not _registry.has("campaign_manager"):
        raise HTTPException(status_code=503, detail="Campaign manager agent not available")

    task_id = str(uuid.uuid4())
    _optimize_tasks[task_id] = {
        "status": "running",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "result": None,
        "error": None,
    }

    asyncio.create_task(_run_optimization(task_id))

    return {"task_id": task_id, "status": "running"}


@router.get("/optimize/{task_id}")
async def get_optimize_status(task_id: str):
    """Check status of an optimization run."""
    task = _optimize_tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


# --- Generate creatives endpoint ---

@router.post("/generate-creatives")
async def generate_creatives(req: GenerateCreativesRequest):
    """Generate ad copy suggestions using proven templates."""
    from aeco.tools.facebook_tools import facebook_generate_ad_copy

    result = facebook_generate_ad_copy(
        product=req.product,
        audience=req.audience,
        style=req.style,
        count=req.count,
    )

    # facebook_generate_ad_copy returns {"ad_copies": [...], ...}
    creatives = result.get("ad_copies", []) if isinstance(result, dict) else result
    return {"creatives": creatives, "style": req.style}


# --- Create Ad (push to Facebook) ---

_FB_BASE = "https://graph.facebook.com/v21.0"
_FB_PAGE_ID = "1091699287351335"
_FB_CAMPAIGN_ID = "120243888605780566"
_FB_AD_SET_ID = "120243888617760566"


@router.post("/create-ad")
async def create_ad(req: CreateAdRequest):
    """Create a live Facebook ad from generated copy."""
    import httpx

    token = settings.facebook_access_token
    if not token:
        raise HTTPException(status_code=400, detail="Facebook access token not configured")

    ad_account = settings.facebook_ad_account_id.replace("act_", "")
    if not ad_account:
        raise HTTPException(status_code=400, detail="Facebook ad account ID not configured")

    act_id = f"act_{ad_account}"

    # Step 1: Create ad creative
    # Facebook Graph API requires form-encoded data, not JSON
    import json as _json

    object_story_spec = _json.dumps({
        "page_id": _FB_PAGE_ID,
        "link_data": {
            "link": req.link,
            "message": req.primary_text,
            "name": req.headline,
            "description": req.description,
            "call_to_action": {"type": req.cta_type, "value": {"link": req.link}},
        },
    })

    async with httpx.AsyncClient(timeout=30) as client:
        # Create creative
        cr_resp = await client.post(
            f"{_FB_BASE}/{act_id}/adcreatives",
            data={
                "name": f"AECO — {req.headline[:60]}",
                "object_story_spec": object_story_spec,
                "access_token": token,
            },
        )
        if cr_resp.status_code != 200:
            logger.error(f"Facebook creative creation failed: {cr_resp.text}")
            raise HTTPException(status_code=502, detail=f"Facebook API error (creative): {cr_resp.text}")
        creative_id = cr_resp.json().get("id")

        # Step 2: Create ad
        ad_resp = await client.post(
            f"{_FB_BASE}/{act_id}/ads",
            data={
                "name": f"AECO — {req.headline[:60]}",
                "adset_id": _FB_AD_SET_ID,
                "creative": _json.dumps({"creative_id": creative_id}),
                "status": "ACTIVE",
                "access_token": token,
            },
        )
        if ad_resp.status_code != 200:
            logger.error(f"Facebook ad creation failed: {ad_resp.text}")
            raise HTTPException(status_code=502, detail=f"Facebook API error (ad): {ad_resp.text}")
        ad_id = ad_resp.json().get("id")

    # Save product mapping for the campaign this ad belongs to
    await _save_product_mapping(
        campaign_id=_FB_CAMPAIGN_ID,
        product_name=req.product_name,
        ad_account_id=act_id,
    )

    logger.info(f"Created Facebook ad {ad_id} with creative {creative_id} (product={req.product_name})")
    return {"ad_id": ad_id, "creative_id": creative_id}


# --- Product mapping endpoints ---

@router.get("/products")
async def list_products():
    """Return distinct product names from campaign-product mappings."""
    async with async_session_factory() as session:
        result = await session.execute(
            select(distinct(CampaignProduct.product_name)).order_by(CampaignProduct.product_name)
        )
        names = [row[0] for row in result.fetchall()]
    # Always include known products even if no mappings exist yet
    for p in _PRODUCT_PREFIXES:
        if p not in names:
            names.append(p)
    return {"products": sorted(names)}


@router.post("/products/map")
async def map_campaign_to_product(
    campaign_id: str,
    product_name: str,
    workspace_path: str = "",
):
    """Manually map an existing Facebook campaign to an AECO product."""
    ad_account_raw = settings.facebook_ad_account_id or ""
    ad_account = ad_account_raw if ad_account_raw.startswith("act_") else f"act_{ad_account_raw}"
    if not ad_account_raw:
        raise HTTPException(400, "Facebook ad account ID not configured")

    await _save_product_mapping(campaign_id, product_name, ad_account, workspace_path)
    return {"status": "ok", "campaign_id": campaign_id, "product_name": product_name}


# --- Internal functions ---

async def _run_monitor_check(**kwargs):
    """Periodic check — pull account overview, flag anomalies."""
    try:
        from aeco.tools.facebook_tools import facebook_get_account_overview

        overview = await facebook_get_account_overview(date_range="last_7d")
        summary = overview.get("summary", {})
        diagnosis = overview.get("diagnosis", {})

        report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "summary": summary,
            "diagnosis": diagnosis,
            "alerts": [],
        }

        # Check for anomalies
        if diagnosis.get("cpm_status") == "high":
            report["alerts"].append(f"CPM is high: {summary.get('cpm', 0)}")
        if diagnosis.get("conversion_status") == "zero":
            report["alerts"].append(f"Zero conversions with {summary.get('spend', 0)} spend")
        if summary.get("ctr", 0) < 0.005 and summary.get("impressions", 0) > 1000:
            report["alerts"].append(f"CTR very low: {summary.get('ctr', 0)*100:.2f}%")

        _reports.append(report)

        if report["alerts"]:
            logger.warning(f"Campaign monitor alerts: {report['alerts']}")
            # Could trigger full optimization here in the future
        else:
            logger.info("Campaign monitor check: all metrics normal")

    except Exception as e:
        logger.error(f"Campaign monitor check failed: {e}")
        _reports.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error": str(e),
            "alerts": [f"Monitor check failed: {e}"],
        })


async def _run_optimization(task_id: str):
    """Run the campaign_manager agent for full optimization."""
    task = _optimize_tasks[task_id]

    try:
        from aeco.agents.executor_factory import create_executor
        from aeco.tools.facebook_tools import facebook_get_account_overview, facebook_creative_report

        # Pre-fetch data for context
        overview = await facebook_get_account_overview(date_range="last_7d")
        creative_data = await facebook_creative_report(date_range="last_7d")

        agent_def = _registry.get("campaign_manager")
        runtime = create_executor(agent_def, _audit_logger)

        context = {
            "task_title": "Optimize Headshot AI Facebook campaigns",
            "task_description": (
                "Analyze current Facebook ad performance and provide optimization recommendations.\n\n"
                f"Account overview (last 7 days): {overview.get('summary', {})}\n"
                f"Diagnosis: {overview.get('diagnosis', {})}\n"
                f"Creative report: {len(creative_data) if isinstance(creative_data, list) else 'unavailable'} creatives analyzed\n\n"
                "Use your tools to dig deeper into the data. Provide specific, actionable recommendations."
            ),
        }

        result = await asyncio.wait_for(
            runtime.execute(context),
            timeout=600,
        )

        task["status"] = "done"
        task["result"] = result
        task["completed_at"] = datetime.now(timezone.utc).isoformat()

        # Store as a report too
        _reports.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": "optimization",
            "summary": result.get("account_health", {}),
            "actions": result.get("actions", []),
            "new_creatives": result.get("new_creatives", []),
            "recommendations": result.get("budget_recommendations", []),
        })

        logger.info(f"Campaign optimization {task_id} completed")

    except asyncio.TimeoutError:
        task["status"] = "error"
        task["error"] = "Optimization timed out after 600s"
        logger.error(f"Campaign optimization {task_id} timed out")

    except Exception as e:
        task["status"] = "error"
        task["error"] = str(e)
        logger.error(f"Campaign optimization {task_id} failed: {e}")
