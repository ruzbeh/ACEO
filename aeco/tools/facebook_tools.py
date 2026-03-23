"""Facebook/Meta Ads API tools for campaign management and optimization.

These tools wrap the Meta Marketing API v19.0. When no API token is configured,
they return mock data so the agent pipeline can still run end-to-end.

Required config:
  FACEBOOK_ACCESS_TOKEN — Long-lived user or system user token with ads_read + ads_management
  FACEBOOK_AD_ACCOUNT_ID — Your ad account ID (without act_ prefix)
"""
from __future__ import annotations

import datetime
import hashlib
import logging
from typing import Any

import httpx

from aeco.config import settings

logger = logging.getLogger(__name__)

_BASE_URL = "https://graph.facebook.com/v19.0"


def _get_token() -> str | None:
    return getattr(settings, "facebook_access_token", None) or None


def _get_account_id() -> str:
    aid = getattr(settings, "facebook_ad_account_id", "")
    # Strip act_ prefix if user included it
    return aid.replace("act_", "") if aid else ""


def _mock_response(description: str) -> dict:
    return {
        "mock": True,
        "message": f"[MOCK] {description} — set FACEBOOK_ACCESS_TOKEN and FACEBOOK_AD_ACCOUNT_ID in .env",
    }


def _date_range(range_str: str) -> dict[str, str]:
    """Convert human-friendly range to Meta API time_range."""
    end = datetime.date.today()
    ranges = {
        "today": 0, "yesterday": 1, "last_3d": 3, "last_7d": 7,
        "last_14d": 14, "last_30d": 30, "last_90d": 90,
    }
    days = ranges.get(range_str, 7)
    start = end - datetime.timedelta(days=max(days, 1))
    if range_str == "today":
        start = end
    elif range_str == "yesterday":
        start = end - datetime.timedelta(days=1)
        end = start
    return {"since": start.isoformat(), "until": end.isoformat()}


async def _api_get(path: str, params: dict) -> dict:
    """Make authenticated GET request to Meta API."""
    token = _get_token()
    params["access_token"] = token
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(f"{_BASE_URL}/{path}", params=params)
        resp.raise_for_status()
        return resp.json()


async def _api_post(path: str, data: dict) -> dict:
    """Make authenticated POST request to Meta API."""
    token = _get_token()
    data["access_token"] = token
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(f"{_BASE_URL}/{path}", data=data)
        resp.raise_for_status()
        return resp.json()


# ──────────────────────────────────────────────────────────────────
# 1. READ: Campaign + Ad Set + Ad level data
# ──────────────────────────────────────────────────────────────────


async def facebook_get_campaigns(**kwargs: Any) -> dict:
    """Read all campaigns with status, budget, and objective."""
    if not _get_token():
        return _mock_response("Get campaigns: list all active/paused campaigns with budget and objective")

    return await _api_get(
        f"act_{_get_account_id()}/campaigns",
        {
            "fields": "name,status,objective,daily_budget,lifetime_budget,start_time,stop_time,buying_type",
            "effective_status": '["ACTIVE","PAUSED"]',
            "limit": "100",
        },
    )


async def facebook_get_adsets(**kwargs: Any) -> dict:
    """Read ad sets for a campaign — targeting, bid strategy, placements."""
    campaign_id = kwargs.get("campaign_id", "")
    if not _get_token():
        return _mock_response(f"Get ad sets for campaign {campaign_id}: targeting, bid, budget, placement details")

    path = f"{campaign_id}/adsets" if campaign_id else f"act_{_get_account_id()}/adsets"
    return await _api_get(
        path,
        {
            "fields": (
                "name,status,daily_budget,lifetime_budget,bid_amount,bid_strategy,"
                "billing_event,optimization_goal,targeting,promoted_object,"
                "start_time,end_time"
            ),
            "effective_status": '["ACTIVE","PAUSED"]',
            "limit": "100",
        },
    )


async def facebook_get_ads(**kwargs: Any) -> dict:
    """Read ads for an ad set — creative, status, preview."""
    adset_id = kwargs.get("adset_id", "")
    if not _get_token():
        return _mock_response(f"Get ads for ad set {adset_id}: creative details, preview URL, status")

    path = f"{adset_id}/ads" if adset_id else f"act_{_get_account_id()}/ads"
    return await _api_get(
        path,
        {
            "fields": "name,status,creative{title,body,image_url,thumbnail_url,link_url},preview_shareable_link",
            "effective_status": '["ACTIVE","PAUSED"]',
            "limit": "50",
        },
    )


