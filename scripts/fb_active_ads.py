"""Pull active FB ad creatives + recent insights for Headshot AI."""
import asyncio, json
from aeco.tools.facebook_tools import facebook_get_ads, facebook_get_insights, facebook_get_campaigns


async def main():
    campaigns = await facebook_get_campaigns()
    ads = await facebook_get_ads()
    print(json.dumps({"campaigns": campaigns, "ads": ads}, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())
