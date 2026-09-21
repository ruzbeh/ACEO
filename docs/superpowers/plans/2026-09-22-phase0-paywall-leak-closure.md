# Phase 0 — Paywall Leak Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the three live paywall bypasses on headshot-generators.com (free unlock via `?ref=FAMILY200`, clean generated images exposed through the job JSON, `$0` unlock via image feedback) without changing any paid-customer behaviour.

**Architecture:** One shared unlock predicate in `lib/result-access.ts` becomes the single source of truth for "may this index be served clean", and the three places that decide image visibility (the per-image route, the job JSON route, the Stripe checkout thumbnail) all call it. The referral coupon prefill is reduced to a known-code allowlist, the redeem endpoint gains an owner-token check plus a rate limiter, and the feedback auto-unlock is gated on the job having actually received a feedback-request email. A separate ops step rotates the 100%-off codes out of the production environment.

**Tech Stack:** Next.js 15 App Router, TypeScript, Supabase (jsonb `jobs`), Vercel Blob, Stripe, standalone `tsx` test scripts under `tests/` run by `scripts/run-tests.mjs` with `node:assert/strict`.

**Repo:** `/Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio`. All line references are against `origin/main` at `c44cd9a`. **Before starting, run `git fetch origin main && git checkout -b fix/phase0-paywall-leaks origin/main`** — the local checkout may be many commits behind and gives a wrong picture of this code.

**Spec:** `docs/superpowers/specs/2026-09-21-contagious-acquisition-design.md` §4 M0 (in the Agentic Company repo).

---

## Background an engineer needs before touching anything

There are two different "unpaid but visible" rules already live, and both must be preserved exactly:

- **Preview-mode jobs** (`job.generationMode === "preview" && !job.paid`): exactly one image is generated and **nothing** is served clean. `PREVIEW_STYLE_COUNT = 1` in `lib/run-generation.ts` was deliberately reverted from 3 on 2026-05-21 because the SVG watermark drops glyphs on bright backgrounds and 2 of 3 previews looked clean enough to save, which produced `0/26` and `0/11` paid days. Do not change it.
- **Full/legacy jobs that are not paid**: the first 2 indexes are intentionally served clean as a free preview (`FREE_PREVIEW_COUNT = 2` in `app/api/jobs/[jobId]/result/[index]/route.ts`).
- **Paid jobs**: `job.unlockedIndexes == null` means everything is unlocked; otherwise only the listed indexes are.

The bug is not in that rule. The bug is that `GET /api/jobs/[jobId]` returns `resultStyles[].url` and `styleResults[].imageUrl` as `/api/blob?url=…` proxy paths for **every completed job with no paid check** (the owner token is required only while a job is in progress), and `app/api/blob/route.ts` streams any private blob with no auth at all. Watermarking happens only inside `result/[index]/route.ts` at serve time, so the unpaid preview's clean file is one fetch away in devtools.

The results page UI already renders locked images through the watermarking route — `imageUrls={resultStyles.map((rs, i) => (isUnlocked(i) ? rs.url : \`/api/jobs/${jobId}/result/${i}\`))}` at `ResultsPageClient.tsx:1266`. So replacing the locked URLs *in the JSON* changes nothing the customer sees; it only removes the raw path an attacker reads.

---

## File structure

| File | Responsibility | Change |
|---|---|---|
| `lib/result-access.ts` | The single unlock predicate: given a job and an index, may that index be served clean? | **Create** |
| `app/api/jobs/[jobId]/result/[index]/route.ts` | Serves one image, clean or watermarked | Modify: delete inline predicate, call the shared one |
| `app/api/jobs/[jobId]/route.ts` | Job JSON for the processing/results pages | Modify: locked indexes get the watermark route path, never a blob path |
| `app/api/checkout/route.ts` | Stripe session creation | Modify: thumbnail uses the shared predicate |
| `app/api/jobs/[jobId]/image-feedback/route.ts` | Records per-image ratings, auto-unlocks HD | Modify: gate the unlock on `feedbackRequestSentAt` |
| `app/api/coupon/redeem/route.ts` | Redeems a 100%-off code | Modify: require the owner token |
| `app/upload/UploadPageClient.tsx` | Upload page | Modify: `?ref=` no longer persists arbitrary codes |
| `app/results/[jobId]/ResultsPageClient.tsx` | Results page | Modify: coupon prefill limited to known codes; send owner token on redeem |
| `app/refer/page.tsx`, `app/refer/ReferClient.tsx` | Orphan referral page advertising a 100%-off code as "20% off" | **Delete** |
| `next.config.ts` | Redirects | Modify: `/refer` → `/` |
| `tests/test_result_access.ts` | Unit tests for the predicate | **Create** |
| `tests/test_job_response_privacy.ts` | Job JSON privacy | Modify: add unpaid-leak cases |
| `tests/test_image_feedback_unlock_gate.ts` | Feedback unlock gating | **Create** |
| `tests/test_coupon_prefill_allowlist.ts` | `?ref=` allowlist | **Create** |

