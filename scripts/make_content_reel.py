"""Make a faceless science-news reel end-to-end and (optionally) upload to YouTube.

Pipeline:
    script (default or --script-file)
      -> ElevenLabs voiceover per segment   (timing drives caption sync)
      -> Remotion ScienceNewsReel render     (kinetic typography + VO)
      -> [optional] YouTube Shorts upload

Run with a Node 18+ on PATH (Remotion 4 requires it), e.g.:
    PATH="$HOME/.nvm/versions/node/v22.22.1/bin:$PATH" \
      .venv/bin/python scripts/make_content_reel.py --upload

Flags:
    --no-vo            render silent (skip ElevenLabs) — fast smoke test
    --voice NAME       ElevenLabs preset (default male_deep)
    --script-file F    JSON: {"segments":[{"text","durationSec","source"}], ...}
    --upload           upload the rendered MP4 to YouTube after rendering
    --privacy P        private | unlisted | public   (default unlisted)
    --output PATH      where to write the MP4
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from aeco.tools.video.composer import render_reel  # noqa: E402
from aeco.tools.video.voiceover import (  # noqa: E402
    ElevenLabsError,
    measure_mp3_duration,
    text_to_speech,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("make_content_reel")

OUTPUT_DIR = REPO_ROOT / "workspace" / "content" / "output"

# A real, carefully-hedged science story (taurine & aging — Singh et al.,
# Science 2023). Framed as informational, sourced, no cure/dosage claims.
DEFAULT = {
    "brand": "TheScienceDrop",
    "headerLabel": "SCIENCE DROP",
    "disclaimer": "Educational — not medical advice",
    "segments": [
        {"text": "Could a single amino acid **slow aging**?"},
        {
            "text": "A 2023 study in the journal **Science** found taurine levels drop as we age.",
            "source": "Science, 2023",
        },
        {
            "text": "In mice and monkeys, topping it back up **improved healthspan**.",
            "source": "Singh et al., 2023",
        },
        {"text": "Your body makes taurine — it's also in **fish, meat, and eggs**."},
        {"text": "But whether supplements help **humans** live longer is still **unproven**."},
        {"text": "Follow for **tomorrow's** science drop."},
    ],
}


def _to_audio_data_uri(mp3_path: str) -> str:
    data = Path(mp3_path).read_bytes()
    return f"data:audio/mpeg;base64,{base64.b64encode(data).decode('ascii')}"


async def build_segments(raw_segments: list[dict], *, voice: str, use_vo: bool) -> list[dict]:
    """Voice each segment and attach audioSrc + a duration that fits the VO."""
    out: list[dict] = []
    for i, seg in enumerate(raw_segments):
        text = seg["text"]
        spoken = text.replace("**", "")  # don't read the emphasis markers aloud
        dur = float(seg.get("durationSec", 4.0))
        audio_uri = None
        if use_vo:
            try:
                logger.info("VO %d/%d: %r", i + 1, len(raw_segments), spoken)
                # Expressive delivery for the science channel — flat style=0 reads
                # as "AI slop". Scoped here; the global text_to_speech defaults stay
                # flat so the Headshot AI ad reels are unaffected.
                mp3 = await text_to_speech(spoken, voice=voice, style=0.45, stability=0.40)
                measured = await measure_mp3_duration(mp3)
                if measured:
                    dur = round(measured + 0.6, 2)  # small tail so it doesn't clip
                audio_uri = _to_audio_data_uri(mp3)
            except ElevenLabsError as e:
                logger.warning("VO failed (%s) — segment will be silent", e)
        item = {"text": text, "durationSec": dur}
        if audio_uri:
            item["audioSrc"] = audio_uri
        if seg.get("source"):
            item["source"] = seg["source"]
        out.append(item)
    return out


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--script-file")
    ap.add_argument("--voice", default="male_deep")
    ap.add_argument("--no-vo", action="store_true")
    ap.add_argument("--upload", action="store_true")
    ap.add_argument("--privacy", default="unlisted", choices=["private", "unlisted", "public"])
    ap.add_argument("--output")
    args = ap.parse_args()

    spec = DEFAULT
    if args.script_file:
        spec = json.loads(Path(args.script_file).read_text())

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    # Must be absolute: the Remotion subprocess runs with cwd=video_renderer/,
    # so a relative path would land there instead of where we check for it.
    output = (Path(args.output).resolve() if args.output else OUTPUT_DIR / f"science-{ts}.mp4")

    logger.info("Building %d segments (vo=%s)…", len(spec["segments"]), not args.no_vo)
    segments = await build_segments(spec["segments"], voice=args.voice, use_vo=not args.no_vo)
    total = sum(s["durationSec"] for s in segments)
    logger.info("Total reel length ~%.1fs", total)

    props = {
        "segments": segments,
        "brand": spec.get("brand", "TheScienceDrop"),
        "headerLabel": spec.get("headerLabel", "SCIENCE DROP"),
        "disclaimer": spec.get("disclaimer", "Educational — not medical advice"),
    }

    logger.info("Rendering ScienceNewsReel → %s", output)
    rendered = await render_reel(
        composition="ScienceNewsReel", props=props, output_path=str(output)
    )
    print(f"\n✓ Rendered {rendered.duration_sec or total:.1f}s reel: {rendered.path}")
    print(f"   open {rendered.path}")

    if not args.upload:
        return

    # Lazy import so a missing YouTube setup doesn't block render-only runs.
    from aeco.tools.content.youtube_publisher import YouTubeError, upload_short

    title = spec["segments"][0]["text"].replace("**", "")
    description = (
        "A daily 60-second science drop on supplements and medical discoveries.\n"
        "Educational only — not medical advice. Sources cited on screen.\n"
    )
    tags = ["science", "longevity", "supplements", "health", "shorts"]
    try:
        logger.info("Uploading to YouTube (privacy=%s)…", args.privacy)
        res = await upload_short(
            rendered.path,
            title=title,
            description=description,
            tags=tags,
            privacy=args.privacy,
        )
        print("\n" + "=" * 60)
        print("✓ Uploaded to YouTube")
        print(f"  Video ID:  {res['id']}")
        print(f"  Watch URL: {res['watch_url']}")
        print(f"  Privacy:   {args.privacy}")
        print("=" * 60)
    except YouTubeError as e:
        print(f"\n✗ YouTube upload failed: {e}")
        print("  (The MP4 is rendered and saved above — fix auth and re-run with --upload.)")
        raise


if __name__ == "__main__":
    asyncio.run(main())
