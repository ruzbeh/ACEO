"""Build & publish 'The Science Drop' serialized investigation series.

Each episode is a connected 5-beat reel carrying a PART X/8 badge and a
cliffhanger hand-off, designed to be dripped one-per-day to turn passive
swipers into followers. Reuses the daily_reels render / compliance-gate /
upload primitives, so the load-bearing daily job stays untouched.

Run (needs Node 18+ on PATH for Remotion):
    # proof: render Part 1, do NOT upload
    PATH="$HOME/.nvm/versions/node/v22.22.1/bin:$PATH" \
      .venv/bin/python scripts/make_series.py --part 1 --no-upload
    # publish the next not-yet-published part (the daily drip)
    ... scripts/make_series.py --next --privacy public
    # publish every remaining part in order, now
    ... scripts/make_series.py --all --privacy public

State (which parts are live + their URLs, for backward cross-links) lives in
workspace/content/state/series_<slug>.json.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import scripts.daily_reels as dr  # noqa: E402 — render/gate/image/frame primitives

logger = dr.logger

# ── The series ─────────────────────────────────────────────────────────────
# An 8-part investigation: each episode reveals one "thief" of energy and hands
# off to the next on a cliffhanger. Escalates simple → hidden-medical →
# counterintuitive payoff. Every claim cited + compliance-safe (diagnostic-test
# suggestions only; no dosing/cure-of-disease language). 5-beat HOOK formula,
# **bold** = accent word; the last beat is the hand-off to the next part.
SERIES: dict = {
    "slug": "why-tired",
    "name": "Why Are You Always Tired?",
    "total": 8,
    "tags": ["why am i always tired", "fatigue", "tired all the time", "low energy",
             "energy", "health", "science", "shorts", "wellness"],
    "culprits": {
        1: "dehydration", 2: "blood-sugar crashes", 3: "hidden low iron (ferritin)",
        4: "B12 deficiency", 5: "an underactive thyroid", 6: "broken deep sleep",
        7: "chronic stress & cortisol burnout", 8: "the one real fix — movement",
    },
    "episodes": [
        {"part": 1, "title": "8 Hours of Sleep & Still Exhausted?", "segments": [
            {"text": "You sleep eight hours — and you're **still** wrecked. Why?"},
            {"text": "It's not laziness. Something is quietly **stealing** your energy."},
            {"text": "Suspect one: **dehydration** — even 1–2% low drains focus and drive.", "source": "J. Nutrition, 2012"},
            {"text": "Water's the **easy** thief — most of us run mildly low all day."},
            {"text": "But it's small. Tomorrow, the **3pm crash**. Part 2."}]},
        {"part": 2, "title": "The 3pm Energy Crash, Explained", "segments": [
            {"text": "Crashing hard every **afternoon**? Meet suspect two."},
            {"text": "Refined carbs spike your blood sugar — then **drop** you off a cliff."},
            {"text": "That rollercoaster leaves you **foggy and drained**.", "source": "clinical reviews"},
            {"text": "Protein and a short **walk** flatten the crash."},
            {"text": "Smoothed your carbs and still tired? It's **in your blood**. Part 3."}]},
        {"part": 3, "title": "Your 'Normal' Blood Test Might Be Lying", "segments": [
            {"text": "Your blood test says \"**normal**\" — it can still be lying."},
            {"text": "Suspect three: low **ferritin**, your iron stores near empty."},
            {"text": "It drains energy for **years** before anemia ever shows.", "source": "clinical reviews"},
            {"text": "One number most checkups skip — ask for **ferritin**."},
            {"text": "Iron clear? Another fuel your **nerves** are starving for. Part 4."}]},
        {"part": 4, "title": "Tired AND Tingling Hands?", "segments": [
            {"text": "Tired **and** tingling hands? Suspect four is sneaky."},
            {"text": "Your nerves run on **B12** — and it quietly runs low."},
            {"text": "Vegans and the over-50s are most at **risk**.", "source": "clinical reviews"},
            {"text": "A cheap blood test **settles** it."},
            {"text": "Vitamins fine? Check the **thermostat** of your metabolism. Part 5."}]},
        {"part": 5, "title": "The Tiny Gland That Controls Your Energy", "segments": [
            {"text": "One tiny gland sets your whole energy **thermostat**."},
            {"text": "Suspect five: an **underactive thyroid** — and it's often missed."},
            {"text": "It slows metabolism into **fatigue** and brain fog.", "source": "clinical reviews"},
            {"text": "A simple **TSH** blood test checks it — ask your doctor."},
            {"text": "Thyroid normal? Then it's not how **long** you sleep. Part 6."}]},
        {"part": 6, "title": "Why 8 Hours of Sleep Isn't Enough", "segments": [
            {"text": "Eight hours of **bad** sleep beats you up like five."},
            {"text": "Suspect six: shallow, **broken** deep sleep."},
            {"text": "Late screens, a nightcap and low magnesium all **fragment** it.", "source": "sleep research"},
            {"text": "Dim the screens, skip the **bedtime** drink — it rebuilds."},
            {"text": "Sleeping deep and still drained? It's your **stress** chemistry. Part 7."}]},
        {"part": 7, "title": "Wired But Exhausted? Here's Why", "segments": [
            {"text": "**Wired** but exhausted? That's suspect seven."},
            {"text": "Chronic stress throws your **cortisol** rhythm out of sync."},
            {"text": "You end up tired-and-tense, running on **fumes**.", "source": "stress research"},
            {"text": "Time outdoors and slow breathing help **reset** it."},
            {"text": "All seven cleared — so why save the **fix** for last? Part 8."}]},
        {"part": 8, "title": "The Fix for Exhaustion Nobody Wants to Hear", "segments": [
            {"text": "The fix for exhaustion is the thing you **least** feel like doing."},
            {"text": "**Move.** Exercise builds the mitochondria that *make* your energy."},
            {"text": "The more you rest, the more tired you **get**.", "source": "exercise research"},
            {"text": "Seven thieves, one fix: water, sugar, iron, B12, thyroid, sleep, stress — **move**."},
            {"text": "Start with **one** today. Your energy is fixable."}]},
    ],
}

STATE_FILE = dr.STATE_DIR / f"series_{SERIES['slug']}.json"


def _load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except json.JSONDecodeError:
            pass
    return {"published": [], "urls": {}, "video_ids": {}}


def _save_state(s: dict) -> None:
    dr.STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(s, indent=2))


def _episode(part: int) -> dict:
    for ep in SERIES["episodes"]:
        if ep["part"] == part:
            return ep
    raise SystemExit(f"no such part {part} (1..{SERIES['total']})")


def _title(ep: dict) -> str:
    base = f"Why You're Always Tired (Part {ep['part']}/{SERIES['total']}): {ep['title']}"
    return (base + " #Shorts") if len(base) + 8 <= 100 else base[:100]


def _description(ep: dict, src: str | None, prev_url: str | None) -> str:
    n = ep["part"]
    lines = [
        f"🔍 WHY ARE YOU ALWAYS TIRED? — a science investigation in {SERIES['total']} parts.",
        f"Part {n} of {SERIES['total']}: {SERIES['culprits'][n]}.",
        "New part daily — follow @sciencedropdaily so you don't miss the answer.",
        "",
        "Educational only — not medical advice.",
    ]
    if src:
        lines.append(f"Source: {src}")
    if prev_url:
        lines.append(f"◀ Previous part: {prev_url}")
    lines += ["", "#Shorts #fatigue #energy #tired #health #science"]
    return "\n".join(lines)


async def make_episode(ep: dict, *, privacy: str, upload: bool,
                       use_agent: bool = True, use_images: bool = True,
                       prev_url: str | None = None) -> dict:
    n = ep["part"]
    topic_id = f"{SERIES['slug']}-{n}"
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    out = dr.OUTPUT_DIR / f"{topic_id}-{ts}.mp4"
    dr.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    segments = await dr.build_segments(ep["segments"], voice="male_deep", use_vo=True)

    hero_uri = None
    if use_images:
        try:
            prompt = await dr.hero_director(topic_id, ep["segments"])
            seed = int(hashlib.md5(topic_id.encode()).hexdigest()[:6], 16)
            img = await dr.generate_image(prompt, seed=seed)
            if img:
                hero_uri = dr._img_data_uri(img)
                logger.info("hero image: ok")
            else:
                logger.info("hero image: none — motion graphics only")
        except Exception as e:  # noqa: BLE001 — imagery is best-effort
            logger.warning("hero imagery failed (%s) — motion-graphics only", e)

    props = {"segments": segments, "brand": dr.BRAND, "headerLabel": dr.HEADER,
             "disclaimer": dr.DISCLAIMER, "seriesLabel": f"PART {n} / {SERIES['total']}"}
    if hero_uri:
        props["heroImage"] = hero_uri
    rendered = await dr.render_reel(composition="ScienceNewsReel", props=props, output_path=str(out))
    result = {"part": n, "file": rendered.path, "uploaded": False}
    if not upload:
        result["status"] = "rendered"
        return result

    from aeco.tools.content.youtube_publisher import YouTubeError, upload_short

    title = _title(ep)
    src = next((s.get("source") for s in ep["segments"] if s.get("source")), None)
    desc = _description(ep, src, prev_url)
    tags = list(SERIES["tags"])

    # Compliance / quality gate (keep the strike-risk net). We KEEP our own series
    # title + description — the agent's rewrites would break the "Part X/8" framing
    # — and only borrow extra tags.
    if use_agent:
        script = " ".join(s["text"].replace("**", "") for s in ep["segments"])
        opt = await dr.review_and_optimize(topic_id, script, dr._frame_uris(rendered.path))
        result["agent"] = {k: opt[k] for k in
                           ("approved", "quality_score", "decision", "visual_ok", "issues")}
        if not opt["approved"]:
            result["status"] = "held_by_agent"
            return result
        if opt["tags"]:
            tags = list(dict.fromkeys(tags + opt["tags"]))[:15]

    try:
        res = await upload_short(rendered.path, title=title, description=desc,
                                 tags=tags, privacy=privacy)
        result.update(uploaded=True, status="uploaded", video_id=res["id"],
                      url=res["watch_url"], title=title)
    except YouTubeError as e:
        result.update(status="upload_failed", error=str(e)[:200])
    return result


async def main() -> None:
    ap = argparse.ArgumentParser(description="Build/publish the 8-part 'Why Are You Always Tired?' series.")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--part", type=int, help="render/publish a single part (1..8)")
    g.add_argument("--next", action="store_true", help="the next not-yet-published part (daily drip)")
    g.add_argument("--all", action="store_true", help="every remaining unpublished part, in order")
    ap.add_argument("--privacy", default="unlisted", choices=["private", "unlisted", "public"])
    ap.add_argument("--no-upload", action="store_true", help="render only (proof)")
    ap.add_argument("--no-agent", action="store_true", help="skip the compliance gate")
    ap.add_argument("--no-images", action="store_true", help="motion graphics only (skip hero image)")
    args = ap.parse_args()

    state = _load_state()
    published = set(state.get("published", []))

    if args.part:
        parts = [args.part]
    elif args.all:
        parts = [e["part"] for e in SERIES["episodes"] if e["part"] not in published]
    elif args.next:
        remaining = [e["part"] for e in SERIES["episodes"] if e["part"] not in published]
        parts = remaining[:1]
    else:
        # Default: proof Part 1 only, no upload.
        parts = [1]
        args.no_upload = True

    if not parts:
        print("All parts already published. Nothing to do.")
        return

    logger.info("Series '%s' — parts %s (upload=%s, privacy=%s)",
                SERIES["slug"], parts, not args.no_upload, args.privacy)
    results = []
    for n in parts:
        ep = _episode(n)
        logger.info("── Part %d/%d: %s ──", n, SERIES["total"], ep["title"])
        prev_url = state.get("urls", {}).get(str(n - 1))
        try:
            r = await make_episode(ep, privacy=args.privacy, upload=not args.no_upload,
                                   use_agent=not args.no_agent, use_images=not args.no_images,
                                   prev_url=prev_url)
        except Exception as e:  # noqa: BLE001
            logger.exception("part %d failed", n)
            r = {"part": n, "status": "error", "error": str(e)[:200], "uploaded": False}
        results.append(r)
        if r.get("status") == "uploaded":
            state.setdefault("published", []).append(n)
            state.setdefault("urls", {})[str(n)] = r["url"]
            state.setdefault("video_ids", {})[str(n)] = r["video_id"]
            _save_state(state)

    print("\n" + "=" * 64)
    print(f"SERIES '{SERIES['name']}' — {sum(1 for r in results if r.get('uploaded'))}/{len(results)} published")
    print("=" * 64)
    for r in results:
        line = f"  [{r.get('status','?'):14}] Part {r['part']}/{SERIES['total']}"
        if r.get("file"):
            line += f"  {Path(r['file']).name}"
        if r.get("url"):
            line += f"  → {r['url']}"
        if r.get("status") == "held_by_agent" and r.get("agent"):
            line += f"  ⚠ {'; '.join(r['agent']['issues'][:2])}"
        elif r.get("error"):
            line += f"  ✗ {r['error']}"
        print(line)
    print("=" * 64)


if __name__ == "__main__":
    asyncio.run(main())