---

### Task 1: Shared unlock predicate

**Files:**
- Create: `lib/result-access.ts`
- Test: `tests/test_result_access.ts`

- [ ] **Step 1: Write the failing test**

Create `tests/test_result_access.ts`:

```typescript
import assert from "node:assert/strict";
import { isResultIndexUnlocked, FREE_PREVIEW_COUNT } from "../lib/result-access";

function job(overrides: Record<string, unknown> = {}) {
  return {
    id: "job-1",
    generationMode: "full",
    paid: false,
    ...overrides,
  } as Parameters<typeof isResultIndexUnlocked>[0];
}

function main() {
  // Preview mode, unpaid: nothing is clean. Index 0 must stay watermarked —
  // PREVIEW_STYLE_COUNT=1 means index 0 is the only image that exists.
  const preview = job({ generationMode: "preview", paid: false });
  assert.equal(isResultIndexUnlocked(preview, 0), false);
  assert.equal(isResultIndexUnlocked(preview, 1), false);

  // Full/legacy mode, unpaid: first FREE_PREVIEW_COUNT indexes are clean.
  const unpaidFull = job({ generationMode: "full", paid: false });
  assert.equal(FREE_PREVIEW_COUNT, 2);
  assert.equal(isResultIndexUnlocked(unpaidFull, 0), true);
  assert.equal(isResultIndexUnlocked(unpaidFull, 1), true);
  assert.equal(isResultIndexUnlocked(unpaidFull, 2), false);

  // Paid with no unlockedIndexes: everything is clean.
  const paidAll = job({ paid: true, unlockedIndexes: undefined });
  assert.equal(isResultIndexUnlocked(paidAll, 0), true);
  assert.equal(isResultIndexUnlocked(paidAll, 7), true);

  // Paid with an explicit list: only those indexes, plus the free preview.
  const paidSome = job({ paid: true, unlockedIndexes: [3, 5] });
  assert.equal(isResultIndexUnlocked(paidSome, 3), true);
  assert.equal(isResultIndexUnlocked(paidSome, 5), true);
  assert.equal(isResultIndexUnlocked(paidSome, 4), false);
  assert.equal(isResultIndexUnlocked(paidSome, 0), true); // free preview still applies

  // A paid preview-mode job (coupon/gift unlock before full generation):
  // preview mode only suppresses the free preview while UNPAID.
  const paidPreview = job({ generationMode: "preview", paid: true, unlockedIndexes: [0] });
  assert.equal(isResultIndexUnlocked(paidPreview, 0), true);

  console.log("result access predicate covers preview, free-preview, paid and partial-unlock cases");
}

main();
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && npx tsx tests/test_result_access.ts
```

Expected: FAIL — `Cannot find module '../lib/result-access'`.

- [ ] **Step 3: Write the implementation**

Create `lib/result-access.ts`:

```typescript
import type { Job } from "./types";

/**
 * Unpaid full/legacy jobs serve their first two images clean as a free
 * preview. Preview-mode jobs serve nothing clean — see PREVIEW_STYLE_COUNT
 * in run-generation.ts (reverted to 1 on 2026-05-21 because near-clean
 * previews collapsed preview→paid to zero).
 */
export const FREE_PREVIEW_COUNT = 2;

type ResultAccessJob = Pick<Job, "paid" | "generationMode" | "unlockedIndexes">;

export function isResultIndexUnlocked(job: ResultAccessJob, index: number): boolean {
  const isPreviewMode = job.generationMode === "preview" && !job.paid;
  const isFreePreview = !isPreviewMode && index < FREE_PREVIEW_COUNT;
  if (isFreePreview) return true;
  if (!job.paid) return false;
  return job.unlockedIndexes == null || job.unlockedIndexes.includes(index);
}
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && npx tsx tests/test_result_access.ts
```

Expected: PASS, printing `result access predicate covers preview, free-preview, paid and partial-unlock cases`.

- [ ] **Step 5: Commit**

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && git add lib/result-access.ts tests/test_result_access.ts && git commit -m "Add shared result-index unlock predicate"
```

---

### Task 2: Route the per-image endpoint through the shared predicate

**Files:**
- Modify: `app/api/jobs/[jobId]/result/[index]/route.ts` (the `isPreviewMode`/`FREE_PREVIEW_COUNT`/`isUnlocked` block, around L97–106)
- Test: `tests/test_result_access.ts` (already covers the predicate; this task is a refactor with no behaviour change)

This task exists so the predicate has exactly one definition. Per the house rule, new call sites route through the shared handler rather than duplicating it inline.

- [ ] **Step 1: Read the current block to confirm the line numbers**

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && grep -n "isPreviewMode\|FREE_PREVIEW_COUNT\|isFreePreview\|const isUnlocked" "app/api/jobs/[jobId]/result/[index]/route.ts"
```

