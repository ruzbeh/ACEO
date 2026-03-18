"""Facebook/Meta Ads API tools for campaign management.

These tools wrap the Meta Marketing API. When no API token is configured,
they return mock data so the agent pipeline can still run end-to-end.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from aeco.config import settings

logger = logging.getLogger(__name__)

_BASE_URL = "https://graph.facebook.com/v19.0"


def _get_token() -> str | None:
    return getattr(settings, "facebook_access_token", None) or None


def _mock_response(description: str) -> dict:
    return {"mock": True, "message": f"[MOCK] {description} — configure FACEBOOK_ACCESS_TOKEN to use real API"}


async def facebook_get_campaigns(**kwargs: Any) -> dict:
    """Read active Facebook ad campaigns with performance metrics."""
    token = _get_token()
    if not token:
        return _mock_response("Get campaigns: would return active campaigns with spend, impressions, clicks, conversions")

    ad_account_id = getattr(settings, "facebook_ad_account_id", "")
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{_BASE_URL}/act_{ad_account_id}/campaigns",
            params={
                "access_token": token,
                "fields": "name,status,objective,daily_budget,lifetime_budget,start_time",
                "effective_status": '["ACTIVE","PAUSED"]',
            },
        )
        resp.raise_for_status()
        return resp.json()


async def facebook_get_insights(**kwargs: Any) -> dict:
    """Get campaign performance insights (spend, impressions, clicks, conversions, CPC, CTR)."""
    campaign_id = kwargs.get("campaign_id", "")
    date_range = kwargs.get("date_range", "last_7d")
    token = _get_token()
    if not token:
        return _mock_response(f"Get insights for campaign {campaign_id}: spend, CTR, CPC, conversions over {date_range}")

    time_range = {"since": "2024-01-01", "until": "2024-12-31"}
    if date_range == "last_7d":
        import datetime
        end = datetime.date.today()
        start = end - datetime.timedelta(days=7)
        time_range = {"since": start.isoformat(), "until": end.isoformat()}

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{_BASE_URL}/{campaign_id}/insights",
            params={
                "access_token": token,
                "fields": "spend,impressions,clicks,ctr,cpc,actions,cost_per_action_type",
                "time_range": str(time_range),
            },
        )
        resp.raise_for_status()
        return resp.json()


async def facebook_update_campaign(**kwargs: Any) -> dict:
    """Update a campaign (pause, resume, change budget)."""
    campaign_id = kwargs.get("campaign_id", "")
    status = kwargs.get("status")  # ACTIVE or PAUSED
    daily_budget = kwargs.get("daily_budget")
    token = _get_token()
    if not token:
        return _mock_response(f"Update campaign {campaign_id}: status={status}, budget={daily_budget}")

    data: dict[str, Any] = {"access_token": token}
    if status:
        data["status"] = status
    if daily_budget is not None:
        data["daily_budget"] = int(daily_budget * 100)  # Meta API uses cents

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(f"{_BASE_URL}/{campaign_id}", data=data)
        resp.raise_for_status()
        return resp.json()


async def facebook_create_campaign(**kwargs: Any) -> dict:
    """Create a new ad campaign."""
    name = kwargs.get("name", "New Campaign")
    objective = kwargs.get("objective", "OUTCOME_SALES")
    daily_budget = kwargs.get("daily_budget", 50.0)
    token = _get_token()
    if not token:
        return _mock_response(f"Create campaign: {name}, objective={objective}, budget=${daily_budget}/day")

    ad_account_id = getattr(settings, "facebook_ad_account_id", "")
    data = {
        "access_token": token,
        "name": name,
        "objective": objective,
        "status": "PAUSED",
        "daily_budget": int(daily_budget * 100),
        "special_ad_categories": "[]",
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(f"{_BASE_URL}/act_{ad_account_id}/campaigns", data=data)
        resp.raise_for_status()
        return resp.json()
