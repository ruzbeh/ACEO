"""Stripe API tools for revenue tracking and customer management.

When no API key is configured, returns mock data so agents can still run.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from aeco.config import settings

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.stripe.com/v1"


def _get_key() -> str | None:
    return getattr(settings, "stripe_api_key", None) or None


def _mock_response(description: str) -> dict:
    return {"mock": True, "message": f"[MOCK] {description} — configure STRIPE_API_KEY to use real API"}


def _headers(key: str) -> dict:
    return {"Authorization": f"Bearer {key}"}


async def stripe_get_mrr(**kwargs: Any) -> dict:
    """Get current MRR, subscriber count, and revenue breakdown by plan."""
    key = _get_key()
    if not key:
        return _mock_response("Get MRR: would return monthly recurring revenue, active subscriptions, revenue by plan")

    async with httpx.AsyncClient(timeout=30) as client:
        # Get active subscriptions
        resp = await client.get(
            f"{_BASE_URL}/subscriptions",
            headers=_headers(key),
            params={"status": "active", "limit": 100},
        )
        resp.raise_for_status()
        subs = resp.json().get("data", [])

        mrr = sum(
            s.get("items", {}).get("data", [{}])[0].get("price", {}).get("unit_amount", 0) / 100
            for s in subs
        )
        return {
            "mrr": mrr,
            "active_subscriptions": len(subs),
            "arr": mrr * 12,
        }


async def stripe_get_revenue(**kwargs: Any) -> dict:
    """Get revenue for a time period (charges, refunds, net)."""
    days = kwargs.get("days", 30)
    key = _get_key()
    if not key:
        return _mock_response(f"Get revenue: last {days} days — total charges, refunds, net revenue")

    import time
    created_after = int(time.time()) - (days * 86400)

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{_BASE_URL}/charges",
            headers=_headers(key),
            params={"created[gte]": created_after, "limit": 100},
        )
        resp.raise_for_status()
        charges = resp.json().get("data", [])

        total = sum(c.get("amount", 0) for c in charges if c.get("paid")) / 100
        refunded = sum(c.get("amount_refunded", 0) for c in charges) / 100
        return {
            "total_revenue": total,
            "refunds": refunded,
            "net_revenue": total - refunded,
            "charge_count": len(charges),
            "period_days": days,
        }


async def stripe_get_churn(**kwargs: Any) -> dict:
    """Get recent subscription cancellations and churn metrics."""
    days = kwargs.get("days", 30)
    key = _get_key()
    if not key:
        return _mock_response(f"Get churn: last {days} days — cancelled subscriptions, churn rate, reasons")

    import time
    created_after = int(time.time()) - (days * 86400)

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{_BASE_URL}/subscriptions",
            headers=_headers(key),
            params={"status": "canceled", "created[gte]": created_after, "limit": 100},
        )
        resp.raise_for_status()
        canceled = resp.json().get("data", [])
        return {
            "canceled_count": len(canceled),
            "period_days": days,
        }


async def stripe_get_customers(**kwargs: Any) -> dict:
    """Get customer count and recent signups."""
    days = kwargs.get("days", 30)
    key = _get_key()
    if not key:
        return _mock_response(f"Get customers: total count, new in last {days} days")

    import time
    created_after = int(time.time()) - (days * 86400)

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{_BASE_URL}/customers",
            headers=_headers(key),
            params={"created[gte]": created_after, "limit": 100},
        )
        resp.raise_for_status()
        customers = resp.json().get("data", [])
        return {
            "new_customers": len(customers),
            "period_days": days,
        }