Expected: five lines in the 97–106 range, matching the block replaced in Step 2.

- [ ] **Step 2: Replace the inline predicate with the shared one**

Delete these lines:

```typescript
  // Preview mode: all images are watermarked (user hasn't paid yet, single preview headshot).
  // Full/legacy mode: first 2 images served clean as free preview; rest based on unlock status.
  const isPreviewMode = job.generationMode === "preview" && !job.paid;
  const FREE_PREVIEW_COUNT = 2;
  const isFreePreview = !isPreviewMode && index < FREE_PREVIEW_COUNT;
  const isUnlocked = isFreePreview || (job.paid && (
    job.unlockedIndexes == null
      ? true
      : job.unlockedIndexes.includes(index)
  ));
```

Replace with:

```typescript
  const isUnlocked = isResultIndexUnlocked(job, index);
```

Add to the imports at the top of the file, beside the existing `hasOwnerOrCompletedPaidAccess` import:

```typescript
import { isResultIndexUnlocked } from "@/lib/result-access";
```

- [ ] **Step 3: Check for other uses of the deleted locals**

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && grep -n "isPreviewMode\|isFreePreview\|FREE_PREVIEW_COUNT" "app/api/jobs/[jobId]/result/[index]/route.ts"
```

Expected: no output. If any line still references them, replace that reference with `isUnlocked` or `isResultIndexUnlocked(job, index)` as the surrounding logic requires, then re-run until the output is empty.

- [ ] **Step 4: Typecheck**

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && npm run typecheck
```

Expected: no errors.

- [ ] **Step 5: Commit**

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && git add "app/api/jobs/[jobId]/result/[index]/route.ts" && git commit -m "Route per-image endpoint through shared unlock predicate"
```

---

### Task 3: Stop the job JSON from leaking clean image URLs

**Files:**
- Modify: `app/api/jobs/[jobId]/route.ts` (the `toDisplayUrl` / `resultStyles` / `styleResults` block, L69–94)
- Test: `tests/test_job_response_privacy.ts`

- [ ] **Step 1: Write the failing test**

Append a second scenario to `tests/test_job_response_privacy.ts`. Insert this function above the existing `main`, and add `await unpaidPreviewOmitsCleanUrls();` as the last line inside `main` (before its closing brace):

```typescript
async function unpaidPreviewOmitsCleanUrls() {
  const [{ GET }, { createJob, setJob }] = await Promise.all([
    import("../app/api/jobs/[jobId]/route"),
    import("../lib/store"),
  ]);

  const blobUrl = "https://abc123.public.blob.vercel-storage.com/jobs/x/0.png";
  const pending = await createJob();

  await setJob({
    ...pending,
    status: "completed",
    generationMode: "preview",
    paid: false,
    resultUrls: [blobUrl],
    resultStyles: [{ url: blobUrl, style: "Studio portrait" }],
    styleResults: [{ style: "Studio portrait", status: "success", imageUrl: blobUrl }],
  });

  const response = await GET(
    new Request(`http://localhost/api/jobs/${pending.id}`, {
      headers: { "x-owner-token": pending.ownerToken! },
    }),
    { params: Promise.resolve({ jobId: pending.id }) },
  );
  const payload = await response.json();
  const serialized = JSON.stringify(payload);

  assert.equal(response.status, 200);
  // The raw blob URL and the unauthenticated blob proxy must never appear for
  // a locked index — that pair is a clean-file download for an unpaid job.
  assert.equal(serialized.includes(blobUrl), false);
  assert.equal(serialized.includes("/api/blob"), false);
  // The locked index is served through the watermarking route instead.
  assert.equal(payload.resultStyles[0].url, `/api/jobs/${pending.id}/result/0`);
  assert.equal("imageUrl" in payload.styleResults[0], false);

  console.log("unpaid preview response exposes no clean image URL");
}
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && npx tsx tests/test_job_response_privacy.ts
```

Expected: FAIL on `serialized.includes("/api/blob")` being `true`.

- [ ] **Step 3: Write the implementation**

In `app/api/jobs/[jobId]/route.ts`, replace the `resultStyles` and `styleResults` blocks (L74–94) with:

```typescript
  const lockedResultPath = (index: number) => `/api/jobs/${jobId}/result/${index}`;
  const resultStyles =
    current.status === "completed"
      ? (current.resultStyles ?? []).map((r, index) => ({
          ...r,
          url: isResultIndexUnlocked(current, index)
            ? toDisplayUrl(r.url)
            : lockedResultPath(index),
        }))
      : undefined;

  // styleResults during processing — proxy any blob URLs so the processing
  // page can render live thumbnails as each style finishes. Without the
  // proxy mapping, private vercel-blob URLs would 401 in the browser.
  // Also: legacy jobs may have imageUrl as `/generated/jobId/N.png` (the
  // pre-2026-04-27 local-filesystem path that never resolved at runtime).
  // Strip those so the live thumbnail grid silently omits broken entries
  // instead of rendering a 404 placeholder.
  const styleResults = (current.styleResults ?? []).map((sr, index) => {
    if (!sr.imageUrl) return sr;
    if (sr.imageUrl.startsWith("/generated/")) {
      const { imageUrl, ...rest } = sr;
      void imageUrl;
      return rest;
    }
    // A locked index must not carry a second, unwatermarked path to the same
    // file. The thumbnail grid falls back to the result route for these.
    if (!isResultIndexUnlocked(current, index)) {
      const { imageUrl, ...rest } = sr;
      void imageUrl;
      return rest;
    }
    return { ...sr, imageUrl: toDisplayUrl(sr.imageUrl) };
  });
