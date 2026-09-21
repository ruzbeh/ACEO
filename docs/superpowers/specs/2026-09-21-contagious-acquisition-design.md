# Headshot AI — Contagious Acquisition Strategy (design spec)

**Status:** Draft, awaiting founder review. No implementation started.
**Date:** 2026-09-21
**Product:** Headshot AI, https://www.headshot-generators.com (repo `headshot-studio`)
**Framework requested:** Jonah Berger's *Contagious* (STEPPS) plus viral-loop math.

## How this spec was produced

- Audit of the existing share/referral surface, GA4 (property 527593434) and Supabase `jobs` for the trailing 30 days: 57 paid orders, 84% Facebook-attributed, 75% via the women landing variant, 74% at the $29 tier; GA4 shows 1 `share` event from ~45 purchasers and 0 `/refer` pageviews.
- A 30-agent panel: 4 research sweeps (competitor referral/affiliate/team mechanics, viral AI-photo case studies, referral and K-factor benchmarks, non-referral contagion vectors), 5 independent strategists (STEPPS purist, growth-loop engineer, distribution-native, capital allocator, B2B/partner contrarian), 3 adversarial refuters per strategy (behavioral, economics, execution/risk), 3 judges, then synthesis, a completeness critic and one revision pass.
- Every strategy failed its refutation as designed (average score 3/10). The refuters independently converged on the same salvage list, and all three judges ranked the partner/gift strategy first. That convergence, not any single strategist's claim, is the basis for the design below.
- All codebase references were verified read-only against `origin/main` (c44cd9a). The local `headshot-studio` checkout was 75 commits behind at audit time and gave a wrong picture (it suggested `?ref=` was never read; on `origin/main` it prefills the coupon field, which makes `/upload?ref=FAMILY200` a free-full-set link today).

## Decisions required before implementation

1. **Phase 0 leak closure** (the `?ref=`/FAMILY200 free unlock, the clean-image URL exposure through the job JSON route and unauthenticated blob proxy, and the ungated image-feedback $0 unlock) is security and revenue hygiene with no strategy dependency. Approve shipping it first.
2. **Strategy approval:** partner program + gift seat + attribution rail + private share, with hosted "help me pick" polls explicitly deferred. See §9 for what was rejected and why.
3. **Routing:** per the house rule, code changes go through an AECO initiative; ops changes (Vercel env rotation, Stripe coupons) are done directly. Confirm, or authorize a direct build in `headshot-studio`.
4. The founder-only questions in §10.


## 1. Core insight and honest expected outcome

No buyer-driven viral loop is measurable at 45–57 buyers/month: GA4 shows one `share` event from ~45 buyers in 30 days (~2%), and every corrected chain (share × recipients × upload × paid) lands at buyer→buyer K ≈ 0.0004, an order every few years, not a channel. So the contagion unit cannot be the buyer; it has to be a **node that touches many of her at the moment of need** (career coach, resume writer, AI-headshot reviewer, midlife-career creator, realtor team lead or direct-sales upline as an individual) or a **purchase where buyer ≠ user** (a gift, including the adult daughter buying for her mother), because nodes recur monthly and gifts create a new user with revenue already collected. The buyer's own share stays private and infrastructure-free (send the image files; a spoken answer to "where did you get that?"), and is prompted twice — at day 0 and at day 10, when the research says referrals actually happen — so it produces the share-rate baseline any hosted loop would need before it is justified.

**Base numbers, one window.** The brief's "ROAS 0.42 on ~$2.3k" (Sept 7 memory) and "57 orders / 84% Facebook" (Sept 21 pull) are different windows and do not reconcile (0.42 × $2,300 = $966 ≈ 36 orders at $27, not 57). Day-0 task: recompute both on one 30-day window in Stripe. Until then: headshot-only ROAS ≈ 0.67–0.70 once the ~$894 paused pet spend is excluded ($966 ÷ ~$1,400), so the gap to the 1.2 floor is ~1.75×, not ~2.9×; FB CPA is somewhere between $29 (headshot-only spend ÷ 48 FB orders) and $64 (0.42-implied), placeholder $48.

**Expected incremental paid orders/month (Stripe-attributed):**

| Day | Conservative | Base | Optimistic | What is live |
|---|---|---|---|---|
| 30 | 0 | 0.1 | 0.5 | Leak fixes, attribution rail, private share + spoken answer, heard-from question, day-10 nudge, one-time "give a friend" blast, `/friend` |
| 60 | 0.2 | 0.9 | 3 | + partner page and first 30 outreach (from day 14), gift seat (from ~day 21, gated) |
| 90 | 0.5 | 2.1 | 10.5 | + vertical landers, customers table for the 11-month refresh email, analyzer share card, seat-pack demand test |

