# AECO Video Ad Harness

Produces a ready-to-launch FB/IG Reel from a set of before/after images, no manual editing required.

```
Brief + images
    → script_writer   (LLM → headline/sub/CTA)
    → composer        (Remotion → 1080×1920 H.264 MP4)
    → publisher       (FB Graph API → PAUSED video ad)
```

## Phase 1 (now) — Ken Burns + captions

Pure local render. No paid video-gen API required. 25-second BeforeAfterReel
with:

- **Hook** (3s): before image + bold "Your LinkedIn photo?" overlay
- **Problem** (3s): caption "...first thing recruiters see"
- **Reveal** (10s): 4 after-headshots swap with Ken Burns zoom + style badges
- **Proof** (4s): 2,000+ customers · 4.8/5 · 2 min · $300+
- **CTA** (5s): offer + button with pulse animation

Output: ~6–8 MB MP4, FB Reels spec (1080×1920, 30fps, yuv420p).

## Phase 2 (ready, not shipped) — Runway image-to-video

`RUNWAY_API_KEY` is wired in `aeco/config.py`. Next step: swap the Ken Burns
clips for actual Gen-4 Turbo img2vid outputs so the headshots have real motion
(head turn, subtle blink). ~$1.20 per reel in video generation cost.

## Usage

```bash
# Render only (no upload)
python scripts/make_reel.py \
    --before ./before.jpg \
    --after a.jpg b.jpg c.jpg d.jpg \
    --output ./out.mp4

# Render + upload to Facebook as PAUSED ad under the Registration adset
python scripts/make_reel.py \
    --before ./before.jpg \
    --after a.jpg b.jpg c.jpg d.jpg \
    --upload
```

## Files

| Path | What it does |
|---|---|
| `video_renderer/` | Remotion (Node) project — actual rendering |
| `video_renderer/src/compositions/BeforeAfterReel.tsx` | The composition |
| `aeco/tools/video/composer.py` | Python wrapper around `npx remotion render` |
| `aeco/tools/video/script_writer.py` | LLM → script variants |
| `aeco/tools/video/publisher.py` | FB Graph API video upload + ad creation |
| `scripts/make_reel.py` | CLI orchestrator |

## Known quirks

- **Remotion bundle caches `public/` at build time.** Files staged after the
  first bundle are served 404. Workaround (already applied): pass images as
  base64 `data:` URIs via `--props` instead of filesystem paths.
- **Entry-point arg is required** on `remotion render <entry> <comp> <out>`.
  Default-inferred entry doesn't register our Root.tsx.

## FB ad config used by `--upload`

- Adset: `120243930512770566` (US Broad — Registration — 1700/day)
- Page:  `1091699287351335`
- Link:  `https://www.headshot-generators.com/lp`
- Status: always created PAUSED — user toggles ACTIVE in Meta Ads Manager