# ──────────────────────────────────────────────────────────────────
# 2. INSIGHTS: Performance metrics at every level
# ──────────────────────────────────────────────────────────────────

_INSIGHT_FIELDS = (
    "campaign_name,adset_name,ad_name,"
    "spend,impressions,reach,frequency,"
    "clicks,unique_clicks,ctr,unique_ctr,"
    "cpc,cpm,cpp,"
    "actions,cost_per_action_type,action_values,"
    "conversions,cost_per_conversion,conversion_values,"
    "video_thruplay_watched_actions,video_p25_watched_actions,"
    "quality_score_ectr,quality_score_ecvr,quality_score_organic"
)


async def facebook_get_insights(**kwargs: Any) -> dict:
    """Get performance insights (spend, CPM, CTR, CPC, conversions, ROAS).

    Args:
        campaign_id: Campaign ID (optional — omit for account-level)
        adset_id: Ad set ID (optional)
        ad_id: Ad ID (optional)
        date_range: today, yesterday, last_3d, last_7d, last_14d, last_30d, last_90d
        breakdowns: Optional comma-separated: age, gender, country, placement, device_platform
        level: campaign, adset, ad (default: auto based on ID)
        time_increment: 1 (daily), 7 (weekly), all_days (default: all_days)
    """
    date_range = kwargs.get("date_range", "last_7d")
    breakdowns = kwargs.get("breakdowns", "")
    time_increment = kwargs.get("time_increment", "all_days")

    # Determine path: most specific ID wins
    entity_id = (
        kwargs.get("ad_id")
        or kwargs.get("adset_id")
        or kwargs.get("campaign_id")
        or f"act_{_get_account_id()}"
    )

    if not _get_token():
        return _mock_response(
            f"Get insights for {entity_id} ({date_range}): "
            f"spend, CPM, CTR, CPC, conversions, ROAS"
            + (f" broken down by {breakdowns}" if breakdowns else "")
        )

    params: dict[str, Any] = {
        "fields": _INSIGHT_FIELDS,
        "time_range": str(_date_range(date_range)),
        "time_increment": time_increment,
    }
    level = kwargs.get("level")
    if level:
        params["level"] = level
    if breakdowns:
        params["breakdowns"] = breakdowns

    return await _api_get(f"{entity_id}/insights", params)


async def facebook_get_account_overview(**kwargs: Any) -> dict:
    """Get account-level summary: total spend, CPM, CTR, conversions across all campaigns.

    Quick health check for the founder — "how are my ads doing?"
    """
    date_range = kwargs.get("date_range", "last_7d")
    if not _get_token():
        return _mock_response(f"Account overview ({date_range}): total spend, avg CPM, CTR, conversions, ROAS")

    result = await _api_get(
        f"act_{_get_account_id()}/insights",
        {
            "fields": "spend,impressions,reach,frequency,clicks,ctr,cpc,cpm,actions,cost_per_action_type,action_values",
            "time_range": str(_date_range(date_range)),
            "level": "account",
        },
    )

    # Parse into a human-readable summary
    data = result.get("data", [{}])[0] if result.get("data") else {}
    spend = float(data.get("spend", 0))
    impressions = int(data.get("impressions", 0))
    clicks = int(data.get("clicks", 0))
    cpm = float(data.get("cpm", 0))
    ctr = float(data.get("ctr", 0))
    cpc = float(data.get("cpc", 0))

    # Extract conversions from actions
    conversions = 0
    cost_per_conversion = 0
    for action in data.get("actions", []):
        if action.get("action_type") in ("purchase", "offsite_conversion.fb_pixel_purchase", "lead", "complete_registration"):
            conversions += int(action.get("value", 0))
    if conversions > 0:
        cost_per_conversion = spend / conversions

    # Extract revenue from action_values
    revenue = 0
    for av in data.get("action_values", []):
        if av.get("action_type") in ("purchase", "offsite_conversion.fb_pixel_purchase"):
            revenue += float(av.get("value", 0))
    roas = round(revenue / spend, 2) if spend > 0 else 0

    return {
        "date_range": date_range,
        "raw_data": data,
        "summary": {
            "spend": round(spend, 2),
            "impressions": impressions,
            "clicks": clicks,
            "cpm": round(cpm, 2),
            "ctr": round(ctr, 4),
            "cpc": round(cpc, 2),
            "conversions": conversions,
            "cost_per_conversion": round(cost_per_conversion, 2),
            "revenue": round(revenue, 2),
            "roas": roas,
        },
        "diagnosis": {
            "cpm_status": "high" if cpm > 15 else "normal" if cpm > 5 else "low",
            "ctr_status": "low" if ctr < 0.01 else "normal" if ctr < 0.03 else "good",
            "conversion_status": "zero" if conversions == 0 else "low" if cost_per_conversion > 50 else "healthy",
        },
    }


