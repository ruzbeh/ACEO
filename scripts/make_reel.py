"""End-to-end: take a set of images + brief → render a reel → (optional) upload to FB.

Usage:
    python scripts/make_reel.py --before path/to/before.jpg --after a.jpg b.jpg c.jpg d.jpg [--upload]

Phase 1: Remotion composition only (Ken Burns, captions, music bed). No paid APIs.
Phase 2 will swap the Ken Burns clips for Runway img2vid outputs.
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import logging
import mimetypes
import shutil
from pathlib import Path

from aeco.tools.video import (
    ReelScript,
    render_reel,
    upload_video_to_facebook,
    create_video_ad,
    write_scripts,
)


def _to_data_uri(path: Path) -> str:
    """Base64-encode an image as a data: URI so Remotion loads it inline
    without relying on the bundled public/ server (which caches at build time)."""
    mime, _ = mimetypes.guess_type(str(path))
    mime = mime or "image/jpeg"
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{data}"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("make_reel")


AECO_ROOT = Path(__file__).resolve().parents[1]
RENDERER_DIR = AECO_ROOT / "video_renderer"
RENDERER_PUBLIC = RENDERER_DIR / "public" / "reel_assets"

# The Registration adset is the current winner (from earlier FB insights analysis)
DEFAULT_ADSET_ID = "120243930512770566"
DEFAULT_PAGE_ID = "1091699287351335"
DEFAULT_LINK = "https://www.headshot-generators.com/lp"


def _stage_assets(before: Path, afters: list[Path]) -> tuple[str, list[str]]:
    """Encode images as base64 data URIs and pass them as props.
    This side-steps Remotion's bundle-time public/ cache — we embed the bytes
    directly so the browser decodes them without a network fetch.
    """
    return _to_data_uri(before), [_to_data_uri(a) for a in afters]


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", required=True, help="Path to the 'before' selfie")
    ap.add_argument("--after", nargs="+", required=True, help="3-6 after-headshot paths")
    ap.add_argument("--output", default=str(AECO_ROOT / "workspace" / "reel.mp4"))
    ap.add_argument("--brief", default="Headshot AI — 8 pro headshots in 2 min for $19")
    ap.add_argument("--adset-id", default=DEFAULT_ADSET_ID)
    ap.add_argument("--page-id", default=DEFAULT_PAGE_ID)
    ap.add_argument("--link", default=DEFAULT_LINK)
    ap.add_argument("--upload", action="store_true", help="Upload to FB as a PAUSED ad")
    ap.add_argument("--n-scripts", type=int, default=1)
    args = ap.parse_args()

    before = Path(args.before).resolve()
    afters = [Path(a).resolve() for a in args.after]
    if not before.exists():
        raise FileNotFoundError(before)
    for a in afters:
        if not a.exists():
            raise FileNotFoundError(a)

    logger.info("Staging %d after images into %s", len(afters), RENDERER_PUBLIC)
    before_public, after_public = _stage_assets(before, afters)

    logger.info("Writing script (n=%d) ...", args.n_scripts)
    scripts = await write_scripts(brief=args.brief, n=args.n_scripts)
    script: ReelScript = scripts[0]
    logger.info("Script: headline=%r  sub=%r  cta=%r", script.headline, script.subheadline, script.cta_text)

    props = script.to_props(before_image=before_public, after_images=after_public)

    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    logger.info("Rendering reel → %s", output)
    result = await render_reel(composition="BeforeAfterReel", props=props, output_path=str(output))
    logger.info("Rendered OK (%.1fs): %s", result.duration_sec or 0, result.path)

    if not args.upload:
        print(f"\n✓ Reel written to: {result.path}")
        print("   Preview locally:  open {result.path}" if False else f"   open {result.path}")
        return

    logger.info("Uploading to Facebook ...")
    upload = await upload_video_to_facebook(result.path, name=f"AECO Reel · {script.headline}")
    logger.info("Upload status=%s video_id=%s", upload["status"], upload["id"])

    ad = await create_video_ad(
        video_id=upload["id"],
        adset_id=args.adset_id,
        page_id=args.page_id,
        ad_name=f"Reel V1 · {script.headline[:40]}",
        message=(
            f"{script.problem_caption or 'Your LinkedIn photo is the first thing recruiters see.'}\n\n"
            f"Upload a selfie. Get 8 studio-quality headshots in 2 minutes — for $19.\n"
            f"→ Free preview. Money-back guarantee."
        ),
        headline=script.headline,
        description=script.subheadline,
        link=args.link,
    )
    print("\n" + "=" * 60)
    print("✓ Reel rendered + uploaded as PAUSED ad")
    print("=" * 60)
    print(f"Local MP4:    {result.path}")
    print(f"Video ID:     {ad['video_id']}")
    print(f"Creative ID:  {ad['creative_id']}")
    print(f"Ad ID:        {ad['ad_id']}")
    print(f"Status:       {ad['status']}")
    print(f"Review here:  {ad['ads_manager_url']}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
