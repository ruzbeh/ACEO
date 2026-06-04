"""Upload an already-rendered reel to YouTube as a Short (no re-render).

Defaults to the newest workspace/content/output/science-*.mp4 so we publish the
exact file we verified, without spending another render/VO pass.

Requires YOUTUBE_OAUTH_* in .env (mint with scripts/youtube_oauth.py).

Usage:
    .venv/bin/python scripts/upload_to_youtube.py \
        --title "Could a single amino acid slow aging?" --privacy unlisted
"""
from __future__ import annotations

import argparse
import asyncio
import glob
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from aeco.tools.content.youtube_publisher import YouTubeError, upload_short  # noqa: E402

DEFAULT_TITLE = "Could a single amino acid slow aging? #Shorts"
DEFAULT_DESCRIPTION = (
    "A daily 60-second science drop on supplements and medical discoveries.\n"
    "Educational only — not medical advice. Sources cited on screen.\n"
)
DEFAULT_TAGS = ["science", "longevity", "supplements", "health", "shorts"]


def _latest_reel() -> str:
    matches = sorted(
        glob.glob(str(REPO_ROOT / "workspace" / "content" / "output" / "science-*.mp4"))
    )
    if not matches:
        sys.exit("No rendered reel found in workspace/content/output/. Render one first.")
    return matches[-1]


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", help="MP4 to upload (default: newest science-*.mp4)")
    ap.add_argument("--title", default=DEFAULT_TITLE)
    ap.add_argument("--description", default=DEFAULT_DESCRIPTION)
    ap.add_argument("--privacy", default="unlisted", choices=["private", "unlisted", "public"])
    args = ap.parse_args()

    mp4 = args.file or _latest_reel()
    print(f"Uploading: {mp4}\n  title:   {args.title}\n  privacy: {args.privacy}")
    try:
        res = await upload_short(
            mp4,
            title=args.title,
            description=args.description,
            tags=DEFAULT_TAGS,
            privacy=args.privacy,
        )
    except YouTubeError as e:
        sys.exit(f"\n✗ Upload failed: {e}")

    print("\n" + "=" * 60)
    print("✓ Uploaded to YouTube")
    print(f"  Video ID:  {res['id']}")
    print(f"  Watch URL: {res['watch_url']}")
    print(f"  Privacy:   {args.privacy}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