# ──────────────────────────────────────────────────────────────────
# 3. WRITE: Create, update, pause campaigns/adsets/ads
# ──────────────────────────────────────────────────────────────────


async def facebook_update_campaign(**kwargs: Any) -> dict:
    """Update a campaign (pause, resume, change budget, rename)."""
    campaign_id = kwargs.get("campaign_id", "")
    status = kwargs.get("status")
    daily_budget = kwargs.get("daily_budget")
    name = kwargs.get("name")
    if not _get_token():
        return _mock_response(f"Update campaign {campaign_id}: status={status}, budget={daily_budget}")

    data: dict[str, Any] = {}
    if status:
        data["status"] = status  # ACTIVE or PAUSED
    if daily_budget is not None:
        data["daily_budget"] = int(float(daily_budget) * 100)  # Meta uses cents
    if name:
        data["name"] = name
    return await _api_post(campaign_id, data)


async def facebook_update_adset(**kwargs: Any) -> dict:
    """Update an ad set — budget, bid, targeting, status."""
    adset_id = kwargs.get("adset_id", "")
    if not _get_token():
        return _mock_response(f"Update ad set {adset_id}")

    data: dict[str, Any] = {}
    for field in ("status", "daily_budget", "lifetime_budget", "bid_amount", "name"):
        val = kwargs.get(field)
        if val is not None:
            if field in ("daily_budget", "lifetime_budget", "bid_amount"):
                data[field] = int(float(val) * 100)
            else:
                data[field] = val
    # Targeting update (JSON object)
    targeting = kwargs.get("targeting")
    if targeting:
        import json
        data["targeting"] = json.dumps(targeting) if isinstance(targeting, dict) else targeting
    return await _api_post(adset_id, data)


async def facebook_create_campaign(**kwargs: Any) -> dict:
    """Create a new ad campaign."""
    name = kwargs.get("name", "New Campaign")
    objective = kwargs.get("objective", "OUTCOME_SALES")
    daily_budget = kwargs.get("daily_budget", 50.0)
    if not _get_token():
        return _mock_response(f"Create campaign: {name}, objective={objective}, budget=${daily_budget}/day")

    return await _api_post(
        f"act_{_get_account_id()}/campaigns",
        {
            "name": name,
            "objective": objective,
            "status": "PAUSED",
            "daily_budget": int(float(daily_budget) * 100),
            "special_ad_categories": "[]",
        },
    )


async def facebook_create_adset(**kwargs: Any) -> dict:
    """Create a new ad set with targeting and budget."""
    campaign_id = kwargs.get("campaign_id", "")
    name = kwargs.get("name", "New Ad Set")
    daily_budget = kwargs.get("daily_budget", 20.0)
    targeting = kwargs.get("targeting", {})
    optimization_goal = kwargs.get("optimization_goal", "OFFSITE_CONVERSIONS")
    billing_event = kwargs.get("billing_event", "IMPRESSIONS")
    bid_strategy = kwargs.get("bid_strategy", "LOWEST_COST_WITHOUT_CAP")

    if not _get_token():
        return _mock_response(f"Create ad set: {name} in campaign {campaign_id}")

    import json
    return await _api_post(
        f"act_{_get_account_id()}/adsets",
        {
            "campaign_id": campaign_id,
            "name": name,
            "status": "PAUSED",
            "daily_budget": int(float(daily_budget) * 100),
            "billing_event": billing_event,
            "optimization_goal": optimization_goal,
            "bid_strategy": bid_strategy,
            "targeting": json.dumps(targeting) if isinstance(targeting, dict) else targeting,
        },
    )


# ──────────────────────────────────────────────────────────────────
# 4. DIAGNOSIS: High-level tools for the agent to diagnose problems
# ──────────────────────────────────────────────────────────────────


