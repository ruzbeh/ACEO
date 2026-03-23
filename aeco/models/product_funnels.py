"""Product-specific funnel definitions.

Each product has its own funnel steps mapped to Facebook Pixel events.
"""
from __future__ import annotations
from typing import Any

PRODUCT_FUNNELS: dict[str, list[dict[str, Any]]] = {
    "Headshot AI": [
        {"name": "Ad Impression", "key": "impressions", "source": "metric", "description": "User sees the ad"},
        {"name": "Ad Click", "key": "link_click", "source": "action", "description": "User clicks the ad"},
        {"name": "Landing Page View", "key": "landing_page_view", "source": "action", "description": "User lands on headshot-generators.com"},
        {"name": "Email Submitted", "key": "lead", "alt_keys": ["offsite_conversion.fb_pixel_lead"], "source": "action", "description": "User enters email on upload page"},
        {"name": "Photos Uploaded", "key": "offsite_conversion.fb_pixel_complete_registration", "alt_keys": ["complete_registration"], "source": "action", "description": "User finishes uploading selfies"},
        {"name": "Tier Selected", "key": "offsite_conversion.fb_pixel_add_to_cart", "alt_keys": ["add_to_cart"], "source": "action", "description": "User picks pricing tier ($9/$19/$29)"},
        {"name": "Checkout Started", "key": "offsite_conversion.fb_pixel_initiate_checkout", "alt_keys": ["initiate_checkout"], "source": "action", "description": "User clicks pay → Stripe checkout"},
        {"name": "Purchase", "key": "offsite_conversion.fb_pixel_purchase", "alt_keys": ["purchase"], "source": "action", "description": "Payment completed", "is_conversion": True},
    ],
    "_default": [
        {"name": "Impression", "key": "impressions", "source": "metric"},
        {"name": "Click", "key": "link_click", "source": "action"},
        {"name": "Landing View", "key": "landing_page_view", "source": "action"},
        {"name": "Lead", "key": "lead", "alt_keys": ["offsite_conversion.fb_pixel_lead"], "source": "action"},
        {"name": "Purchase", "key": "offsite_conversion.fb_pixel_purchase", "alt_keys": ["purchase"], "source": "action", "is_conversion": True},
    ],
}


def get_funnel(product_name: str) -> list[dict[str, Any]]:
    """Get the funnel definition for a product."""
    if product_name in PRODUCT_FUNNELS:
        return PRODUCT_FUNNELS[product_name]
    lower = product_name.lower()
    for key, funnel in PRODUCT_FUNNELS.items():
        if key.lower() in lower or lower in key.lower():
            return funnel
    return PRODUCT_FUNNELS["_default"]


def extract_funnel_metrics(funnel: list[dict[str, Any]], insights: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract funnel step values from Facebook insights response."""
    actions = {a["action_type"]: int(a["value"]) for a in insights.get("actions", [])}
    action_values = {a["action_type"]: float(a["value"]) for a in insights.get("action_values", [])}

    result = []
    prev_value = None

    for step in funnel:
        if step["source"] == "metric":
            value = int(insights.get(step["key"], 0))
        else:
            value = actions.get(step["key"], 0)
            if value == 0:
                for alt in step.get("alt_keys", []):
                    value = actions.get(alt, 0)
                    if value > 0:
                        break

        monetary_value = 0.0
        if step.get("is_conversion"):
            monetary_value = action_values.get(step["key"], 0)
            if monetary_value == 0:
                for alt in step.get("alt_keys", []):
                    monetary_value = action_values.get(alt, 0)
                    if monetary_value > 0:
                        break

        drop = None
        if prev_value is not None and prev_value > 0:
            drop_pct = round((1 - value / prev_value) * 100, 1)
            lost = prev_value - value
            severity = "critical" if drop_pct > 95 else "warning" if drop_pct > 80 else "ok"
            drop = {"percent": drop_pct, "lost": lost, "severity": severity}

        result.append({
            "name": step["name"],
            "key": step["key"],
            "value": value,
            "monetary_value": monetary_value,
            "description": step.get("description", ""),
            "is_conversion": step.get("is_conversion", False),
            "drop_from_previous": drop,
        })
        prev_value = value

    return result
