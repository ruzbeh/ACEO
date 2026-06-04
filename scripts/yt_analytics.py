"""Pull YouTube performance for The Science Drop.

Reads two sources with the OAuth refresh token in .env:
  • Data API v3      — channel totals + per-video public stats (views / likes)
  • YouTube Analytics — watch-time + average-view-% (retention) per video

The stored token must carry youtube.readonly + yt-analytics.readonly scopes. If
you only ever ran the upload flow, re-mint it first (the oauth helper now asks
for read+analytics too):
    .venv/bin/python scripts/youtube_oauth.py \\
        --client-id "$(grep ^YOUTUBE_OAUTH_CLIENT_ID .env | cut -d= -f2)" \\
        --client-secret "$(grep ^YOUTUBE_OAUTH_CLIENT_SECRET .env | cut -d= -f2)"
then paste the new YOUTUBE_OAUTH_REFRESH_TOKEN into .env.

Usage:
    .venv/bin/python scripts/yt_analytics.py [--days 30]
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_API = "https://www.googleapis.com/youtube/v3/"
ANALYTICS_API = "https://youtubeanalytics.googleapis.com/v2/reports"


def _load_env() -> dict:
    env: dict[str, str] = {}
    for line in (REPO_ROOT / ".env").read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k] = v.strip().strip('"').strip("'")
    return env


def _access_token(env: dict) -> str:
    body = urllib.parse.urlencode({
        "client_id": env["YOUTUBE_OAUTH_CLIENT_ID"],
        "client_secret": env["YOUTUBE_OAUTH_CLIENT_SECRET"],
        "refresh_token": env["YOUTUBE_OAUTH_REFRESH_TOKEN"],
        "grant_type": "refresh_token",
    }).encode()
    req = urllib.request.Request("https://oauth2.googleapis.com/token", data=body)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)["access_token"]
    except urllib.error.HTTPError as e:
        sys.exit(f"Token refresh failed ({e.code}): {e.read().decode()[:300]}")


def _get(url: str, token: str):
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        detail = e.read().decode()[:300]
        if e.code == 403 and "scope" in detail.lower():
            sys.exit(
                "403 insufficient scope — the refresh token is upload-only.\n"
                "Re-mint it with scripts/youtube_oauth.py (it now requests read + "
                "analytics), paste the new YOUTUBE_OAUTH_REFRESH_TOKEN into .env, retry."
            )
        print(f"HTTP {e.code} on {url.split('?')[0]}: {detail}", file=sys.stderr)
        return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=30, help="analytics window (default 30)")
    args = ap.parse_args()

    env = _load_env()
    token = _access_token(env)

    ch = _get(DATA_API + "channels?" + urllib.parse.urlencode(
        {"part": "contentDetails,statistics,snippet", "mine": "true"}), token)
    if not ch or not ch.get("items"):
        sys.exit("Could not read channel (see error above).")
    c = ch["items"][0]
    st = c["statistics"]
    print("=" * 70)
    print(f"CHANNEL  {c['snippet']['title']}   (id {c['id']})")
    print(f"  subscribers {st.get('subscriberCount','?')}   "
          f"total views {st.get('viewCount','?')}   videos {st.get('videoCount','?')}")
    print("=" * 70)

    uploads = c["contentDetails"]["relatedPlaylists"]["uploads"]
    vids: list[str] = []
    page = None
    while True:
        pl = _get(DATA_API + "playlistItems?" + urllib.parse.urlencode(
            {"part": "contentDetails", "playlistId": uploads, "maxResults": 50,
             **({"pageToken": page} if page else {})}), token)
        if not pl:
            break
        vids += [it["contentDetails"]["videoId"] for it in pl["items"]]
        page = pl.get("nextPageToken")
        if not page:
            break

    meta: dict[str, dict] = {}
    for i in range(0, len(vids), 50):
        v = _get(DATA_API + "videos?" + urllib.parse.urlencode(
            {"part": "snippet,statistics,status", "id": ",".join(vids[i:i + 50])}), token)
        if not v:
            continue
        for it in v["items"]:
            s = it["statistics"]
            meta[it["id"]] = {
                "title": it["snippet"]["title"],
                "published": it["snippet"]["publishedAt"][:16],
                "privacy": it["status"]["privacyStatus"],
                "views": int(s.get("viewCount", 0)),
                "likes": int(s.get("likeCount", 0)),
            }

    # Analytics API: per-video watch-time + retention over the window.
    end = date.today()
    start = end - timedelta(days=args.days)
    a = _get(ANALYTICS_API + "?" + urllib.parse.urlencode({
        "ids": "channel==MINE",
        "startDate": start.isoformat(),
        "endDate": end.isoformat(),
        "metrics": "views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage",
        "dimensions": "video",
        "sort": "-views",
        "maxResults": 200,
    }), token)
    retention: dict[str, dict] = {}
    if a and a.get("rows"):
        for vid, views, mins, avgdur, avgpct in a["rows"]:
            retention[vid] = {"mins": mins, "avgdur": avgdur, "avgpct": avgpct}

    print(f"\nPER-VIDEO  (analytics window {start} → {end})\n")
    print(f"  {'published':16}  {'priv':8} {'views':>6} {'likes':>5} {'watch-min':>9} {'avg-view%':>9}  title")
    for vid in sorted(meta, key=lambda k: meta[k]["published"]):
        m = meta[vid]
        r = retention.get(vid, {})
        pct = f"{r['avgpct']:.0f}%" if "avgpct" in r else "—"
        mins = f"{r['mins']:.0f}" if "mins" in r else "—"
        print(f"  {m['published']:16}  {m['privacy']:8} {m['views']:>6} {m['likes']:>5} "
              f"{mins:>9} {pct:>9}  {m['title'][:46]}")
    print(f"\n  {len(meta)} videos · {sum(m['views'] for m in meta.values())} total views")
    if not retention:
        print("  (no analytics rows yet — channel is new; YouTube needs ~48h + traffic to populate.)")


if __name__ == "__main__":
    main()