async def facebook_diagnose_cpm(**kwargs: Any) -> dict:
    """Diagnose why CPM is high — checks audience size, placement, frequency, creative fatigue.

    Returns actionable recommendations.
    """
    date_range = kwargs.get("date_range", "last_7d")
    if not _get_token():
        return _mock_response("Diagnose high CPM: would analyze audience overlap, frequency, placement performance")

    # Get account insights with breakdowns
    placement_data = await _api_get(
        f"act_{_get_account_id()}/insights",
        {
            "fields": "spend,impressions,cpm,ctr,clicks,frequency,reach",
            "time_range": str(_date_range(date_range)),
            "level": "adset",
            "breakdowns": "publisher_platform,platform_position",
        },
    )

    # Get campaign-level for frequency analysis
    campaign_data = await _api_get(
        f"act_{_get_account_id()}/insights",
        {
            "fields": "campaign_name,spend,impressions,cpm,frequency,reach",
            "time_range": str(_date_range(date_range)),
            "level": "campaign",
        },
    )

    recommendations = []
    issues = []

    for row in campaign_data.get("data", []):
        freq = float(row.get("frequency", 0))
        cpm = float(row.get("cpm", 0))
        name = row.get("campaign_name", "Unknown")

        if freq > 3:
            issues.append(f"Campaign '{name}' has frequency {freq:.1f} — audience is oversaturated")
            recommendations.append(f"Expand audience or pause '{name}' — frequency > 3 means ad fatigue")
        if cpm > 20:
            issues.append(f"Campaign '{name}' CPM is ${cpm:.2f} — significantly above average")
            recommendations.append(f"Test broader targeting or new creatives for '{name}'")

    # Check placement CPM variance
    placement_cpms = {}
    for row in placement_data.get("data", []):
        platform = row.get("publisher_platform", "unknown")
        position = row.get("platform_position", "unknown")
        key = f"{platform}/{position}"
        placement_cpms[key] = float(row.get("cpm", 0))

    if placement_cpms:
        avg_cpm = sum(placement_cpms.values()) / len(placement_cpms)
        for placement, cpm in sorted(placement_cpms.items(), key=lambda x: x[1], reverse=True):
            if cpm > avg_cpm * 2:
                issues.append(f"Placement '{placement}' CPM ${cpm:.2f} is 2x+ above average ${avg_cpm:.2f}")
                recommendations.append(f"Consider excluding '{placement}' from placements")

    if not recommendations:
        recommendations.append("CPM looks normal. Focus on CTR and conversion rate instead.")

    return {
        "date_range": date_range,
        "issues": issues,
        "recommendations": recommendations,
        "placement_cpms": placement_cpms,
        "campaign_data": campaign_data.get("data", []),
    }


async def facebook_diagnose_zero_conversions(**kwargs: Any) -> dict:
    """Diagnose why there are zero conversions — checks pixel, targeting, funnel.

    This is the tool for "I spent 17K INR and got 0 conversions".
    """
    date_range = kwargs.get("date_range", "last_30d")
    if not _get_token():
        return _mock_response(
            "Diagnose zero conversions: would check pixel events, targeting mismatch, "
            "landing page alignment, and funnel drop-off"
        )

    # Account overview
    overview = await facebook_get_account_overview(date_range=date_range)
    summary = overview.get("summary", {})

    # Campaign-level insights to find which campaign is the problem
    campaign_data = await _api_get(
        f"act_{_get_account_id()}/insights",
        {
            "fields": "campaign_name,spend,impressions,clicks,ctr,cpc,cpm,actions,cost_per_action_type",
            "time_range": str(_date_range(date_range)),
            "level": "campaign",
        },
    )

    # Check pixel events
    pixel_data = {}
    try:
        pixels = await _api_get(
            f"act_{_get_account_id()}/adspixels",
            {"fields": "name,id,last_fired_time,is_unavailable"},
        )
        pixel_data = pixels
    except Exception as e:
        pixel_data = {"error": str(e)}

    diagnosis = []
    recommendations = []

    # Check if pixel is firing
    pixels_list = pixel_data.get("data", [])
    if not pixels_list:
        diagnosis.append("NO PIXEL FOUND — conversions cannot be tracked without a Meta Pixel")
        recommendations.append("Install Meta Pixel on your landing page and conversion/thank-you page")
    else:
        for px in pixels_list:
            if px.get("is_unavailable"):
                diagnosis.append(f"Pixel '{px.get('name')}' is marked UNAVAILABLE")
                recommendations.append("Check pixel installation — it may not be firing correctly")
            last_fired = px.get("last_fired_time")
            if not last_fired:
                diagnosis.append(f"Pixel '{px.get('name')}' has NEVER fired")
                recommendations.append("Verify pixel is installed correctly on your website")

    # Check clicks vs conversions gap
    clicks = summary.get("clicks", 0)
    conversions = summary.get("conversions", 0)
    spend = summary.get("spend", 0)

    if clicks == 0:
        diagnosis.append(f"ZERO CLICKS with ${spend} spend — ads are not engaging")
        recommendations.append("Your creative/copy needs a complete overhaul")
        recommendations.append("Test video ads, carousel, or user-generated content")
    elif clicks > 0 and conversions == 0:
        diagnosis.append(
            f"{clicks} clicks but ZERO conversions — traffic is reaching your site but not converting"
        )
        recommendations.append("Your landing page is the problem, not the ads")
        recommendations.append("Check: page load speed, mobile responsiveness, clear CTA above fold")
        recommendations.append("Check: price point, trust signals (reviews, guarantees), value proposition clarity")
        recommendations.append("Add a conversion pixel on your purchase/signup page if missing")

    # Check CTR
    ctr = summary.get("ctr", 0)
    if 0 < ctr < 0.005:
        diagnosis.append(f"CTR is very low ({ctr*100:.2f}%) — ads are not resonating with audience")
        recommendations.append("Test completely different creatives — before/after photos, testimonials, UGC")
        recommendations.append("Narrow targeting to people who recently searched for headshots")

    # Check CPM
    cpm = summary.get("cpm", 0)
    if cpm > 15:
        diagnosis.append(f"CPM is high (${cpm:.2f}) — you're paying too much per 1000 impressions")
        recommendations.append("Broaden audience slightly to reduce competition")
        recommendations.append("Test Instagram Reels / Stories placements (usually cheaper CPM)")

    return {
        "date_range": date_range,
        "account_summary": summary,
        "pixel_status": pixel_data,
        "campaign_breakdown": campaign_data.get("data", []),
        "diagnosis": diagnosis,
        "recommendations": recommendations,
        "severity": "critical" if conversions == 0 and spend > 0 else "warning",
    }