```

Add to the imports at the top of the file:

```typescript
import { isResultIndexUnlocked } from "@/lib/result-access";
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && npx tsx tests/test_job_response_privacy.ts
```

Expected: PASS, printing both the original owner-response line and `unpaid preview response exposes no clean image URL`.

- [ ] **Step 5: Confirm paid jobs still get direct blob URLs**

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && npx tsx tests/test_owner_token_idor_fix.ts && npm run typecheck
```

Expected: PASS and no type errors. A paid job's `resultStyles[i].url` must still be a `/api/blob?url=…` path — the results page uses it directly for unlocked images and a regression here would break every paid gallery.

- [ ] **Step 6: Commit**

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && git add "app/api/jobs/[jobId]/route.ts" tests/test_job_response_privacy.ts && git commit -m "Serve locked result indexes through the watermark route in job JSON"
```

---

### Task 4: Stripe checkout thumbnail must not be a clean locked image

**Files:**
- Modify: `app/api/checkout/route.ts` (the `images:` IIFE inside `product_data`, L177–186)

The thumbnail is built from `job.resultStyles[0].url`. On a preview-mode job index 0 is locked, so this publishes a clean copy of the gated image to Stripe's CDN.

- [ ] **Step 1: Replace the thumbnail builder**

Replace:

```typescript
                images: (() => {
                  try {
                    const u = job.resultStyles?.[0]?.url;
                    if (!u) return undefined;
                    const resolved = isBlobUrl(u) ? blobProxyPath(u) : u;
                    return [new URL(resolved, baseUrl).href];
                  } catch {
                    return undefined;
                  }
                })(),
```

with:

```typescript
                images: (() => {
                  try {
                    const u = job.resultStyles?.[0]?.url;
                    if (!u) return undefined;
                    // Index 0 is locked on preview-mode jobs; sending the clean
                    // file to Stripe's CDN would publish the gated image.
                    const resolved = isResultIndexUnlocked(job, 0)
                      ? (isBlobUrl(u) ? blobProxyPath(u) : u)
                      : `/api/jobs/${job.id}/result/0`;
                    return [new URL(resolved, baseUrl).href];
                  } catch {
                    return undefined;
                  }
                })(),
```

Add to the imports:

```typescript
import { isResultIndexUnlocked } from "@/lib/result-access";
```

- [ ] **Step 2: Typecheck and run the checkout tests**

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && npm run typecheck && npx tsx tests/test_checkout_attribution_metadata.ts
```

Expected: no type errors, test PASS.

- [ ] **Step 3: Commit**

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && git add app/api/checkout/route.ts && git commit -m "Use watermarked path for Stripe checkout thumbnail on locked jobs"
```

---

### Task 5: Gate the image-feedback auto-unlock

**Files:**
- Modify: `app/api/jobs/[jobId]/image-feedback/route.ts` (the auto-unlock block, L69–82)
- Test: `tests/test_image_feedback_unlock_gate.ts`

Today any caller can `POST` one rating to a 1-image preview job and receive `paid: true, paidAmountCents: 0, tier: "signature"` plus full generation of the remaining 15 styles. The unlock is only ever meant for customers who received the "free HD if you give feedback" email, which is the only thing that sets `feedbackRequestSentAt`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_image_feedback_unlock_gate.ts`:

