"""Pull FB campaign/ad performance + fresh GA funnel."""
import asyncio, json
from aeco.tools.facebook_tools import (
    facebook_get_insights, facebook_get_campaigns, facebook_get_ads,
    facebook_get_account_overview,
)
from aeco.tools.ga_tools import ga_funnel_report, ga_user_journey, ga_realtime


async def main():
    # FB — use supported date_range tokens only
    account_7 = await facebook_get_account_overview(date_range="last_7d")
    account_30 = await facebook_get_account_overview(date_range="last_30d")
    campaigns_7 = await facebook_get_insights(date_range="last_7d", level="campaign")
    campaigns_30 = await facebook_get_insights(date_range="last_30d", level="campaign")
    ads_7 = await facebook_get_insights(date_range="last_7d", level="ad")
    ads_30 = await facebook_get_insights(date_range="last_30d", level="ad")

    # GA — fresh funnel
    funnel_7 = await ga_funnel_report(days=7)
    funnel_1 = await ga_funnel_report(days=1)
    events_7 = await ga_user_journey(days=7)
    events_1 = await ga_user_journey(days=1)
    realtime = await ga_realtime()

    out = {
        "fb_account_7d": account_7,
        "fb_account_30d": account_30,
        "fb_campaigns_7d": campaigns_7,
        "fb_campaigns_30d": campaigns_30,
        "fb_ads_7d": ads_7,
        "fb_ads_30d": ads_30,
        "ga_funnel_7d": funnel_7,
        "ga_funnel_1d": funnel_1,
        "ga_events_7d": events_7,
        "ga_events_1d": events_1,
        "ga_realtime": realtime,
    }
    print(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())