# ──────────────────────────────────────────────────────────────────
# 5. CREATIVE: Creative performance reports and ad copy generation
# ──────────────────────────────────────────────────────────────────


async def facebook_creative_report(**kwargs: Any) -> dict:
    """Aggregate performance by creative across all campaigns.

    Groups ads by creative (image_url hash), sorts by CTR and ROAS,
    and assigns a performance grade (A/B/C/F) to each.

    Args:
        date_range: today, yesterday, last_3d, last_7d, last_14d, last_30d, last_90d
    """
    date_range = kwargs.get("date_range", "last_7d")

    if not _get_token():
        return _mock_response(
            f"Creative report ({date_range}): aggregated performance by creative — "
            f"CTR, CPM, ROAS, spend per creative with A/B/C/F grades"
        )

    # 1. Get all ads with creative details
    ads_response = await _api_get(
        f"act_{_get_account_id()}/ads",
        {
            "fields": "id,name,status,creative{title,body,image_url,thumbnail_url,link_url}",
            "effective_status": '["ACTIVE","PAUSED"]',
            "limit": "200",
        },
    )
    ads_list = ads_response.get("data", [])

    # 2. Get insights for each ad
    ad_insights = await _api_get(
        f"act_{_get_account_id()}/insights",
        {
            "fields": (
                "ad_id,ad_name,spend,impressions,clicks,ctr,cpm,"
                "actions,cost_per_action_type,action_values"
            ),
            "time_range": str(_date_range(date_range)),
            "level": "ad",
            "limit": "200",
        },
    )

    # Build a lookup: ad_id -> creative details
    creative_lookup: dict[str, dict] = {}
    for ad in ads_list:
        ad_id = ad.get("id", "")
        creative = ad.get("creative", {})
        creative_lookup[ad_id] = {
            "ad_name": ad.get("name", ""),
            "creative_title": creative.get("title", ""),
            "creative_body": creative.get("body", ""),
            "image_url": creative.get("image_url", ""),
        }

    # 3. Merge insights with creative details and compute metrics
    creatives: list[dict] = []
    for row in ad_insights.get("data", []):
        ad_id = row.get("ad_id", "")
        spend = float(row.get("spend", 0))
        impressions = int(row.get("impressions", 0))
        clicks = int(row.get("clicks", 0))
        ctr = float(row.get("ctr", 0))
        cpm = float(row.get("cpm", 0))

        # Extract conversions from actions
        conversions = 0
        for action in row.get("actions", []):
            if action.get("action_type") in (
                "purchase", "offsite_conversion.fb_pixel_purchase",
                "lead", "complete_registration",
            ):
                conversions += int(action.get("value", 0))

        # Extract revenue from action_values
        revenue = 0.0
        for av in row.get("action_values", []):
            if av.get("action_type") in (
                "purchase", "offsite_conversion.fb_pixel_purchase",
            ):
                revenue += float(av.get("value", 0))
        roas = round(revenue / spend, 2) if spend > 0 else 0.0

        # Performance grade: A (top), B (above avg), C (below avg), F (losing money)
        if roas >= 3.0 or (ctr >= 0.02 and conversions > 0):
            grade = "A"
        elif ctr >= 0.01 and (roas >= 1.0 or conversions > 0):
            grade = "B"
        elif ctr >= 0.005 or impressions < 500:
            grade = "C"
        else:
            grade = "F"

        creative_info = creative_lookup.get(ad_id, {})
        image_url = creative_info.get("image_url", "")

        creatives.append({
            "ad_id": ad_id,
            "ad_name": creative_info.get("ad_name", row.get("ad_name", "")),
            "creative_title": creative_info.get("creative_title", ""),
            "creative_body": creative_info.get("creative_body", ""),
            "image_url": image_url,
            "image_hash": hashlib.md5(image_url.encode()).hexdigest()[:8] if image_url else "",
            "spend": round(spend, 2),
            "impressions": impressions,
            "clicks": clicks,
            "ctr": round(ctr, 4),
            "cpm": round(cpm, 2),
            "conversions": conversions,
            "roas": roas,
            "performance_grade": grade,
        })

    # 4. Sort by CTR descending, then by ROAS descending
    creatives.sort(key=lambda c: (c["ctr"], c["roas"]), reverse=True)

    return {
        "date_range": date_range,
        "total_creatives": len(creatives),
        "creatives": creatives,
        "grade_summary": {
            "A": sum(1 for c in creatives if c["performance_grade"] == "A"),
            "B": sum(1 for c in creatives if c["performance_grade"] == "B"),
            "C": sum(1 for c in creatives if c["performance_grade"] == "C"),
            "F": sum(1 for c in creatives if c["performance_grade"] == "F"),
        },
    }