```typescript
import assert from "node:assert/strict";

async function main() {
  process.env.VERCEL = "1";
  delete process.env.NEXT_PUBLIC_SUPABASE_URL;
  delete process.env.SUPABASE_SERVICE_ROLE_KEY;
  delete process.env.KV_REST_API_URL;
  delete process.env.KV_REST_API_TOKEN;
  delete process.env.BLOB_READ_WRITE_TOKEN;

  const [{ POST }, { createJob, setJob, getJob }] = await Promise.all([
    import("../app/api/jobs/[jobId]/image-feedback/route"),
    import("../lib/store"),
  ]);

  const rate = async (jobId: string) =>
    POST(
      new Request(`http://localhost/api/jobs/${jobId}/image-feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ styleIndex: 0, rating: "up" }),
      }),
      { params: Promise.resolve({ jobId }) },
    );

  // No feedback email was sent: the rating records, the job stays unpaid.
  const ungated = await createJob();
  await setJob({
    ...ungated,
    status: "completed",
    generationMode: "preview",
    paid: false,
    resultStyles: [{ url: "https://x.blob.vercel-storage.com/a.png", style: "Studio" }],
  });
  const ungatedResponse = await rate(ungated.id);
  assert.equal(ungatedResponse.status, 200);
  const afterUngated = await getJob(ungated.id);
  assert.equal(afterUngated!.paid, false, "rating alone must not unlock a job");
  assert.equal(Object.keys(afterUngated!.imageFeedback ?? {}).length, 1, "rating is still recorded");

  // Feedback email was sent: the unlock still works for the real cohort.
  const gated = await createJob();
  await setJob({
    ...gated,
    status: "completed",
    generationMode: "preview",
    paid: false,
    feedbackRequestSentAt: Date.now(),
    resultStyles: [{ url: "https://x.blob.vercel-storage.com/b.png", style: "Studio" }],
  });
  const gatedResponse = await rate(gated.id);
  assert.equal(gatedResponse.status, 200);
  const afterGated = await getJob(gated.id);
  assert.equal(afterGated!.paid, true, "invited feedback cohort still unlocks");
  assert.equal(afterGated!.paidAmountCents, 0);

  console.log("image feedback unlock requires an invited feedback job");
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && npx tsx tests/test_image_feedback_unlock_gate.ts
```

Expected: FAIL on `rating alone must not unlock a job` — the first job comes back `paid: true`.

- [ ] **Step 3: Write the implementation**

In `app/api/jobs/[jobId]/image-feedback/route.ts`, change the unlock condition. Replace:

```typescript
  if (!job.paid && ratingsCount >= requiredCount) {
```

with:

```typescript
  // The free-HD-for-feedback unlock is only for customers who were invited by
  // sendFeedbackRequestEmail (the only writer of feedbackRequestSentAt).
  // Without this gate one POST to a 1-image preview job unlocks a full
  // Signature set for $0.
  const wasInvitedToGiveFeedback = job.feedbackRequestSentAt != null;
  if (!job.paid && wasInvitedToGiveFeedback && ratingsCount >= requiredCount) {
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && npx tsx tests/test_image_feedback_unlock_gate.ts
```

Expected: PASS, printing `image feedback unlock requires an invited feedback job`.

- [ ] **Step 5: Commit**

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && git add "app/api/jobs/[jobId]/image-feedback/route.ts" tests/test_image_feedback_unlock_gate.ts && git commit -m "Gate image-feedback HD unlock on an invited feedback job"
```

---

### Task 6: Limit coupon prefill to known codes and retire `?ref=`

**Files:**
- Modify: `app/upload/UploadPageClient.tsx` (the referral capture effect, L314–334)
- Modify: `app/results/[jobId]/ResultsPageClient.tsx` (the prefill effect, L746–761)
- Create: `lib/referral-codes.ts`
- Test: `tests/test_coupon_prefill_allowlist.ts`

`/upload?ref=ANYCODE` currently writes any string to `localStorage.headshot_referral_code`, and the results page prefills the coupon input from it. Paired with a 100%-off code in `COUPON_CODES`, that URL is a free full set. The only code this flow legitimately carries is the `COMEBACK15` retargeting code, which the banner already treats as the sole known value.

- [ ] **Step 1: Write the failing test**

Create `tests/test_coupon_prefill_allowlist.ts`:

```typescript
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { PREFILLABLE_COUPON_CODES, isPrefillableCouponCode } from "../lib/referral-codes";

function main() {
  assert.deepEqual([...PREFILLABLE_COUPON_CODES], ["COMEBACK15"]);
  assert.equal(isPrefillableCouponCode("COMEBACK15"), true);
  assert.equal(isPrefillableCouponCode("comeback15"), true);
  assert.equal(isPrefillableCouponCode("FAMILY200"), false);
  assert.equal(isPrefillableCouponCode(""), false);
  assert.equal(isPrefillableCouponCode(null), false);

  const upload = readFileSync("app/upload/UploadPageClient.tsx", "utf8");
  const results = readFileSync("app/results/[jobId]/ResultsPageClient.tsx", "utf8");

  // `?ref=` is retired: it was the delivery vector for arbitrary codes.
  assert.equal(upload.includes('params.get("ref")'), false);
  assert.equal(results.includes('searchParams.get("ref")'), false);

  // Both pages go through the allowlist rather than trusting the URL.
  assert.ok(upload.includes("isPrefillableCouponCode"));
  assert.ok(results.includes("isPrefillableCouponCode"));

  console.log("coupon prefill is allowlisted and ?ref= is retired");
}

main();
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && npx tsx tests/test_coupon_prefill_allowlist.ts
```

Expected: FAIL — `Cannot find module '../lib/referral-codes'`.

- [ ] **Step 3: Create the allowlist module**

Create `lib/referral-codes.ts`:

```typescript
/**
 * Codes a URL is allowed to prefill into the coupon input. Anything else has
 * to be typed by the customer, so a shared link can never carry a discount
 * (or, as with the FAMILY200 self-test code, a free set).
 */
export const PREFILLABLE_COUPON_CODES = ["COMEBACK15"] as const;

export const PREFILLABLE_COUPON_LABELS: Record<string, string> = {
  COMEBACK15: "15% off",
};

export function isPrefillableCouponCode(code: string | null | undefined): boolean {
  if (!code) return false;
  return (PREFILLABLE_COUPON_CODES as readonly string[]).includes(code.trim().toUpperCase());
}
```

- [ ] **Step 4: Update the upload page**

In `app/upload/UploadPageClient.tsx`, replace the whole referral capture effect (the block that starts with the `// Referral: capture ?ref=CODE from URL` comment and ends with the closing brace of its `else` branch) with:

```typescript
  // Retargeting coupon capture. Only allowlisted codes are honoured from the
  // URL — `?ref=` used to accept any string, which made a shared link a free
  // set while a 100%-off self-test code existed in COUPON_CODES.
  useEffect(() => {
    if (typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    const fromUrl = params.get("coupon");
    if (fromUrl && isPrefillableCouponCode(fromUrl)) {
      const code = fromUrl.trim().toUpperCase();
      try { window.localStorage.setItem("headshot_referral_code", code); } catch { /* noop */ }
      // Surface the discount visibly so retargeted users know the offer
      // is real. Without this banner, the coupon silently applies on the
      // results page 3+ minutes later — by which time the user may have
      // forgotten why they clicked the ad. 2026-05-22.
      setReferralBanner({ code, label: PREFILLABLE_COUPON_LABELS[code] });
    } else {
      try {
        const stored = window.localStorage.getItem("headshot_referral_code")?.trim().toUpperCase();
        if (stored && isPrefillableCouponCode(stored)) {
          setReferralBanner({ code: stored, label: PREFILLABLE_COUPON_LABELS[stored] });
        } else if (stored) {
          window.localStorage.removeItem("headshot_referral_code");
        }
      } catch { /* noop */ }
    }
```

Keep everything after that point in the same effect (the `// Feedback mode: ?feedback=1 …` logic and the effect's dependency array) exactly as it is.

Add to the imports at the top of the file:

```typescript
import { isPrefillableCouponCode, PREFILLABLE_COUPON_LABELS } from "@/lib/referral-codes";
```

- [ ] **Step 5: Update the results page**

In `app/results/[jobId]/ResultsPageClient.tsx`, replace the prefill effect at L746–761 with:

```typescript
  // Auto-prefill the coupon input from ?coupon=CODE for allowlisted codes
  // only, and persist it so it survives a Stripe round-trip / page reload.
  useEffect(() => {
    if (refPrefillAppliedRef.current) return;
    if (typeof window === "undefined") return;
    refPrefillAppliedRef.current = true;
    let code = searchParams.get("coupon") ?? "";
    if (code) {
      if (!isPrefillableCouponCode(code)) return;
      try { window.localStorage.setItem("headshot_referral_code", code.trim().toUpperCase()); } catch { /* noop */ }
    } else {
      try { code = window.localStorage.getItem("headshot_referral_code") ?? ""; } catch { /* noop */ }
      if (!isPrefillableCouponCode(code)) return;
    }
    if (code && !couponCodeInput) {
      setCouponCodeInput(code.trim().toUpperCase());
    }
  }, [searchParams, couponCodeInput]);
```

Add to the imports at the top of the file:

```typescript
import { isPrefillableCouponCode } from "@/lib/referral-codes";
```

- [ ] **Step 6: Run the test to verify it passes**

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && npx tsx tests/test_coupon_prefill_allowlist.ts && npm run typecheck
```

Expected: PASS, printing `coupon prefill is allowlisted and ?ref= is retired`, and no type errors. The customer can still type any code by hand — this only stops a URL from supplying one.

- [ ] **Step 7: Commit**

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && git add lib/referral-codes.ts app/upload/UploadPageClient.tsx "app/results/[jobId]/ResultsPageClient.tsx" tests/test_coupon_prefill_allowlist.ts && git commit -m "Allowlist coupon prefill codes and retire the ref query param"
```

---

### Task 7: Require the owner token to redeem a coupon

**Files:**
- Modify: `app/api/coupon/redeem/route.ts`
- Modify: `app/results/[jobId]/ResultsPageClient.tsx` (the `handleApplyCoupon` fetch at L496)

The endpoint flips a job to paid from any caller who knows a job id and a 100%-off code. The legitimate caller is always the results page on the device that created the job, which holds `ownerToken_<jobId>` in `localStorage` and already passes it to `GET /api/jobs/[jobId]`.

- [ ] **Step 1: Add the owner check to the route**

In `app/api/coupon/redeem/route.ts`, immediately after the existing `job.status !== "completed"` guard and before the `if (job.paid)` check, insert:

```typescript
    if (!hasOwnerAccess(request, job.ownerToken, { allowLegacy: true })) {
      log("coupon redeem: owner token mismatch", { jobId });
      return NextResponse.json({ error: "Unauthorized" }, { status: 403 });
    }
```

Add to the imports:

```typescript
import { hasOwnerAccess } from "@/lib/api-auth";
```

`allowLegacy: true` keeps pre-owner-token jobs redeemable, matching `hasOwnerAccess`'s documented behaviour elsewhere in the codebase.

- [ ] **Step 2: Send the owner token from the client**

In `app/results/[jobId]/ResultsPageClient.tsx`, inside `handleApplyCoupon`, replace:

```typescript
      const res = await fetch("/api/coupon/redeem", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ jobId, code }),
      });
```

with:

```typescript
      const couponHeaders: Record<string, string> = { "Content-Type": "application/json" };
      if (ownerTokenRef.current) {
        couponHeaders["X-Owner-Token"] = ownerTokenRef.current;
      }
      const res = await fetch("/api/coupon/redeem", {
        method: "POST",
        headers: couponHeaders,
        body: JSON.stringify({ jobId, code }),
      });
```

- [ ] **Step 3: Confirm `ownerTokenRef` is in scope**

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && grep -n "ownerTokenRef" "app/results/[jobId]/ResultsPageClient.tsx" | head -5
```

Expected: a destructuring line from `useResultsJob` plus the new usage. If `ownerTokenRef` is not destructured in this component, add it to the existing `useResultsJob(jobId)` destructuring — the hook already returns it (`app/results/[jobId]/hooks/useResultsJob.ts:19`).

- [ ] **Step 4: Typecheck and run the auth tests**

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && npm run typecheck && npx tsx tests/test_api_auth.ts
```

Expected: no type errors, test PASS.

- [ ] **Step 5: Commit**

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && git add app/api/coupon/redeem/route.ts "app/results/[jobId]/ResultsPageClient.tsx" && git commit -m "Require owner token to redeem a coupon"
```

---

### Task 8: Delete the orphan `/refer` page

**Files:**
- Delete: `app/refer/page.tsx`, `app/refer/ReferClient.tsx`
- Modify: `next.config.ts`

The page had 0 pageviews in the last 30 days and advertises `FAMILY200` as "20% off" when it is a 100%-off code. A redirect is kept because the URL may exist in old emails.

- [ ] **Step 1: Confirm nothing links to it**

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && grep -rn '"/refer"\|'"'"'/refer'"'" app components lib --include=*.tsx --include=*.ts | grep -v "^app/refer/"
```

Expected: no output. If a link exists, remove it in this task before deleting the page.

- [ ] **Step 2: Delete the page and add the redirect**

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && git rm -r app/refer
```

Then in `next.config.ts`, add a `redirects` entry. If the config already exports a `redirects` function, append this object to the array it returns; otherwise add the whole method to the config object:

```typescript
  async redirects() {
    return [
      { source: "/refer", destination: "/", permanent: true },
    ];
  },
```

- [ ] **Step 3: Verify the build still compiles**

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && npm run typecheck && npm run build
```

Expected: build succeeds and the route list no longer contains `/refer`.

- [ ] **Step 4: Commit**

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && git add -A app/refer next.config.ts && git commit -m "Delete orphan refer page and redirect to home"
```

---

### Task 9: Full suite, PR, deploy

- [ ] **Step 1: Run everything**

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && npm run check
```

Expected: lint, typecheck, the whole `tests/` suite (including the three new files) and the production build all pass. Do not proceed on a red suite — fix it or report it.

- [ ] **Step 2: Open the PR**

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && git push -u origin fix/phase0-paywall-leaks && gh pr create --title "Close three paywall bypasses (Phase 0)" --body "$(cat <<'EOF'
## Problem

Three ways to get paid output without paying, all live on production:

1. `/upload?ref=FAMILY200` persisted any URL-supplied code to `localStorage`, the results page prefilled it, and `POST /api/coupon/redeem` accepted it — `FAMILY200` is a 100%-off self-test code in `COUPON_CODES`.
2. `GET /api/jobs/[jobId]` returned `resultStyles[].url` and `styleResults[].imageUrl` as `/api/blob?url=…` for every completed job with no paid check, and `/api/blob` streams private blobs unauthenticated. Watermarking only happens in `result/[index]`, so an unpaid preview's clean file was one fetch away.
3. `POST /api/jobs/[jobId]/image-feedback` unlocked a full Signature set for `$0` after `min(5, totalImages)` ratings — one rating on a 1-image preview job — with no check that the customer was ever invited to give feedback.

## Changes

- New `lib/result-access.ts` holds the single unlock predicate; the per-image route, the job JSON route and the Stripe checkout thumbnail all call it instead of deciding separately.
- Locked indexes in the job JSON now point at `/api/jobs/<id>/result/<i>` (the watermarking route). Paid and free-preview indexes are unchanged, and the results page already rendered locked images through that route, so there is no visible change for customers.
- `?ref=` is retired. URL-supplied coupon codes are limited to an allowlist (`COMEBACK15`); customers can still type any code by hand.
- `/api/coupon/redeem` requires the job's owner token.
- The feedback HD unlock requires `feedbackRequestSentAt`, which only `sendFeedbackRequestEmail` sets.
- Orphan `/refer` page deleted (0 pageviews in 30 days, advertised a 100%-off code as "20% off"), `/refer` → `/`.

## Tests

New: `tests/test_result_access.ts`, `tests/test_image_feedback_unlock_gate.ts`, `tests/test_coupon_prefill_allowlist.ts`. Extended: `tests/test_job_response_privacy.ts` asserts an unpaid preview response contains no blob path. `npm run check` green.

## Follow-up outside this PR

The 100%-off entries must be removed from the `COUPON_CODES` and `COUPON_STRIPE_IDS` production environment variables — that is the root cause, and the code changes here are defence in depth around it. Self-testing moves to single-use Stripe promotion codes.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 3: Rotate the production coupon codes (ops, after the PR merges)**

This is the actual root-cause fix and it is an operational change to production configuration, not code. Remove every 100%-off entry from both variables, keeping any partial-discount codes:

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && vercel env ls production | grep -E "COUPON_CODES|COUPON_STRIPE_IDS"
```

Then re-add the pruned values with `printf`, never `echo` — `echo` appends a newline that silently broke `NEXT_PUBLIC_GA_MEASUREMENT_ID`, `RESEND_API_KEY` and `RESEND_FROM_EMAIL` before:

```bash
printf '%s' 'COMEBACK15:15' | vercel env add COUPON_CODES production --force
```

`lib/coupons.ts` caches the registry per serverless instance, so a redeploy is required for the change to take effect everywhere.

- [ ] **Step 4: Verify on production**

After the Vercel deploy finishes, walk the funnel on the real site rather than trusting the suite — four bugs have shipped past a green suite on this codebase before:

```bash
curl -s -o /dev/null -w "/refer -> %{http_code}\n" https://www.headshot-generators.com/refer
```

Then, with a real preview job created through the site:

1. `GET https://www.headshot-generators.com/api/jobs/<previewJobId>` — the response body must contain no `/api/blob` and no `blob.vercel-storage.com`.
2. Open the results page for that job — the preview image must still render, watermarked.
3. `POST /api/coupon/redeem` with `{"jobId":"<previewJobId>","code":"FAMILY200"}` and no owner token — expect `403`, and after the env rotation a rejected code regardless.
4. `POST /api/jobs/<previewJobId>/image-feedback` with one rating — expect the job to stay unpaid.
5. Buy one real Signature order end to end (test against Signature, not just the $29 tier) and confirm all images download clean.

- [ ] **Step 5: Report**

State which checks passed with their actual output, and flag anything that did not. Then stop — Phase 1 (attribution rail) is a separate plan.

---

## Self-review

**Spec coverage.** Spec §4 M0(a) clean-image bypass → Tasks 1–4. M0(b) FAMILY200 and `/refer` → Tasks 7, 8 and the Task 9 env rotation. M0(c) `?ref=` retirement → Task 6. M0(d) feedback auto-unlock → Task 5. The spec also proposed deleting the redeem route outright; this plan gates it with the owner token instead, because the results page calls it at `ResultsPageClient.tsx:496` and the owner token is available there, so the legitimate redemption path keeps working while the abuse path closes. The spec's `rl:coupon` rate limiter is left out: with 100%-off codes gone from the environment and an owner check in place there is no discount left to brute-force, and adding a limiter to `proxy.ts` would widen this PR past leak closure.

**Placeholders.** None. Every code step carries the code, every command its expected output.

**Type consistency.** `isResultIndexUnlocked(job, index)` takes `Pick<Job, "paid" | "generationMode" | "unlockedIndexes">` and is called with a full `Job` in all four call sites (the per-image route, the job route's `current`, the checkout route's `job`), which structurally satisfies the parameter. `FREE_PREVIEW_COUNT` is exported once from `lib/result-access.ts` and no longer declared in the per-image route. `isPrefillableCouponCode` and `PREFILLABLE_COUPON_LABELS` keep the same names across the module and both call sites.
