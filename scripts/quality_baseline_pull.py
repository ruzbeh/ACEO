"""Pull GA4 baseline data for Headshot AI quality audit (2026-04-14).

Outputs JSON to stdout. Run from repo root with .venv/bin/python.
"""
import asyncio
import json

from aeco.tools.ga_tools import (
    ga_funnel_report,
    ga_device_report,
    ga_traffic_sources,
    ga_user_journey,
    ga_realtime,
)


async def main() -> None:
    # 28-day window for the funnel/journey to smooth weekly noise;
    # 7-day for device/traffic to reflect current mix.
    funnel_28 = await ga_funnel_report(days=28)
    funnel_7 = await ga_funnel_report(days=7)
    devices = await ga_device_report(days=28)
    traffic = await ga_traffic_sources(days=28)
    journey_28 = await ga_user_journey(days=28)
    journey_7 = await ga_user_journey(days=7)
    realtime = await ga_realtime()

    out = {
        "funnel_28d": funnel_28,
        "funnel_7d": funnel_7,
        "devices_28d": devices,
        "traffic_28d": traffic,
        "events_28d": journey_28,
        "events_7d": journey_7,
        "realtime": realtime,
    }
    print(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())