def facebook_generate_ad_copy(**kwargs: Any) -> dict:
    """Generate ad copy variations from proven direct-response templates.

    This does NOT call an LLM — it returns structured templates populated
    with the provided product and audience details.

    Args:
        product: Product description (e.g. "AI headshot generator for professionals")
        audience: Target audience (e.g. "US professionals, LinkedIn users, job seekers")
        style: Template style — direct_response, social_proof, urgency, benefit_led, problem_agitation
        count: Number of variations to return (default 5, max 10)
    """
    product = kwargs.get("product", "AI headshot generator for professionals")
    audience = kwargs.get("audience", "US professionals, LinkedIn users, job seekers")
    style = kwargs.get("style", "direct_response")
    count = min(int(kwargs.get("count", 5)), 10)

    # ── Template library: proven direct-response patterns ──

    templates: dict[str, list[dict]] = {
        "direct_response": [
            {
                "headline": f"Get a Professional Headshot in 60 Seconds",
                "primary_text": f"No studio. No photographer. No $300 bill. Upload a selfie and get a studio-quality professional headshot powered by AI. Perfect for {audience}.",
                "description": "AI-powered headshots — ready in minutes, not days.",
                "cta": "SIGN_UP",
                "rationale": "Leads with speed (60 seconds) and removes friction (no studio needed). Direct CTA.",
            },
            {
                "headline": f"Your LinkedIn Photo Is Costing You Interviews",
                "primary_text": f"Recruiters spend 7 seconds on your profile. A professional headshot increases InMail responses by 36%. Get yours with AI — no photoshoot required.",
                "description": "Professional headshots from your selfie. Try it free.",
                "cta": "SIGN_UP",
                "rationale": "Pain point (missed interviews) + specific stat (36% increase) + low friction.",
            },
            {
                "headline": f"Professional Headshots Starting at $29",
                "primary_text": f"Studio headshots cost $200-$500 and take a full afternoon. Get the same quality from a selfie in under 2 minutes. Trusted by 10,000+ professionals across the US.",
                "description": "AI headshots — fraction of the cost, fraction of the time.",
                "cta": "GET_OFFER",
                "rationale": "Price anchoring ($200-500 vs $29) + time saving + social proof (10K users).",
            },
            {
                "headline": f"Stop Using That 5-Year-Old Headshot",
                "primary_text": f"Your professional image matters. Get a fresh, AI-generated headshot that looks like you hired a photographer — because the AI was trained on studio photography.",
                "description": "Modern headshots for modern professionals.",
                "cta": "SIGN_UP",
                "rationale": "Calls out a common behavior (outdated photo) and positions AI as professional-grade.",
            },
            {
                "headline": f"Upload a Selfie. Get a Headshot. It's That Simple.",
                "primary_text": f"No scheduling. No awkward posing. No waiting. Just upload your best selfie and let AI create a polished professional headshot in minutes. Join thousands of {audience} who already upgraded.",
                "description": "The fastest way to a professional headshot.",
                "cta": "SIGN_UP",
                "rationale": "Simplicity messaging. Removes every objection (scheduling, posing, waiting).",
            },
        ],
        "social_proof": [
            {
                "headline": f"10,000+ Professionals Trust AI for Their Headshots",
                "primary_text": f"Join consultants, realtors, and executives across the US who replaced their $300 photoshoot with an AI headshot. Same quality. 1/10th the price.",
                "description": "See why professionals are switching to AI headshots.",
                "cta": "LEARN_MORE",
                "rationale": "Social proof (10K users) + specific professions the audience relates to.",
            },
            {
                "headline": f"\"Best $29 I Ever Spent on My Career\"",
                "primary_text": f"That's what Sarah, a marketing manager in NYC, said after getting her AI headshot. She landed 3 interviews in the first week with her new LinkedIn photo.",
                "description": "Real results from real professionals.",
                "cta": "SIGN_UP",
                "rationale": "Testimonial format with specific result (3 interviews). Relatable persona.",
            },
            {
                "headline": f"Why Fortune 500 Employees Are Using AI Headshots",
                "primary_text": f"When your company doesn't offer headshot sessions, you make your own. AI headshots look studio-professional and take 2 minutes. No photographer needed.",
                "description": "Professional headshots for every employee.",
                "cta": "LEARN_MORE",
                "rationale": "Authority transfer (Fortune 500) + practical use case for corporate professionals.",
            },
            {
                "headline": f"Rated 4.8/5 by 3,000+ Users",
                "primary_text": f"Professionals across the US are choosing AI headshots over expensive photoshoots. Upload a selfie, pick your style, and download your headshot. It's that easy.",
                "description": "Top-rated AI headshot generator.",
                "cta": "SIGN_UP",
                "rationale": "Rating as social proof (4.8/5) + volume (3000 users) + simple process.",
            },
            {
                "headline": f"The Headshot Hack LinkedIn Experts Recommend",
                "primary_text": f"Career coaches are telling clients to get AI headshots instead of booking expensive photoshoots. Professional quality, ready in minutes, updated whenever you want.",
                "description": "Expert-recommended professional headshots.",
                "cta": "LEARN_MORE",
                "rationale": "Authority endorsement (career coaches) + positions as an insider tip.",
            },
        ],
        "urgency": [
            {
                "headline": f"Job Market Is Moving Fast. Is Your Headshot Ready?",
                "primary_text": f"Hiring managers are scrolling past profiles with bad photos. Get a professional AI headshot in 2 minutes — before your next opportunity passes you by.",
                "description": "Don't let your photo hold you back.",
                "cta": "SIGN_UP",
                "rationale": "FOMO (job market moving fast) + time pressure (before next opportunity).",
            },
            {
                "headline": f"Your Competitors Already Upgraded Their Headshot",
                "primary_text": f"In a competitive job market, first impressions are everything. Get an AI-powered professional headshot today — while the introductory pricing lasts.",
                "description": "Professional headshots at launch pricing.",
                "cta": "GET_OFFER",
                "rationale": "Competitive pressure + scarcity (introductory pricing).",
            },
            {
                "headline": f"New Year, New Headshot — AI Makes It Instant",
                "primary_text": f"Start the quarter with a fresh professional image. AI headshots are ready in minutes — no appointment needed. Limited-time offer for new users.",
                "description": "Refresh your professional image today.",
                "cta": "GET_OFFER",
                "rationale": "Seasonal urgency + limited-time framing for new users.",
            },
            {
                "headline": f"Still Using a Cropped Group Photo as Your Headshot?",
                "primary_text": f"You have 7 seconds to make an impression on LinkedIn. A pixelated crop isn't cutting it. Get a clean, professional AI headshot right now — takes 60 seconds.",
                "description": "Upgrade your headshot in under a minute.",
                "cta": "SIGN_UP",
                "rationale": "Calls out embarrassing behavior + specific stat (7 seconds) + instant solution.",
            },
            {
                "headline": f"This Week Only: Professional Headshots for $19",
                "primary_text": f"We're running a limited promotion for {audience}. Get studio-quality AI headshots for the price of lunch. Upload a selfie, choose your background, download in minutes.",
                "description": "Limited-time headshot deal.",
                "cta": "GET_OFFER",
                "rationale": "Hard deadline + price anchor (price of lunch) + clear process.",
            },
        ],
        "benefit_led": [
            {
                "headline": f"Look Like You Hired a Photographer (You Didn't)",
                "primary_text": f"AI headshots that fool everyone. Professional lighting, perfect background, natural expression — all generated from a single selfie. Ready in minutes.",
                "description": "Studio-quality headshots without the studio.",
                "cta": "SIGN_UP",
                "rationale": "Aspirational outcome (look professional) + reveal twist (AI, not photographer).",
            },
            {
                "headline": f"Get 40+ Headshot Variations From One Selfie",
                "primary_text": f"Different backgrounds, outfits, and styles — all from one upload. Pick your favorites and download instantly. Perfect for LinkedIn, company bios, and speaker profiles.",
                "description": "One selfie, unlimited professional looks.",
                "cta": "SIGN_UP",
                "rationale": "Volume benefit (40+ variations) + specific use cases the audience needs.",
            },
            {
                "headline": f"Save $270 on Your Next Professional Headshot",
                "primary_text": f"The average US headshot photoshoot costs $299. Get the same result for a fraction of the price with AI. No scheduling, no commute, no awkward small talk with a photographer.",
                "description": "Professional headshots from $29.",
                "cta": "GET_OFFER",
                "rationale": "Savings-first ($270 saved) + eliminates all pain points of traditional photoshoots.",
            },
            {
                "headline": f"Update Your Headshot Anytime You Want",
                "primary_text": f"New haircut? New glasses? New job? Generate a fresh professional headshot whenever you need one. No rescheduling a photographer — just upload and go.",
                "description": "Always-current professional headshots.",
                "cta": "SIGN_UP",
                "rationale": "Recurring benefit (anytime updates) vs one-time photoshoot.",
            },
            {
                "headline": f"The Headshot That Gets You Noticed",
                "primary_text": f"Profiles with professional headshots get 14x more views on LinkedIn. Don't leave your career to chance — get a polished AI headshot in 2 minutes.",
                "description": "Stand out with a professional headshot.",
                "cta": "SIGN_UP",
                "rationale": "Specific stat (14x views) ties headshot directly to career outcomes.",
            },
        ],
        "problem_agitation": [
            {
                "headline": f"Bad Headshot = Missed Opportunities",
                "primary_text": f"Recruiters judge you in 7 seconds. A blurry selfie or outdated photo tells them you don't take your career seriously. Fix it in 60 seconds with AI-generated professional headshots.",
                "description": "First impressions matter. Make yours count.",
                "cta": "SIGN_UP",
                "rationale": "Problem (bad photo) → agitation (recruiters judging) → solution (AI headshot).",
            },
            {
                "headline": f"You're Losing Jobs Because of Your LinkedIn Photo",
                "primary_text": f"A study found that profiles with professional headshots receive 36% more InMail messages. If you're job hunting without one, you're invisible. Get an AI headshot in minutes.",
                "description": "Stop being invisible to recruiters.",
                "cta": "SIGN_UP",
                "rationale": "Direct pain statement + research backing + simple solution.",
            },
            {
                "headline": f"$300 for a Headshot? There's a Better Way.",
                "primary_text": f"Booking a photographer means scheduling, commuting, posing for an hour, waiting a week for edits, and paying $200-$500. Or: upload a selfie and get AI headshots in 2 minutes for $29.",
                "description": "Skip the photoshoot. Get AI headshots.",
                "cta": "GET_OFFER",
                "rationale": "Problem (expensive/time-consuming) agitated with detail → elegant solution.",
            },
            {
                "headline": f"Nobody Wants to Sit Through a Headshot Session",
                "primary_text": f"The forced smile. The weird poses. The photographer saying \"relax\" while you feel anything but. Skip all of it. Upload a selfie, let AI handle the rest. Done in 2 minutes.",
                "description": "Professional headshots without the awkwardness.",
                "cta": "SIGN_UP",
                "rationale": "Emotional agitation (awkwardness of photoshoots) makes AI feel like relief.",
            },
            {
                "headline": f"Your Headshot Is Older Than Your Job Title",
                "primary_text": f"If your headshot is from 2019 but your resume says 2024, something doesn't add up. Recruiters notice. Update your professional image in under 2 minutes with AI.",
                "description": "Keep your professional image current.",
                "cta": "SIGN_UP",
                "rationale": "Specific relatable problem (outdated photo) + credibility gap + easy fix.",
            },
        ],
    }

    # Fallback if style not found
    selected_templates = templates.get(style, templates["direct_response"])

    # Return requested count
    results = selected_templates[:count]

    return {
        "product": product,
        "audience": audience,
        "style": style,
        "count": len(results),
        "ad_copies": results,
    }