Base at day 90 = 1.2 partner-attributed + 0.6 gift + 0.3 landers + 0.02 customer share = **2.1/month, 3.6% of orders** (2.6% excluding gifts, because a gift bought by an FB-acquired buyer carries `acquisition_source=facebook`; only the recipient's later behaviour is non-paid). Cumulative base expectation by day 120 ≈ 5.5 orders. **Implied K:** buyer→buyer K ≈ 0.0004 (0.00005–0.003), effectively zero and stated as such. The channel ratio (non-paid orders ÷ paid orders) is ~0.03 at day 90 base (0.005–0.13); it is partner-driven and does not compound, so it is not called K. Blended ROAS moves +0.02 (on $2,300) to +0.04 (on headshot-only spend). A ~10% share of orders by day 180 is reachable only under the optimistic partner ramp (8 partners × 60% active × 1/month + 2% gifts + 1 lander order ≈ 7/64); there is no sourced comparator for it. Completed→paid (10–12% today) and AOV (Signature $49 push, PR #29 upsell) remain the primary levers and run in parallel; nothing here touches the pre-purchase paywall except the partner-client discount, which is a cohort surface, not a test (see §6 on the `flags.ts` freeze).

## 2. Judges' winner, grafts, and objections answered

**Winner:** `b2b-partner-contrarian` (Roster Loop), **stripped** to what survives: attribution rail → 30% partner program with a server-applied client discount → paid gift seat → individual vertical landers → seat-pack *demand test* (no orgs table until offices pay). Dropped: orgs table, manage page, seat ladder, roster composite, individual "give your team $19" nudge.

**Grafted (from the rejected strategies):**
- *growth-loop-engineer*: share/redeem tokens that never expose `jobId` (paid results are open by UUID via `hasOwnerOrCompletedPaidAccess`); records in their own tables, never on the jsonb job row; edge-by-edge instrumentation into Stripe metadata; a /stats acquisition panel counting only `paid && paidAmountCents > 0`.
- *stepps-purist*: recipient-only, in-kind-or-percent, no-sender-cash incentive shape; the pasteable/spoken "where did you get it" answer in the ready email; creator seeding with disclosure, inside the partner program.
- *linkedin-native*: "Post it" Facebook profile-photo caption (no link, no forced AI disclosure); "How did you hear about us?" on the download prompt; per-segment outreach kill rule; same-day pause criteria for any face-bearing surface.
- *capital-allocator*: download-triggered (not vote-triggered) Pro→Signature upgrade email; decide on leading indicators at day 30–60, on counts at day 120, never on single-digit paid counts at day 60.
- *refuter consensus*: address-level `email_suppressions` and a `charge.refunded` webhook branch before any third-party email; first-touch partner attribution beside last-touch; `?ref=` retired in Phase 0, not reused; the pre-existing clean-image bypass closed before anything referral-shaped ships.

**Restored from the critic (previously dropped or missing):** the clean-image leak via `GET /api/jobs/[jobId]` + `/api/blob` (Phase 0); gating the image-feedback auto-unlock to jobs that received the feedback email (Phase 0); the day-10 nudge, whose delivery path (`drip-reminder` cron + `reminderStep`) does exist; a one-time "give a friend, nothing for you" blast as the cheapest falsification test and the gate for the gift build; retention/frequency levers (customers table → 11-month refresh email; the dormant `subscriptionOnResults` flag and `monthly-drops` crons noted, not flipped); the /pet post-fix data as the gifting prior; the intergenerational buyer, a forwardable no-face Practical-Value asset (`/linkedin-photo-analyzer` already exists), and calendar triggers; a prod-walk step per phase; refund and negative-WOM exposure in the math; brand-search/direct baselines; Supabase egress discipline.

**Objections answered:**

| Objection | Answer |
|---|---|
| "Buyer belongs to a roster" is unmeasured; `personal_print` leads the download survey | Accepted. No customer-initiated team invite. Phase 1 reads the `company_team` share of `job.downloadLearning.intendedUse` (collected since 2026-08-08) as a gate; the seat pack is a Payment-Link demand test, built out only if ≥3 offices pay. |
| Telling colleagues you used an AI tool is a social cost | Accepted. Nothing requires disclosure: partners endorse to *their* audience; gifts are occasion-framed; her private share sends photos, not a link; the spoken answer is optional and unbranded by default. |
| Corrected customer-seeded K ≈ 0.01; the rest is outbound B2B | Accepted and stated in §1. This is a **channel with node contagion**, not a loop. Founder outreach capped at ~2 h/week with segment kill rules. |
| 14.5 agent-days on the checkout/webhook path that broke twice in September | Re-estimated bottom-up in §7 at ~12 agent-days, planned as 12–16 (refuters found every estimate 2–3× low). Gift checkout follows the jobless reel precedent (`metadata.reelId` branch, webhook L96–130); the gift and partner tables are separate from `jobs`. |
| Kill criteria unreachable at this volume | Day 60 is a leading-indicator checkpoint only (partners recruited, link clicks, gift checkout starts, blast clicks); outcome gates move to day 120 with thresholds set so the base case passes ~90% of the time and a dead channel passes ~20% (§6). No gate depends on invitee conversion or on a ratio over ~30 survey responses. |
| Realtors/direct sellers are 1099; brokerages don't buy | Accepted. `/for/real-estate` and `/for/direct-sales` sell the individual $29 set; no brokerage-pays model. |
| Recipient benefit hollow (COMEBACK15 already 15%) | COMEBACK15 is a typed code (`checkout/redirect` requires `couponCode`; it was auto-applied only on 2026-06-02, L214 comment). The partner client discount is server-applied via the existing `discounts:[…]` / `allow_promotion_codes:false` branch (`app/api/checkout/route.ts` L166, `checkout/redirect` L184), bound to a validated partner row, replaces rather than stacks, `percent_off` so en-GB GBP sessions work. The gift is 100% buyer-covered. |
| Commission basis undefined (gross vs net) | Defined: **30% of the amount the client actually paid** (net of the 15% discount): Professional $24.65 → $7.40 commission, partner CAC = $7.40 + $4.35 discount = **$11.75**; Signature $41.65 → $12.50. Commission-only alternative (no client discount): $8.70 / $14.70. HeadshotPro's "30% of $29–39" is from the research digest, unsourced; treat parity as an assumption. |
| Opportunity cost vs paywall/AOV | ~12 agent-days staged behind gates; paywall/AOV work is the primary lever and is not paused. Phase 1 items are post-purchase or infrastructure and do not touch the paywall. |
| Unsolicited email threatens the transactional Resend domain | Only buyer-initiated gift mail (one send + one 7-day reminder) and the one-time blast to our own buyers ship, from a separate sending subdomain, with `email_suppressions` and a token unsubscribe that needs no job (today's unsubscribe is job-keyed: `app/api/jobs/[jobId]/unsubscribe/route.ts` sets `emailOptOut`). |
| Employer-directed face processing (BIPA/CUBI) | Orgs dropped. A gift recipient uploads her own photos under the existing consent checkbox; the buyer never sees them. |
| Retention (7d/90d) vs "seats never expire" | Gift codes live in `gifts`, valid 12 months; redemption creates a *new* job, so `EXPIRY_DAYS_PAID=90` and the privacy page stay true. The same 90-day deletion means a buyer list does not exist beyond 90 days — hence the `customers` table in M9. |
| Day-10 nudge has no delivery path | Wrong (accepted): `app/api/cron/drip-reminder/route.ts` runs `0 */2 * * *`, keys on `reminderStep`, and step 2 was removed by choice (L54–55). Restored as M8 with a lean projection query, not `listRecentJobs(14)`. |
| In-kind top-up mis-wired; women-variant presets missing | Both dropped. The spoken answer rides the full-delivery branch of `sendHeadshotsReadyEmail` (idempotency key `ready-email:<id>:full`). |
| 60-day partner cookie vs 30-day last-touch `hs_acq` | `hs_acq` is replaced on any explicit touch **or any external referrer** (`proxy.ts` L44), so a partner-referred visitor who returns via Facebook is re-attributed. New `hs_partner` cookie: first-touch, 60 days, never overwritten while valid; stored as `acquisition.partner` beside last-touch source/medium. |
| Coupon codes are env-var backed (FAMILY200 hygiene already failed) | Partner and gift codes are DB rows. 100%-off codes leave `COUPON_CODES` entirely; self-testing uses single-use 100% Stripe promotion codes (the `createFreeRetryCoupon` pattern) through normal checkout, which the webhook records as a $0 session and /stats already excludes. The redeem endpoint is deleted, not auth-gated (its owner token lives only in the creating device's `localStorage`, `app/results/[jobId]/hooks/useResultsJob.ts` L19, so gating it would block cross-device use for no benefit). |
| Seat-ladder coordination, abuse, guarantee on unredeemed seats | Ladder dropped. Gift = one seat, 12 months, refundable to buyer on request if unredeemed. Partner self-buy excluded: customer email ≠ partner email, first purchase per email via `getPaidJobsByEmail` filtered to `paidAmountCents > 0` (it currently counts $0 feedback-unlocks as paid), 30-day hold, no payout on `refunded` orders. |
| Under-18 gift recipients | 18+ attestation on gift purchase; recipient's own consent at upload. |
| `ResultsPageClient.tsx` is 2,026 lines | The whole post-purchase card (L1702–1749: Customize-again, Share on X, Share on LinkedIn, Generate-more) is extracted as `PostPurchaseActions.tsx`, so the grid is not severed; `trackGenerateMoreClick` and `appendVariantParam` move with it. No other edits to the file. |
| Math corrections (share 5%→1–2.5%, recipients 6→1.5–2, invitee upload 35%→10–25%, invitee paid 25%→≤9–12%, partners 10→2–5 active, incremental 22→3–8, ROAS +0.28→+0.03) | Adopted as the base case in §5; §1 and §5 now use the same components (1.2 partner, 0.02 customer share, 2.1 total). |

## 3. STEPPS map

- **Social Currency** — partially owned: the partner's endorsement ("I tested AI headshots for my clients"), the private "which one?" image share, and a shareable analyzer *score* (never the photo).
- **Triggers** — owned: gift occasions (new license, graduation, job hunt, "Mom's new chapter"), the partner's existing "fix your LinkedIn" ritual, the spoken answer at the office or open house, and calendar triggers (January job season, May graduation, September back-to-work, November–December gifting) as copy switches on `/gift` and in the partner kit.
- **Emotion** — owned by the gift: a note naming *why* turns a portrait into a favour, not a comment on appearance.
- **Public** — owned only by surfaces without customer faces: the `/gift` lander, partner posts, the analyzer score card. **Not owned for the buyer's face, deliberately.** Paid output carries no mark; no public face page at this scale. Revisit via opt-in testimonial wall or `/reel` clip when the base exceeds ~300 paid/month.
- **Practical Value** — owned: the free `/linkedin-photo-analyzer` (score /10 across dimensions, already in the sitemap at 0.9) as the forwardable asset, the server-applied 15% partner-client discount, the free preview, "$29 vs a $300 photographer", and a one-page "LinkedIn photo checklist" in the partner kit.
- **Stories** — owned via partners and gifts: "my coach told me about it" / "my daughter bought me a headshot for my new job."

## 4. Mechanics

**M0 — Leak closure (Phase 0, prerequisite).**
(a) *Clean-image bypass, live today:* `GET /api/jobs/[jobId]` (`app/api/jobs/[jobId]/route.ts` L69–77) returns `resultStyles[].url` and `styleResults[].imageUrl` as `/api/blob?url=…` for every completed job with no `paid` check (only in-progress jobs require the owner token, L41–46), and `app/api/blob/route.ts` streams any private blob unauthenticated (only `isBlobUrl`). Watermarking happens only in `result/[index]/route.ts` at serve time, so the unpaid preview's clean file is one fetch away. Fix: for `!job.paid`, emit `/api/jobs/${id}/result/${i}` (the watermarking route) instead of `blobProxyPath`; strip `imageUrl` from unpaid `styleResults`; point the Stripe `product_data.images` thumbnail (`checkout/route.ts` L177–184) at the same route; extend `tests/test_job_response_privacy.ts` to assert no `/api/blob` in unpaid completed responses. `rl:blob` already exists in proxy.ts (L264).
(b) *FAMILY200:* remove every 100%-off entry from `COUPON_CODES`/`COUPON_STRIPE_IDS` and redeploy (`lib/coupons.ts` caches the registry per instance); delete `app/refer/*` (0 pageviews) with `/refer → /`; delete `app/api/coupon/redeem/route.ts` (its only purpose is 100%-off codes; a real customer used it 2026-04-22, L57); the results coupon input keeps routing typed codes to `/api/checkout/redirect`.
(c) *`?ref=` retirement:* `UploadPageClient.tsx` L317–336 and `ResultsPageClient.tsx` L746–761 read `?ref=` **and** `?coupon=`; keep only `?coupon=` and limit prefill to the existing `known` allowlist (COMEBACK15).
(d) *Image-feedback auto-unlock:* `image-feedback/route.ts` L71–82 sets `paid=true, paidAmountCents:0` after `min(5,totalImages)` ratings (one rating on a 1-image preview) and triggers full generation. Gate on `job.feedbackRequestSentAt != null` (set only by the admin blast `send-feedback-request`); ratings still record otherwise.

**M1 — Attribution rail.**
Placement: `proxy.ts maybeSetAcquisition` + `lib/acquisition.ts` + `app/api/jobs/route.ts` (already calls `resolveRequestAcquisition`, L113) + all three checkout routes. URLs: `?partner=CODE`, `?via=friend|gift|nudge|blast`, `/friend` → 302 to `/?via=friend`, `/upload?gift=CODE`. `hasExplicitAcquisitionTouch` learns `partner` and `via`; `buildAcquisitionContext` maps `partner`→source `partner`/medium `referral`, `via=friend|nudge|blast`→source `friend`. Also copy `acquisition_*` and `jobId` into `payment_intent_data.metadata` so charges (and `charge.refunded` events) carry them and Stripe Search works for the payout report. Privacy: labels only, no click IDs. GA4 `page_location` should carry `partner=`; verify on this property day 0.

**M2 — Partner program (30%, node contagion).**
Placement: `/partners` page (terms: 30% of net client payment on first purchase, 60-day first-touch, monthly PayPal after 30-day hold, $25 minimum, LinkedIn disclosure required, FB-group promo-day rule); partner = row in `partners`; client sees "Partner discount applied — 15%" at the paywall when `job.acquisition.partner` resolves. Copy for partners: "a concrete deliverable for your LinkedIn-fix session; your clients see a free preview before paying." Kit: free Signature set as a gift code (`kind=seed`), tracked link, disclosure line, one-page outreach template, the analyzer link, a trigger calendar. Segment order: (1) SEO bloggers/YouTube reviewers ranking for "AI headshot generator", (2) career coaches/resume writers, (3) midlife-career creators and 50+ job-seeker group admins, (4) realtor team leads and direct-sales uplines as individuals. Events: partner landing (`page_location`), `partner_discount_shown`, Stripe `acquisition_partner`, payout report.

**M3 — Gift seat (buyer ≠ user).**
Placement: `/gift` lander (new `GiftOccasions` content on the `Occasions.tsx` layout pattern — that component is pet-only: `if (!isPet) return null`), jobless Stripe checkout (`/api/gift/checkout`, metadata `giftId`), webhook branch beside the reel branch, gift email, recipient link `/upload?gift=CODE`; on job creation with a valid unredeemed code the job is set paid (`setJobPaid(id, 'gift:<giftId>', email, { tier:'professional' })`, `generationMode:'full'`) so the recipient never sees a paywall. Delivery: "send now" or "give me the code to forward" (she pastes it into her own card or text); optional `deliver_at` lives on the `gifts` row and a daily `gift-deliveries` cron sends due rows — **not** `email_send_queue`, which is a Resend-failure retry queue (`next_try_at`, `attempt`, `max_attempts`; migration 003). Copy: "Give someone the photo they've been putting off — a new license, a job hunt, a graduation, Mom's new chapter. They upload their own selfies; you never see them." Cross-links: `/gift` lists pet portraits (`/pet`) as an option; `/pet` gets "Send as a gift code instead" once M3 ships (same `gifts` table, `subject=pet`). Consent: 18+ attestation; recipient's own consent; one send + one 7-day reminder from `GIFT_FROM_EMAIL` on a separate Resend subdomain (today a single `RESEND_FROM_EMAIL`); token unsubscribe writing `email_suppressions`. Events: `gift_checkout_started`, `gift_purchased`, `gift_email_sent`, `gift_redeemed`, recipient job `acquisition.source=gift`.

**M4 — Private share + spoken answer (replaces the X/LinkedIn homepage buttons).**
Placement: the paid card at `ResultsPageClient.tsx` L1702–1749 → `app/results/[jobId]/components/PostPurchaseActions.tsx`. The Share-on-X and Share-on-LinkedIn tiles are **removed** (they share the homepage with a generic OG image; ~1 use in 30 days). Behaviour: pick 2–4 images → `navigator.share({ files })` fetched from `/api/jobs/[jobId]/result/[i]?download=1` (owner/paid access), shown only when `navigator.canShare({ files })` is true; otherwise "Save these and send from your photos" + copy-link. Below: "When someone asks where you got it" — a one-line spoken answer and a copyable durable link `headshot-generators.com/friend`; "Set it as your Facebook profile photo" with an editable caption (no link, brand line default-off). Same block in the full-delivery branch of `sendHeadshotsReadyEmail`. `trackShare` (`lib/analytics.ts` L414) platform union becomes `"native" | "copy" | "fb_caption"`; `friend_link_copied`, `fb_caption_copied` added. i18n via `t` from `lib/i18n` (aliased `msg` in the file).

**M5 — "How did you hear about us?"**
Placement: `DownloadLearningPrompt.tsx` gains step 3 (options `ad`, `friend_told_me`, `friends_post`, `coach_or_group`, `gift`, `search`, `other`); `onSubmit` type (L18–22) widens; `app/api/jobs/[jobId]/download-insight/route.ts` validates via a new `isDownloadHeardFrom`; `completeDownloadLearning` and `DownloadLearning` (`lib/download-learning.ts`) gain `heardFrom`; `buildDownloadLearningSummary` counts it for the existing "Why paying customers download" panel. n ≈ 30 responses/month (GA4: 32 users), so it is read as counts, never as a ratio gate.

**M6 — Individual vertical landers.**
`Hero.tsx` derives copy from `LANDING_VARIANTS[variant].hero` and has no override prop (L12–31), and `LANDING_VARIANTS` is typed by `LandingVariantName = "default" | "women" | "pet"`. Cheapest correct path: add an optional `copy?: Partial<LandingVariantConfig["hero"]>` prop to `Hero` (and `CTA`) merged over `cfg.hero`; `app/for/real-estate` and `app/for/direct-sales` pass `variant="women"` plus overrides; jobs stay `variant="women"` and are split by `acquisition.landingPath`. No new `LandingVariantName`, no migration. Add `/for/*` to `publicPaths` in `app/sitemap.ts` (note `/for/women` and `/pet` are not in it today).

**M7 — Seat-pack demand test (no code).** Stripe Payment Link with quantity → founder issues N gift codes with `scripts/issue_gift_codes.ts`. Orgs table only if ≥3 offices pay within 60 days.

**M8 — Day-10 nudge + one-time friend blast (the falsification test).**
Nudge: new branch in `drip-reminder` (or a daily `share-nudge` route): paid, `paidAmountCents>0`, downloaded (`downloadLearning.events.length>0`), `completedAt` ≥10 days, `reminderStep<2`, not opted out → `sendShareNudgeEmail` (idempotent `share-nudge:<id>`): "Know someone who needs one? Send them headshot-generators.com/friend — nothing in it for you." plus the file-share suggestion and a Google/Trustpilot review link. Query via a lean PostgREST projection (`select("data->id, data->customerEmail, …")`, `.filter("data->>paid","eq","true")`, 14-day `updated_at` window), not `listRecentJobs`. Blast: one admin-triggered send (pattern of `send-feedback-request`) to every buyer still within 90-day retention (~150 reachable), link `/friend?via=blast`, tracked clicks and downstream uploads/paid over 30 days.

**M9 — Refresh cadence (frequency lever, cheap).**
Jobs are deleted at 90 days (cleanup cron), so an 11-month "time to refresh" email needs an email-keyed record: `customers` table (email, first_paid_at, last_tier, variant, opt_out) written in the webhook. A monthly cron sends "New year, new photo" (January) and the 11-month refresh. It first reads in mid-2027; it is ~0.75 day and also serves partner payout and gift-buyer lookups. The dormant `subscriptionOnResults` flag and the `monthly-drops`/`send-drop-emails` subscriber crons exist; neither is a contagion lever and neither is flipped here (a subscription cohort test belongs after the AOV work, one test at a time).

**M10 — Analyzer share card.** `/linkedin-photo-analyzer` already scores a photo /10 via `/api/analyze`; add a copyable/shareable result card and OG image showing score and dimensions only, never the photo, with "see how the headshot version scores" → `/upload?via=analyzer`. Zero face exposure; the forwardable Practical-Value asset partners can hand out.

**M11 — Hosted "Help Me Pick" (conditional, Phase 5 only).** Paid-only, separate token, faceless OG, votes in their own table, ≤300px, 30-day expiry inside the 90-day retention. Not before the §6 gates.

## 5. Loop math

Base: 57 paid/month (Sept 21 window); ~390–630 completed previews/month (GA4 387 users; 57/0.09 = 633). AOV $27–29 (74% at $29, some $19, some $49/$79; recompute from Stripe day 0). Contribution per $29 order ≈ $25 before the ~74% quality-retry rate is costed (Stripe ~$1.14; generation $2–3 per order is an estimate, pull from Replicate/Gemini). Partner Pro order after 15% discount, 30% net commission, fees and generation ≈ $13.5. Source class: **A** first-party, **B** research digest (unsourced in this doc), **C** assumption.

| Assumption | Class | Conservative | Base | Optimistic |
|---|---|---|---|---|
| Partners recruited by day 90 (from ~60 outreach + seeds) | C (cold-outreach accept rates are B) | 2 | 4 | 8 |
| Share active (≥1 sale) | C (the ReferralCandy 83% figure is about consumer referrers and no longer used) | 50% | 50% | 60% |
| Sales per active partner / month | C, no evidence | 0.3 | 0.6 | 1.5 |
| **Partner-attributed paid/month at day 90** | product | 0.3 | 1.2 | 7.2 |
| Partner CAC (30% of net + 15% discount, Pro) | terms | $11.75 | $11.75 | $11.75 (vs FB CPA $29–64, placeholder $48) |
| Gift purchases as % of paid orders | C; /pet has no gift field, so the prior is pet paid orders since 2026-09-08 vs pet previews (pull day 0) and gifting-ad CTR 7–11% (A) | 0.3% | 1% | 3% |
| **Gift paid/month** | ×57 | 0.2 | 0.6 | 1.7 |
| Gift redemption within 12 months | C (HeadshotPro 87.6% is B and HR-mandated) | 60% | 70% | 80% |
| → New users created by gifts / month | product | 0.1 | 0.4 | 1.4 |
| Gift refund rate (recipient dissatisfaction under the guarantee + unredeemed refunds) | C | 25% | 15% | 10% |
| **Gift net paid/month** | product | 0.15 | 0.5 | 1.5 |
| Lander incremental paid/month | C (NAR persona figures are B) | 0 | 0.3 | 1.5 |
| Buyer share action rate (native/copy), lifted by the day-10 nudge | A: GA4 1/45 ≈ 2%; upper values B | 2% | 5% | 10% |
| Recipients per share | B | 1.5 | 2 | 3 |
| Recipient → completed preview | B/C | 1% | 2.5% | 5% |
| Completed → paid (referred) | A: 9–12% first-party | 9% | 10% | 12% |
| Refund rate on referred orders vs baseline | C: friends are the harshest likeness judges at identity ~8/10 | 3× | 2× | 1.5× |
| Spoken/pasted answer visitors per buyer | C: 30%×30%×50%×2 clicks | 0.02 | 0.05 | 0.15 |
| **Buyer→buyer K** | product | 0.00005 | 0.0004 | 0.003 |
| **Customer-share paid/month** | 57 × K | 0.003 | 0.02 | 0.17 |
| **Total incremental paid/month at day 90** | sum (gross) | **0.5** | **2.1** | **10.5** |
| Same, gift-refund-adjusted | | 0.45 | 2.0 | 10.3 |
| Share of orders at day 90 (incl. gifts / excl. gifts) | ÷ (57 + incremental) | 0.9% / 0.5% | 3.6% / 2.6% | 15.7% / 13% |
| Cumulative partner+gift+lander orders by day 120 (base ramp: partners from day 14 → 4 at day 90, gifts from day 21, landers from day 42) | integral | ~1.5 | ~5.5 | ~20 |

Negative-WOM cost: each unhappy referred or gifted recipient tells ~2 people; at these volumes that is cents per month in dollars, which is exactly why the same-day pause rule (§6) is behavioural, not financial. The baseline refund rate is not in this doc; pull it from Stripe day 0.

Power note: any test expressed as polls, invitee previews or a +3pt conversion lift needs 6–17 months (1,600–40,000 previews/arm). Every gate in §6 is therefore a count with its false-pass probability stated.

## 6. Phased rollout

**Phase 0 — Close the leaks (day 0–1, ~0.5 agent-day, no strategy dependency).** M0(a)–(d). Prod walk: unpaid preview job → `GET /api/jobs/<id>` contains no `/api/blob`; `/api/blob?url=<its blob>` still 200 only for URLs no unpaid response exposes; `POST /api/coupon/redeem` → 404; `/refer` → 301; `/upload?ref=FAMILY200` shows no banner and prefills nothing; one $0 self-test through Stripe test mode. Gate: none.

**Phase 1 — Rail, baselines, zero-privacy-surface pieces (week 1–2, ~3.5 agent-days).** M1, M4, M5, M8, download-triggered upgrade email, /stats acquisition panel. Day-0 pulls: one-window ROAS and headshot-only ROAS; GA4 `share ÷ purchase` (≈2%); `company_team` share of `intendedUse`; pet paid since 2026-09-08; Stripe refund rate; GA4 Direct (301) and Organic Search (6) sessions and Search Console branded impressions as the WOM baseline. Prod walk: real iPhone Safari, iPhone FB in-app browser (open the results email link from Messenger), Android Chrome, desktop Chrome — `navigator.share({files})` either shares or the fallback shows; `/friend` sets `hs_acq` source=friend; a test order with `?partner=TEST` shows `acquisition_partner` in the Stripe session and payment intent and in /stats. Gate to Phase 2a: that test order. Flag freeze: none of these is a bucketed experiment; nothing pre-purchase changes.

**Phase 2a — Partner program (weeks 2–3, ~2.5 agent-days + 2 h/week outreach).** M2, `partners` table, `charge.refunded` handler, payout report. Starts outreach day 14.
**Phase 2b — Gift seat (weeks 3–4, ~3.5 agent-days), gated on the blast.** Build M3 only if the M8 blast (~150 recipients) yields ≥5 `/friend` clicks (≈3%) or ≥1 recipient upload within 14 days. Under a 1% click rate P(≥5) ≈ 2%; under 5% ≈ 87%. If it fails, the gift page is deferred and the agent-days go to AOV.
Day-60 checkpoint (leading indicators only): ≥4 partners recruited, ≥100 partner-link landings, ≥300 `/gift` visits with ≥5 `gift_checkout_started`, blast CTR recorded. Segment kill: stop a partner segment after 10 non-responses. Expected base-case *outcomes* at day 60 are ~0.7 partner sales and ~0.8 gifts, so no outcome gate sits here.

**Phase 3 — Landers, refresh table, analyzer card, seat-pack test (weeks 4–6, ~2 agent-days).** M6, M7, M9, M10. Review link rides the M8 nudge (automated), not `sendFeedbackRequestEmail`, which is only sent by the manual admin blast. Prod walk: each lander → upload → paid test order carries `acquisition_landing`. Gate: lander ≥1% visit→checkout after 500 visits, else out of the sitemap; ≥3 offices pay for packs within 60 days → orgs table (~8 days, Phase 5), else never.

**Phase 4 — Day-120 read (outcome gate).** Cumulative partner+gift+lander Stripe-attributed orders since day 14: **≥3 → proceed** (P ≈ 91% under the base expectation of 5.5; ≈19% under a dead-channel rate of 1.5), scale outreach, add Rewardful/Dub; **<2 → kill** the program (keep rail, copy, gift page, customers table) and redirect agent-days to completed→paid and AOV. `heard_from`: ≥6 friend-type responses of ~60 pooled (P ≈ 88% if the true rate is 15%, ≈8% if 5%) is corroborating evidence, never the deciding gate. Partner discount: reviewed here on counts; paused earlier only for abuse (same email/IP patterns), not for conversion.

**Phase 5 — Conditional.** M11 only when native-share ≥8% of buyers **and** friend-type `heard_from` ≥6/60 **and** paid base >300/month. Orgs table only on the Phase 3 gate.

Same-day pause for any surface: any privacy complaint, any refund citing pressure or a gift recipient's dissatisfaction voiced publicly, any Stripe/Meta compliance flag.

## 7. Build list (reuse vs new, with estimates)

| Item | Files / systems | Reuse | New | Est. |
|---|---|---|---|---|
| Leak closure | `app/api/jobs/[jobId]/route.ts` L69–77; `app/api/checkout/route.ts` L177–184; `image-feedback/route.ts` L71–82; `UploadPageClient.tsx` L317–336; `ResultsPageClient.tsx` L746–761; delete `app/refer/*`, `app/api/coupon/redeem/route.ts`; Vercel env `COUPON_CODES`/`COUPON_STRIPE_IDS` | `result/[index]` watermark route, `known` allowlist, `feedbackRequestSentAt` | `/refer` redirect; `tests/test_job_response_privacy.ts` cases; `tests/test_image_feedback_unlock_gate.ts` | 0.5 d |
| Acquisition rail | `lib/acquisition.ts` (`partner?`, `p` in serialize/parse, `via`/`partner` in `hasExplicitAcquisitionTouch`, source mapping); `proxy.ts maybeSetAcquisition`; `app/api/jobs/route.ts` L113; `checkout/route.ts` L83–91, `checkout/redirect` L148–160, `checkout/upgrade/redirect` L172–183 | cookie plumbing; `tests/test_acquisition.ts`, `tests/test_checkout_attribution_metadata.ts` | `hs_partner` cookie (60d, first-touch); `acquisition_partner`, `acquisition_content` (not spread today); `payment_intent_data.metadata`; `/friend` route | 1 d |
| /stats panel | `app/api/admin/stats/route.ts` (already pages Stripe `checkout.sessions.list` since a cutoff, L8–40, and calls `listRecentJobs(30)`), `app/stats/StatsClient.tsx` | Stripe session reads; existing jobs fetch for `heard_from` | "Acquisition" panel from Stripe session metadata (`payment_status=paid`, `amount_total>0`, exclude `stripeSessionId` prefixes `feedback-unlock-`, `coupon:`, `gift:`) by source/medium/partner 30/90d; `gifts` and `partners` counts; payout due. No new jsonb scan. | 0.5 d |
| Post-purchase card | `ResultsPageClient.tsx` L1702–1749 → `app/results/[jobId]/components/PostPurchaseActions.tsx`; `lib/analytics.ts trackShare` L414 | `/api/jobs/[jobId]/result/[i]?download=1`, `t` i18n, `appendVariantParam`, `trackGenerateMoreClick` | component; platform union `native|copy|fb_caption`; `friend_link_copied`, `fb_caption_copied` | 0.75 d |
| Ready-email block | `lib/email.ts sendHeadshotsReadyEmail` L250+ full branch, `renderBrandedEmail` | `ready-email:<id>:full` idempotency | copy block | 0.25 d |
| Heard-from question | `lib/download-learning.ts`, `DownloadLearningPrompt.tsx` L18–22, `app/api/jobs/[jobId]/download-insight/route.ts`, `lib/store.ts mutateDownloadLearning` | persistence path, `tests/test_download_learning*.ts` | `heardFrom` field, validator, step 3, summary count | 0.5 d |
| Day-10 nudge + blast | `app/api/cron/drip-reminder/route.ts` (or `share-nudge`), `lib/email.ts`, `app/api/admin/send-friend-blast/route.ts` on the `send-feedback-request` pattern | `reminderStep`, `emailOptOut`, `isCronAuthorized`/`isAdminAuthorized`, `tests/test_drip_reminder_cron.ts` | `sendShareNudgeEmail` (`share-nudge:<id>`), lean projection query in `lib/store.ts`, blast route | 0.75 d |
| Upgrade email on download | `lib/email.ts`, drip cron branch (24h after first `downloadLearning.events[0]`), PR #29 upgrade route | cron, queue on failure | `sendUpgradeAfterDownloadEmail` (`upgrade-nudge:<id>`) | 0.5 d |
| Partners + gifts + suppressions data | `supabase/migrations/008_partners_gifts_suppressions.sql` (run in dashboard like 004) | `lib/supabase-server.ts` | `partners`, `gifts` (with `deliver_at`, `sent_at`, `redeemed_job_id`), `email_suppressions`, `customers`; `lib/partners.ts`, `lib/gifts.ts` | 0.75 d |
| Partner page, discount, payout | `app/partners/page.tsx`, `checkout/route.ts` L166 + `checkout/redirect` L184 discount branch, payout report in /stats, `docs/partners/outreach.md` | branch exists; `getStripePaymentParams` GBP ⇒ `percent_off` | one 15% Stripe coupon (`PARTNER_CLIENT_COUPON_ID`); partner validation; self-buy guard via `getPaidJobsByEmail` filtered `paidAmountCents>0`; `partner_discount_shown` | 1.75 d |
| Refund handling | `app/api/webhooks/stripe/route.ts` (handles only `checkout.session.completed` + subscription events today) | `refunded`, `stripeRefundId` already in `updateJob` allowlist (`lib/store.ts` L322–323) and set by `run-generation` auto-refund; `auditLog` | `charge.refunded` branch reading `charge.metadata.jobId` → `refunded:true, stripeRefundId` | 0.25 d |
| Gift checkout + fulfilment | `app/gift/page.tsx` + `GiftOccasions.tsx`, `app/api/gift/checkout/route.ts`, webhook branch beside `metadata.reelId` (L96–130), `app/api/jobs/route.ts` (`?gift=` → `setJobPaid(id,'gift:<id>',…)` + `generationMode:'full'`), `UploadPageClient.tsx` (`headshot_gift_code`), `app/api/cron/gift-deliveries`, `app/api/email/unsubscribe?token=` | `lib/stripe`, `getStripePaymentParams`, `Occasions` layout, `setJobPaid`, `runBackgroundGeneration`, `enqueueRenderedEmail` on failure only | lander, checkout, webhook branch, email template, delivery cron, unsubscribe route, `GIFT_FROM_EMAIL` subdomain | 3.5 d |
| Landers | `components/landing/Hero.tsx` (+ `CTA.tsx`) `copy` prop; `app/for/real-estate/page.tsx`, `app/for/direct-sales/page.tsx`; `app/sitemap.ts publicPaths` | `app/for/women/page.tsx` layout, `womenVariant` | prop + two pages; `tests/test_landing_variants.ts` case | 0.75 d |
| Refresh cadence | webhook → `customers`; `app/api/cron/refresh-reminder` monthly | cron auth, email helpers | table write, one template | 0.75 d |
| Analyzer share card | `app/linkedin-photo-analyzer/AnalyzerClient.tsx`, OG route | `/api/analyze` result shape (`overallScore`, dimensions) | score-only card + OG | 0.5 d |
| Flags | `flags.ts` | `flag()` + `vercelAdapter`, all `decide` constants (no bucketing) | `partnerDiscount`, `giftSeat`, `postPurchaseActionsV2` kill switches; add to the inline mock list in `tests/test_flags.ts` (it does not import `flags.ts`) | 0.25 d |
| Scripts/docs | `scripts/issue_gift_codes.ts`, `docs/partners/` | — | new | 0.25 d |

**Total ≈ 12 agent-days** (Phase 0: 0.5 · Phase 1: 3.5 · Phase 2: 6 · Phase 3: 2), planned as 12–16 elapsed. Not touched: `result/[index]/route.ts` watermark logic, paid output, `PREVIEW_STYLE_COUNT`.

## 8. Instrumentation end-to-end

1. **URL** — `?partner=CODE`, `?via=friend|gift|nudge|blast|analyzer`, `/friend` (→ `/?via=friend`), `/upload?gift=CODE`. GA4 records landing `page_location` (confirm query params are retained on this property).
2. **Cookie** — `proxy.ts maybeSetAcquisition`: `hs_acq` (30d, last-touch) is rewritten when absent, on any explicit touch, **or on any external referrer** (`isExternalAcquisitionReferrer`), so it cannot hold partner credit; new `hs_partner` (60d, httpOnly, set only when absent). Prefetches excluded.
3. **Job** — `app/api/jobs/route.ts` copies `resolveRequestAcquisition` and now `hs_partner` → `job.acquisition = { source, medium, content, partner, landingPath, device }`. Gift redemptions set `source=gift, content=<giftId>`.
4. **Stripe** — all three checkout routes spread `acquisition_source/medium/campaign/landing/device` (existing) plus `acquisition_partner`, `acquisition_content`, mirrored into `payment_intent_data.metadata`; gift sessions carry `giftId`, `gift_buyer_source`.
5. **Webhook** — `checkout.session.completed` as today; new `charge.refunded` → `refunded`, `stripeRefundId`.
6. **/stats** — acquisition panel from Stripe sessions (already fetched for the 7-day funnel), `partners`/`gifts` tables, `heard_from` from the existing `listRecentJobs(30)` call; payout due = 30% × net paid, 30-day hold, excludes `refunded`. Egress rule: no new full-jsonb scans; any new cron uses jsonb filters and projections (the project was suspended for egress on 2026-06-25).
7. **GA4** — `share` (platform), `friend_link_copied`, `fb_caption_copied`, `heard_from`, `gift_checkout_started`, `partner_discount_shown`; read beside Stripe, never the FB dashboard (over-attributes ~1.6×).
8. **WOM outcome proxies** — monthly: GA4 Direct sessions (baseline 301), Organic Search (6), Search Console branded impressions/clicks, `/friend` landings, `heard_from` counts. Blind spots: FB/Messenger in-app WebViews partition cookies (a friend who later types the domain into Safari arrives as `direct`; plausible, unverified — the Phase 1 device walk checks it); offline WOM carries no link.

## 9. What not to build (and why)

- **Hosted "Help Me Pick" poll pages (all four variants)** — measured share propensity ~2%; FB/Messenger/iMessage cache the OG collage so "revoke → 410" is a false promise; the OG preview answers "which one?" in-thread so the page is never visited; friends are the harshest likeness judges at identity ~8/10 and "doesn't look like you" becomes a money-back claim; the mechanic forces AI disclosure to the audience she paid to impress; every gate needs 6–24 months at this volume.
- **FRIEND10 / any cookie- or query-param-keyed discount** — a public code without server validation is the FAMILY200 class; a reusable promotion code under `allow_promotion_codes:true` is redeemable by every buyer once an aggregator indexes it.
- **Free clean HD image for referred previewers** — visibly unwatermarked previews produced 0/26 and 0/11 paid days (`lib/run-generation.ts` L404–414); note the clean-file bypass exists *today* through the job JSON and is closed in Phase 0, so this would reopen a hole just shut.
- **Pre-purchase "does this look like me?" polls** — preview is one image by design; the share object is a watermarked doubt inside a 7-day unpaid TTL.
- **Roster Loop as written (orgs table, manage page, composite, seat ladder, colleague invites)** — premise unverified, 1099 realtors/uplines don't buy for others, employer-directed face processing, unsolicited invite mail on the transactional domain, 20–25 real agent-days on the path that broke twice this month.
- **Sender lottery** — entry conditioned on a third party's purchase is an illegal-lottery pattern and a strike vector for an already-flagged ad account.
- **Flipping `subscriptionOnResults` or seasonal drops as a "contagion" lever** — they are frequency/LTV tools with no share mechanic; a subscription cohort test belongs after AOV, one test at a time per `flags.ts`.
- **Vote-back crons, retargeting vote-page visitors, brand marks on paid output, repurposing `?ref=`, repurposing `email_send_queue` as a scheduler** — no measurable yield, or direct conflict with the buyer's discretion motive, or misuse of a retry queue.

## 10. Open questions only the founder can answer

1. **Payouts**: Rewardful/Dub (~$49–59/month) vs a homegrown monthly report with manual PayPal. `lib/company.ts` says Parsill LLC, Wyoming — so W-9 collection and 1099-NEC above $600 apply; is there a PayPal business account under the LLC, or does the India/US setup complicate US payouts?
2. **Client discount**: 15% partner-client discount (CAC $11.75) or commission-only (CAC $8.70), given the AOV push toward $34?
3. **Sending domain**: DNS access this week for a second Resend subdomain for gift/nudge/blast mail?
4. **Reviews**: does a Google Business Profile or Trustpilot page exist to point the nudge email at?
5. **Outreach capacity**: ~2 h/week for 90 days? If not, partner channel = reviewer/SEO-only via the self-serve page.
6. **Brand name**: register a short, sayable redirect domain for the spoken answer?
7. **Seat-pack demand test**: Phase 3 or after the partner channel reads?
8. **Q4 family/holiday portrait SKU** on the women variant (~8 weeks out; gift-native; the only multi-person occasion for this cohort) — in scope this year? It would ride the `/gift` lander and the `customers` table.
9. **Self-test codes**: keep *any* 100%-off code in prod, or only single-use Stripe promotion codes in test mode (recommended)?
10. **Refresh table now?** ~0.75 day for a lever that first reads mid-2027 but also underpins payouts and gift lookups.

## Appendix — critic findings not adopted as written

- `hooks/useResultsJob.ts` L18–19 does not exist on origin/main; the owner-token read is at `app/results/[jobId]/hooks/useResultsJob.ts` L19 — the conclusion (device-local token blocks cross-device redemption) stands and led to deleting the redeem route rather than gating it.
- "FB CPA ≈ $48 = $2,283 / 48" divides a Sept-7 spend window by a Sept-21 order count; it is shown as a $29–64 range with $48 as placeholder, not as a fact.
- Everything else was accepted and is reflected above.