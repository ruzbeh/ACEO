# Faceless Supplement & Medical-Discovery Reels — Design

**Date:** 2026-05-28
**Status:** Approved (design); pending spec review → implementation plan
**Owner:** founder
**Topic slug:** supplement-science-reels

## 1. Summary

A faceless, AI-automated short-form content system that, on a daily schedule,
researches the latest in **supplements and medical/scientific discoveries**
(via Google Gemini), turns the best stories into vertical reels (AI-generated
imagery + kinetic-typography captions + AI voiceover), and — after a one-tap
human approval — publishes them to **Instagram Reels** and **YouTube Shorts**.

This is a **new content/audience venture**, separate from the Headshot AI ad
business. There is no product to sell; the goal is to grow a science-news
channel.

### Non-goals
- Not a paid-ads system (the existing FB ad reel pipeline is untouched).
- Not selling a product or running a funnel.
- No human face / talking-head footage (fully synthetic visuals).

## 2. Key decisions (locked with founder)

| Decision | Choice |
|---|---|
| Architecture | **Approach A** — new parallel module inside AECO, reusing existing primitives |
| Content | Supplements + medical/science discoveries, "science news" framing |
| Visuals | AI-generated images (Google Imagen via Gemini) + kinetic typography. No stock footage. |
| Voiceover | ElevenLabs (reuse existing `voiceover.py`) |
| Autonomy | **Generate + queue for 1-tap approval** (human gate before publish) |
| Cadence | **10 reels/day** |
| Publish split | **All 10 → Instagram**; **top ~6 (by quality_score) → YouTube** (stays under YT's free quota) |
| Length | ~30–45s, 1080×1920 vertical |
| Compliance | Science-news framing, cite sources, no dosage/cure claims, on-screen "Educational — not medical advice" disclaimer |
| Brand | Brand-new; system proposes a name (candidates below) |

### YouTube quota rationale
YouTube Data API v3 default quota is 10,000 units/day; `videos.insert` costs
~1,600 units → ~6 uploads/day max without a quota increase. We publish all 10
to Instagram (IG Content Publishing allows up to 50 posts/24h) and only the
top ~6 by `quality_score` to YouTube. A quota increase can be requested later
to lift the YT cap to the full 10/day.

### Brand name candidates (non-blocking — pick later)
`The Science Drop`, `LabNote Daily`, `Compound Daily`, `VitalBytes`,
`MoleculeDaily`. Stored as config `CONTENT_BRAND_NAME`; drives the on-screen
watermark and caption voice.

## 3. Architecture

New parallel content pipeline that **reuses** the working primitives and adds
content-specific tools, model, routes, dashboard page, and scheduler. The live
Headshot AI ad pipeline (`Reel`, `routes_reels.py`, `publisher.py`) is not
modified.

### Data flow

```
cron (daily) ──► gemini_research ──► pick + rank 10 stories
   │                                  each: script + scene image-prompts + caption/hashtags
   │                                        + yt_title/description + sources[] + quality_score
   ▼
for each story (independent, parallel-bounded):
   image_gen (Imagen)        ──► scene stills
   voiceover (ElevenLabs)    ──► narration mp3 + word/segment timings
   composer (Remotion: new)  ──► 1080×1920 MP4 (AI images + kinetic captions + VO + music bed)
   persist ContentReel(status = AWAITING_APPROVAL)
   ▼
dashboard "Content Queue" ──► batch preview / approve / reject
   ▼ on approve
publish:
   instagram_publisher  (all approved)            via public MP4 URL (media_host → Supabase)
   youtube_publisher    (top ~6 by quality_score) via resumable upload
```

## 4. Modules

### New — `aeco/tools/content/`
- **`gemini_research.py`** — calls Gemini to discover recent supplement/medical
  discoveries and return **structured JSON** per story: `topic`, `title`,
  `script` (hook + 3–5 beats + outro, ~30–45s spoken), `scene_prompts[]`
  (image-gen prompts, one per beat), `caption`, `hashtags[]`, `yt_title`,
  `yt_description`, `sources[]` (`{url, claim}`), `quality_score` (0–1),
  `risk_flags[]`. System prompt enforces compliance (section 8).
- **`image_gen.py`** — text-to-image via Google Imagen (using the Gemini/Google
  API key). One image per scene prompt, 1080×1920 or center-cropped to it.
  Pluggable provider interface so we can swap/add a fallback later.
- **`instagram_publisher.py`** — IG Content Publishing: create REELS container
  with public `video_url` + caption → poll until `FINISHED` → `media_publish`.
- **`youtube_publisher.py`** — YouTube Data API v3 resumable `videos.insert`
  with OAuth refresh token; `#Shorts`, category 28 (Science & Tech).
- **`media_host.py`** — uploads a local MP4 to Supabase Storage and returns a
  public URL (required because IG fetches the video by URL).

### Reused as-is
- `aeco/tools/video/composer.py` → `render_reel` (Remotion subprocess wrapper).
- `aeco/tools/video/voiceover.py` → `text_to_speech`, `measure_mp3_duration`.
- (Phase 4, optional) `aeco/tools/video/runway.py` → `image_to_video`.

### New API — `aeco/api/routes_content.py`
`/api/content` — list queue, get one, approve (single + batch), reject,
re-publish, manual "generate now". Mirrors `routes_reels.py` patterns
(background tasks, WS progress via the event bus, `progress_log`).

## 5. Data model — `ContentReel` (new table)

Separate from `Reel` (which is ad/headshot-specific). Fields:

- `id`, `created_at`, `updated_at`
- `topic`, `title`
- `script` (text), `scene_prompts` (JSON list)
- `image_paths` (JSON list), `voiceover_path`, `voiceover_duration_sec`
- `mp4_path`, `duration_sec`
- `caption`, `hashtags` (JSON list), `yt_title`, `yt_description`
- `sources` (JSON list of `{url, claim}`)
- `quality_score` (float), `risk_flags` (JSON list)
- `content_hash` (dedup key over the core claim/title)
- `status` enum: `RESEARCHING → GENERATING → AWAITING_APPROVAL → APPROVED → PUBLISHING → PUBLISHED → FAILED → REJECTED`
- `ig_media_id`, `yt_video_id` (idempotency: set → never re-post)
- `published_to` (JSON list, e.g. `["instagram","youtube"]`)
- `progress_log` (JSON list of `{ts, stage, message}`)
- `last_error`

**Dedup:** before generating, compute `content_hash` of the story's core
claim/title; skip if the same hash was seen within the last N days (default 30)
so the same discovery isn't reposted.

## 6. Remotion composition — `ScienceNewsReel` (new)

Registered in `video_renderer/src/Root.tsx` next to `BeforeAfterReel`.
Variable duration driven by VO length (clamped to ~30–45s). Per scene:

- AI background image with slow Ken Burns pan/zoom.
- **Kinetic-typography subtitle** burned in, synced to VO segment timings.
- Top header chip (e.g. "🔬 Science Drop").
- Animated progress bar across the bottom.
- Source-citation chip shown on the scene where a claim is stated.
- Persistent small **"Educational — not medical advice"** disclaimer.
- Brand watermark (`CONTENT_BRAND_NAME`).
- Royalty-free music bed under the VO (file in `public/`).

Props: `scenes[]` ({imageSrc, captionText, startSec, endSec, sourceLabel?}),
`audioSrc`, `brand`, `headerLabel`, `disclaimer`, `musicSrc`.

Images and audio passed as base64 data URIs (same approach as the existing
pipeline, to dodge Remotion's `public/` bundle-cache quirk).

## 7. Scheduler + approval queue

- **Scheduler:** a daily cron job fires the research → generate stage for 10
  stories, leaving each as `AWAITING_APPROVAL`. (Implementation: AECO's
  scheduling mechanism or a system cron calling `scripts/make_content_reel.py`
  in batch mode — decided in the plan.)
- **Approval queue (dashboard):** new **Content Queue** page — grid of MP4
  previews with script, sources, caption, quality_score, and risk_flags.
  **Batch approve/reject.** Approving publishes per the 10-IG / top-6-YT rule.
  Risk-flagged items require explicit per-item approval.

## 8. Safety / compliance

The single biggest operational risk is platform medical-misinformation
enforcement. Mitigations baked in:

- Gemini system prompt: science-news framing; **cite a real source per claim**;
  **no dosage, cure, treatment, or "miracle" claims**; appropriate hedging;
  emit `risk_flags[]` for anything borderline.
- A lightweight moderation pass over the generated script; risk-flagged reels
  cannot be batch-approved (require explicit per-item approval).
- On-screen + in-caption **"Educational — not medical advice"** disclaimer.
- Sources surfaced in the approval UI so a human can sanity-check before publish.

## 9. Config / secrets (`config.py` + `.env`)

- `google_api_key` — Gemini research + Imagen image gen.
- `youtube_oauth_client_id`, `youtube_oauth_client_secret`, `youtube_oauth_refresh_token`.
- `instagram_account_id` (IG Business account id) — reuses existing `facebook_access_token`.
- `supabase_url`, `supabase_service_key` — public MP4 hosting for IG.
- `content_brand_name`, `content_reels_per_day` (default 10).
- One-time helper `scripts/youtube_oauth.py` to mint the YouTube refresh token.

## 10. Error handling & idempotency

- Each story is independent; one failure doesn't sink the batch.
- Every external step (Gemini, Imagen, ElevenLabs, Remotion, IG, YT) has
  graceful fallback + bounded retry, mirroring `routes_reels.py:_render_task`.
- Publish is **idempotent**: a set `ig_media_id` / `yt_video_id` blocks
  re-posting on re-approve or retry.
- IG container polling has a timeout; YT resumable upload resumes on transient
  failure.

## 11. Testing

- Unit tests with **mocked** Gemini / Imagen / IG / YT responses (no live calls
  in CI).
- One Remotion **render smoke test** for `ScienceNewsReel` (short fixture).
- `scripts/make_content_reel.py` — CLI to run the full pipeline for a single
  story end-to-end (no scheduler), mirroring `scripts/make_reel.py`. Supports
  `--no-publish` (render only) and `--story "<topic>"`.

## 12. Phasing

1. **Phase 1 — Core + YT:** config keys, `ContentReel` model, `gemini_research`,
   `image_gen`, `ScienceNewsReel` composition, render pipeline, `routes_content`,
   Content Queue dashboard page (preview + approve), **YouTube publish**,
   `make_content_reel.py` CLI.
2. **Phase 2 — Instagram:** `media_host` (Supabase) + `instagram_publisher`;
   wire approve → publish to both platforms (10 IG / top-6 YT).
3. **Phase 3 — Automation:** daily 10/day scheduler + dedup (`content_hash`) +
   batch approval UI.
4. **Phase 4 (optional):** Runway motion on key scenes, multiple composition
   templates, basic performance tracking (views/engagement pull-back).

## 13. Open items (resolved at planning time)
- Exact scheduler mechanism (AECO scheduler vs system cron).
- Final brand name (from candidates in section 2).
- Music-bed track selection (royalty-free).
- Imagen model id / fallback provider.
