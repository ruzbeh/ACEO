# Phase 1b — Post-Purchase Surfaces Implementation Plan

> **MERGED 2026-09-22** as [PR #45](https://github.com/ruzbeh/headshot-studio/pull/45) (merge `622d19d`). `npm run check` fully green.
>
> **Two sends are deliberately withheld.** The day-10 cron is gated off behind `SHARE_NUDGE_ENABLED=1`: counting the real cohort before merging showed it would have emailed 48 customers within two hours, since everyone in the 14-day window is already past day 10. The one-time friend blast has not been sent either. Both are the founder's call.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give a happy customer something worth passing on, ask her where she came from, and run the cheap experiment that decides whether the gift product gets built at all.

**Architecture:** The dead X and LinkedIn buttons (1 use in 30 days, both sharing the homepage with a generic image) are replaced by a private share of her own photo files plus a short spoken-answer link. A third step on the existing download prompt asks how she heard about us, giving a first-party read on whether word of mouth exists. A day-10 email nudges the same share, and a one-time blast to existing buyers measures click-through on `/friend`. Outbound email links get `?via=` tags so email clients stop being recorded as traffic sources.

**Tech Stack:** Next.js 15 App Router, TypeScript, Supabase (jsonb `jobs`), Resend, standalone `tsx` test scripts under `tests/` run by `scripts/run-tests.mjs`.

**Repo:** `/Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio`. Line references are against `origin/main` at `de0f060`. **Before starting, run `git fetch origin main && git checkout -b feat/post-purchase-share origin/main`.** The local checkout drifts and misrepresents this code. Commit plainly with no `-c user.name`/`-c user.email` override — this repo's local config (`ruzbeh <ruzbeh.001234@gmail.com>`) is authorised on Vercel and an override makes Vercel refuse the deploy with "Deployment was blocked".

**Spec:** `docs/superpowers/specs/2026-09-21-contagious-acquisition-design.md` §4 M4, M5, M8 (in the Agentic Company repo). Depends on the Phase 1a rail, already merged in #42 and #44.

---

## Why this shape, given the evidence

Five independent reviewers of the strategy refuted the hosted "help me pick" poll, and the measured share rate backs them: one `share` event from about 45 purchasers in 30 days. So this phase deliberately builds **no public artefact and no hosted page carrying a customer's face**. Everything here is either private (files sent through her own apps), faceless (a short link, an email), or a question.

The honest expectation is near-zero direct virality: corrected buyer-to-buyer K is about 0.0004. The value is a measured share-rate baseline and a real answer to "does word of mouth exist here at all", both of which the partner and gift work in Phase 2 need before anyone spends days on them.

**One thing here is a real experiment with a decision attached.** The one-time blast in Task 6 goes to roughly 150 existing buyers. If it yields at least 5 `/friend` clicks or at least 1 recipient upload within 14 days, the gift seat gets built in Phase 2b. Under a true 1% click rate the probability of reaching 5 is about 2%; under 5% it is about 87%. That is a real test rather than a formality.

---

## Background an engineer needs before touching anything

- **The post-purchase card** lives inline in `app/results/[jobId]/ResultsPageClient.tsx` around lines 1708 to 1756, inside a `{paid && (...)}` block, as a four-cell grid: Customize again, Share on X, Share on LinkedIn, Generate more styles. The file is 2,033 lines, so the whole card is extracted to its own component rather than edited in place.
- **`trackShare`** (`lib/analytics.ts:414`) is typed `platform: "x" | "linkedin"`. The union has to widen, and every existing caller is inside the block being replaced.
- **The download prompt** (`app/results/[jobId]/components/DownloadLearningPrompt.tsx`) is a two-step modal holding `step`, `intendedUse`, `choiceReason` and `otherText` in local state, with an `onSubmit` prop typed to those three fields. `lib/download-learning.ts` owns the option lists, the validators (`isDownloadIntendedUse`, `isDownloadChoiceReason`), `completeDownloadLearning`, and `buildDownloadLearningSummary`, which `/stats` renders.
- **The drip cron** (`app/api/cron/drip-reminder/route.ts`, every 2 hours) calls `listRecentJobs(7)` once and loops it twice: paid delivery reminders, then abandoned-cart. Its paid branch requires `resultsViewedAt == null`, which is the opposite of what a share nudge wants, so the nudge is a third branch with its own eligibility. **Reuse the single fetch.** Supabase suspended this project for egress on 2026-06-25, so a second full scan every 2 hours is not acceptable; widen the existing window to 14 days instead.
- **Email templates** go through `renderBrandedEmail(opts: BrandedEmailOptions)` with `preheader`, `eyebrow`, `heading`, `intro`, optional `photoUrls`/`highlight`/`outro`, `ctaText`, `ctaUrl`, `unsubUrl`, optional `ctaColor`. `buildPaidResultsReminderEmail` (`lib/email.ts:471`) is the closest model: a paid-safe template with no coupon or unlock language. Senders follow `sendDripReminderEmail`: try Resend, and on error or exception call `enqueueRenderedEmail` so `flush-email-queue` retries.
- **Never send unlock or coupon copy to a paid customer.** `buildDripReminderEmail` opens by delegating to the paid-safe template for exactly this reason, and a chargeback dispute is recorded in the cron's comments from getting this wrong.
- **The `$0` trap.** Coupon redemptions and the feedback unlock produce genuine `paid` rows with `paidAmountCents: 0`. Anything selecting "customers" must require `paidAmountCents > 0`, or the blast goes to people who never paid.

---

## File structure

| File | Responsibility | Change |
|---|---|---|
| `lib/email-links.ts` | Tag outbound email URLs with `?via=` | **Create** |
| `lib/download-learning.ts` | Add the `heardFrom` field, options and validator | Modify |
| `app/api/jobs/[jobId]/download-insight/route.ts` | Accept and validate `heardFrom` | Modify |
| `app/results/[jobId]/components/DownloadLearningPrompt.tsx` | Third step asking how they heard | Modify |
| `app/results/[jobId]/components/PostPurchaseActions.tsx` | The whole post-purchase card: private share, spoken answer, upsell | **Create** |
| `app/results/[jobId]/ResultsPageClient.tsx` | Render the extracted component | Modify |
| `lib/analytics.ts` | Widen the share platform union, add the new events | Modify |
| `lib/email.ts` | `buildShareNudgeEmail` / `sendShareNudgeEmail`, `?via=` on links | Modify |
| `app/api/cron/drip-reminder/route.ts` | Day-10 share-nudge branch on the existing fetch | Modify |
| `app/api/admin/send-friend-blast/route.ts` | The one-time falsification blast | **Create** |
| `tests/test_email_links.ts` | `?via=` tagging | **Create** |
| `tests/test_download_learning.ts` | `heardFrom` round-trip and validation | Modify |
| `tests/test_post_purchase_actions.ts` | No homepage share, private share present | **Create** |
| `tests/test_share_nudge_email.ts` | Paid-safe copy, idempotency key, eligibility | **Create** |

---

### Task 1: Tag outbound email links with `?via=`

The `/stats` panel shipped in #42 showed `email.bt.com` as the source of a real order: a customer clicking our own email from her webmail, recorded as a referral from BT. Tagging our links fixes the artefact at the source and makes email-driven orders countable.

**Files:**
- Create: `lib/email-links.ts`
- Test: `tests/test_email_links.ts`

- [x] **Step 1: Write the failing test**

Create `tests/test_email_links.ts`:

```typescript
import * as assert from "assert";
import { withEmailVia } from "../lib/email-links";

// A bare URL gains the via tag.
assert.strictEqual(
  withEmailVia("https://www.headshot-generators.com/results/abc", "nudge"),
  "https://www.headshot-generators.com/results/abc?via=nudge",
);

// An existing query string is preserved.
assert.strictEqual(
  withEmailVia("https://www.headshot-generators.com/results/abc?variant=women", "nudge"),
  "https://www.headshot-generators.com/results/abc?variant=women&via=nudge",
);

// Already tagged: left alone rather than doubled.
assert.strictEqual(
  withEmailVia("https://www.headshot-generators.com/?via=friend", "nudge"),
  "https://www.headshot-generators.com/?via=friend",
);

// Only labels the rail accepts are allowed, so a typo cannot create a
// source that lib/partner-attribution.ts will silently drop.
assert.throws(() => withEmailVia("https://www.headshot-generators.com/", "not-a-label" as never));

// Unsubscribe links are never tagged: clicking one is not an acquisition.
assert.strictEqual(
  withEmailVia("https://www.headshot-generators.com/api/jobs/abc/unsubscribe", "nudge"),
  "https://www.headshot-generators.com/api/jobs/abc/unsubscribe",
);

// A malformed URL is returned unchanged rather than throwing inside a send.
assert.strictEqual(withEmailVia("not a url", "nudge"), "not a url");

console.log("email link via-tagging tests passed");
```

- [x] **Step 2: Run the test to verify it fails**

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && npx tsx tests/test_email_links.ts
```

Expected: FAIL with `Cannot find module '../lib/email-links'`.

- [x] **Step 3: Write the implementation**

Create `lib/email-links.ts`:

```typescript
import { VIA_LABELS, type ViaLabel } from "./partner-attribution";

/**
 * Tags an outbound email link so the click is attributed to the email rather
 * than to the recipient's webmail host. Without this, a customer clicking
 * through from BT webmail was recorded as a referral from email.bt.com — it
 * was the source of a real order in the 30 days to 2026-09-22.
 */
export function withEmailVia(url: string, via: ViaLabel): string {
  if (!(VIA_LABELS as readonly string[]).includes(via)) {
    throw new Error(`Unknown via label: ${via}`);
  }
  let parsed: URL;
  try {
    parsed = new URL(url);
  } catch {
    return url;
  }
  // Clicking unsubscribe is not an acquisition touch.
  if (parsed.pathname.endsWith("/unsubscribe")) return url;
  if (parsed.searchParams.has("via")) return url;
  parsed.searchParams.set("via", via);
  return parsed.toString();
}
```

- [x] **Step 4: Run the test to verify it passes**

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && npx tsx tests/test_email_links.ts
```

Expected: PASS, printing `email link via-tagging tests passed`.

- [x] **Step 5: Commit**

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && git add lib/email-links.ts tests/test_email_links.ts && git commit -m "Tag outbound email links with a via label"
```

---

### Task 2: Ask how they heard about us

The cheapest possible read on whether word of mouth exists. About 32 people see the download prompt per month, so this is read as counts and never as a ratio.

**Files:**
- Modify: `lib/download-learning.ts`
- Modify: `app/api/jobs/[jobId]/download-insight/route.ts`
- Test: `tests/test_download_learning.ts`

- [x] **Step 1: Write the failing test**

Append to `tests/test_download_learning.ts`, before its final `console.log`:

```typescript
// --- heardFrom ---------------------------------------------------------------
assert.strictEqual(isDownloadHeardFrom("friend_told_me"), true);
assert.strictEqual(isDownloadHeardFrom("ad"), true);
assert.strictEqual(isDownloadHeardFrom("nope"), false);
assert.strictEqual(isDownloadHeardFrom(undefined), false);

// heardFrom is optional: existing two-answer submissions still complete.
const withoutHeardFrom = completeDownloadLearning(undefined, {
  intendedUse: "linkedin",
  choiceReason: "looks_like_me",
});
assert.strictEqual(withoutHeardFrom.respondedAt != null, true);
assert.strictEqual(withoutHeardFrom.heardFrom, undefined);

// And it round-trips when supplied.
const withHeardFrom = completeDownloadLearning(undefined, {
  intendedUse: "linkedin",
  choiceReason: "looks_like_me",
  heardFrom: "friend_told_me",
});
assert.strictEqual(withHeardFrom.heardFrom, "friend_told_me");

// The summary counts them so /stats can show word-of-mouth signal.
const summary = buildDownloadLearningSummary([
  { paid: true, downloadLearning: withHeardFrom },
  { paid: true, downloadLearning: withHeardFrom },
  {
    paid: true,
    downloadLearning: completeDownloadLearning(undefined, {
      intendedUse: "linkedin",
      choiceReason: "looks_like_me",
      heardFrom: "ad",
    }),
  },
]);
assert.deepStrictEqual(summary.heardFromCounts.friend_told_me, 2);
assert.deepStrictEqual(summary.heardFromCounts.ad, 1);
```

Add `isDownloadHeardFrom` to that file's existing import from `../lib/download-learning`. The `downloadLearning` fixtures need whatever event shape the surrounding tests already use — check the top of the file and match it, since `buildDownloadLearningSummary` filters on `events.length > 0`.

- [x] **Step 2: Run the test to verify it fails**

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && npx tsx tests/test_download_learning.ts
```

Expected: FAIL — `isDownloadHeardFrom` is not exported.

- [x] **Step 3: Add the field to the model**

In `lib/download-learning.ts`, after `DOWNLOAD_CHOICE_REASON_OPTIONS`, add:

```typescript
export const DOWNLOAD_HEARD_FROM_OPTIONS = [
  { value: "ad", label: "An ad" },
  { value: "friend_told_me", label: "A friend or family member told me" },
  { value: "friends_post", label: "I saw someone's photo online" },
  { value: "coach_or_group", label: "A coach, recruiter or group I'm in" },
  { value: "gift", label: "It was a gift" },
  { value: "search", label: "I searched for it" },
  { value: "other", label: "Somewhere else" },
] as const;
```

Add the type beside the others:

```typescript
export type DownloadHeardFrom = (typeof DOWNLOAD_HEARD_FROM_OPTIONS)[number]["value"];
```

Add `heardFrom?: DownloadHeardFrom;` to the `DownloadLearning` type, after `choiceReason`. Add it as optional to `DownloadResponseInput`:

```typescript
type DownloadResponseInput = {
  intendedUse: DownloadIntendedUse;
  choiceReason: DownloadChoiceReason;
  otherText?: string;
  heardFrom?: DownloadHeardFrom;
};
```

Add the validator beside the existing two:

```typescript
export function isDownloadHeardFrom(value: unknown): value is DownloadHeardFrom {
  return DOWNLOAD_HEARD_FROM_OPTIONS.some((option) => option.value === value);
}
```

In `normalizeLearning`, carry it through alongside `choiceReason`:

```typescript
    ...(current?.heardFrom && { heardFrom: current.heardFrom }),
```

In `completeDownloadLearning`, persist it in the returned object, after `choiceReason`:

```typescript
    ...(response.heardFrom ? { heardFrom: response.heardFrom } : {}),
```

- [x] **Step 4: Count it in the summary**

In `buildDownloadLearningSummary`, build the counts and add them to the returned object:

```typescript
  const heardFromCounts: Record<string, number> = {};
  for (const job of responded) {
    const heardFrom = job.downloadLearning?.heardFrom;
    if (heardFrom) heardFromCounts[heardFrom] = (heardFromCounts[heardFrom] ?? 0) + 1;
  }
```

and inside the `return { ... }`:

```typescript
    heardFromCounts,
```

- [x] **Step 5: Accept it at the API**

In `app/api/jobs/[jobId]/download-insight/route.ts`, find where the body is validated against `isDownloadIntendedUse` and `isDownloadChoiceReason`:

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && grep -n "isDownloadIntendedUse\|isDownloadChoiceReason\|otherText" "app/api/jobs/[jobId]/download-insight/route.ts"
```

Add `isDownloadHeardFrom` to that import, and pass the field through to `completeDownloadLearning` **only when valid**, so a malformed value is dropped rather than rejecting the whole response:

```typescript
      ...(isDownloadHeardFrom(body.heardFrom) ? { heardFrom: body.heardFrom } : {}),
```

- [x] **Step 6: Run the tests and typecheck**

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && npx tsx tests/test_download_learning.ts && npx tsx tests/test_download_learning_persistence.ts && npx tsx tests/test_download_learning_routes.ts && npx tsx tests/test_download_learning_insights.ts && npm run typecheck
```

Expected: all PASS, no type errors. `heardFrom` is optional at every layer, so stored two-answer responses stay valid.

- [x] **Step 7: Commit**

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && git add lib/download-learning.ts "app/api/jobs/[jobId]/download-insight/route.ts" tests/test_download_learning.ts && git commit -m "Record how paying customers heard about us"
```

---

### Task 3: Third step on the download prompt

**Files:**
- Modify: `app/results/[jobId]/components/DownloadLearningPrompt.tsx`
- Modify: `app/results/[jobId]/ResultsPageClient.tsx` (the `onSubmit` handler that posts the response)

- [x] **Step 1: Widen the component contract**

In `DownloadLearningPrompt.tsx`, import the new option list and type:

```typescript
import {
  DOWNLOAD_CHOICE_REASON_OPTIONS,
  DOWNLOAD_HEARD_FROM_OPTIONS,
  DOWNLOAD_INTENDED_USE_OPTIONS,
  type DownloadChoiceReason,
  type DownloadHeardFrom,
  type DownloadIntendedUse,
  type DownloadKind,
} from "@/lib/download-learning";
```

Widen the `onSubmit` prop and the step state:

```typescript
  onSubmit: (response: {
    intendedUse: DownloadIntendedUse;
    choiceReason: DownloadChoiceReason;
    otherText?: string;
    heardFrom?: DownloadHeardFrom;
  }) => void;
```

```typescript
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [heardFrom, setHeardFrom] = useState<DownloadHeardFrom | null>(null);
```

- [x] **Step 2: Render the third step**

Read how step 2 renders its option list and its submit button:

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && grep -n "step === 2" -A 40 "app/results/[jobId]/components/DownloadLearningPrompt.tsx" | head -60
```

Then mirror that markup for a third step, changing three things: it maps `DOWNLOAD_HEARD_FROM_OPTIONS`, its heading asks "One last thing — how did you first hear about us?", and its button is the final submit. Step 2's submit becomes `onClick={() => setStep(3)}` with label "Next", and step 3 calls:

```typescript
onSubmit({
  intendedUse: intendedUse!,
  choiceReason: choiceReason!,
  ...(otherText.trim() ? { otherText: otherText.trim() } : {}),
  ...(heardFrom ? { heardFrom } : {}),
})
```

Keep the existing dismiss affordance on every step. **Step 3 must be skippable**: the submit button stays enabled with `heardFrom` unset, so someone who does not want to answer still records the first two answers rather than dropping out entirely. Match the existing `isWomen` styling branch.

- [x] **Step 3: Pass it through from the results page**

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && grep -n "download-insight\|DownloadLearningPrompt" "app/results/[jobId]/ResultsPageClient.tsx"
```

In the handler that POSTs to `download-insight`, include `heardFrom` in the JSON body when present. The handler's parameter type widens to match the component's `onSubmit`.

- [x] **Step 4: Typecheck and build**

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && npm run typecheck && npm run build
```

Expected: no type errors, build succeeds.

- [x] **Step 5: Commit**

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && git add "app/results/[jobId]/components/DownloadLearningPrompt.tsx" "app/results/[jobId]/ResultsPageClient.tsx" && git commit -m "Add a skippable how-did-you-hear step to the download prompt"
```

---

### Task 4: Replace the dead share buttons with a private share

The X and LinkedIn buttons share `window.location.origin` with a generic image, and were used once in 30 days. The replacement sends her actual photo files through whatever app she already uses, which is where the research says real sharing happens, and adds a short link she can say out loud.

**Files:**
- Create: `app/results/[jobId]/components/PostPurchaseActions.tsx`
- Modify: `app/results/[jobId]/ResultsPageClient.tsx` (lines ~1708 to 1756)
- Modify: `lib/analytics.ts`
- Test: `tests/test_post_purchase_actions.ts`

- [x] **Step 1: Write the failing test**

Create `tests/test_post_purchase_actions.ts`:

```typescript
import * as assert from "assert";
import { readFileSync } from "fs";

const component = readFileSync("app/results/[jobId]/components/PostPurchaseActions.tsx", "utf8");
const resultsPage = readFileSync("app/results/[jobId]/ResultsPageClient.tsx", "utf8");

// The homepage-sharing buttons are gone from both files.
for (const [name, source] of [["component", component], ["results page", resultsPage]] as const) {
  assert.ok(!source.includes("twitter.com/intent/tweet"), `${name} should not share to X`);
  assert.ok(
    !source.includes("linkedin.com/sharing/share-offsite"),
    `${name} should not share the homepage to LinkedIn`,
  );
}

// The private share sends her own files, gated on canShare.
assert.ok(component.includes("navigator.canShare"), "must feature-detect file sharing");
assert.ok(component.includes("navigator.share"), "must use the Web Share API");
assert.ok(component.includes("?download=1"), "must share the real image files");

// The spoken answer is a durable short link, and carries no discount.
assert.ok(component.includes("/friend"), "must offer the /friend link");
assert.ok(!/COMEBACK15|FAMILY/.test(component), "the share must not carry a coupon");

// The results page renders the extracted component instead of inline markup.
assert.ok(resultsPage.includes("PostPurchaseActions"), "results page should render the component");

// Instrumentation for the share-rate baseline.
const analytics = readFileSync("lib/analytics.ts", "utf8");
assert.ok(analytics.includes('"native"'), "trackShare should accept the native platform");
assert.ok(analytics.includes("trackFriendLinkCopied"), "copying the friend link should be tracked");

console.log("post purchase actions tests passed");
```

- [x] **Step 2: Run the test to verify it fails**

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && npx tsx tests/test_post_purchase_actions.ts
```

Expected: FAIL — the component file does not exist.

- [x] **Step 3: Widen the analytics contract**

In `lib/analytics.ts`, replace `trackShare` and add two events beside it:

```typescript
/** Platforms we can actually observe. "native" is the OS share sheet. */
export function trackShare(platform: "native" | "copy" | "fb_caption", jobId?: string): void {
  safeGtag("share", { platform, ...(jobId && { job_id: jobId }) });
}

/** She copied the /friend link to say or paste somewhere we cannot see. */
export function trackFriendLinkCopied(jobId?: string): void {
  safeGtag("friend_link_copied", { ...(jobId && { job_id: jobId }) });
}

/** She copied the suggested profile-photo caption. */
export function trackCaptionCopied(jobId?: string): void {
  safeGtag("fb_caption_copied", { ...(jobId && { job_id: jobId }) });
}
```

- [x] **Step 4: Write the component**

Create `app/results/[jobId]/components/PostPurchaseActions.tsx`. It takes over the whole `{paid && ...}` card, so it needs the props the old inline markup used: `jobId`, `variant`, `nouns`, `locale`, and the unlocked image indexes to share.

```tsx
"use client";

import Link from "next/link";
import { useState } from "react";

import { trackCaptionCopied, trackFriendLinkCopied, trackGenerateMoreClick, trackShare } from "@/lib/analytics";
import { msg } from "@/lib/i18n";
import type { LandingVariant } from "@/lib/landing-variants";

const FRIEND_LINK = "headshot-generators.com/friend";
const MAX_SHARED_FILES = 4;

type PostPurchaseActionsProps = {
  appendVariantParam: (path: string, variant: LandingVariant) => string;
  jobId: string;
  locale: string;
  nouns: string;
  /** Indexes the customer has paid for; only these can be shared. */
  unlockedIndexes: number[];
  variant: LandingVariant;
};

export function PostPurchaseActions({
  appendVariantParam,
  jobId,
  locale,
  nouns,
  unlockedIndexes,
  variant,
}: PostPurchaseActionsProps) {
  const [shareState, setShareState] = useState<"idle" | "preparing" | "unsupported">("idle");
  const [copied, setCopied] = useState<"none" | "link" | "caption">("none");

  const caption = `Finally updated my photo. No photographer, no studio.`;

  const copy = async (text: string, which: "link" | "caption") => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(which);
      setTimeout(() => setCopied("none"), 2000);
    } catch {
      // Clipboard can be blocked; the text is on screen to select by hand.
    }
  };

  // Share the real files rather than a link to a page: this cohort shares in
  // chat, and a file needs no hosted artefact carrying her face.
  const shareFiles = async () => {
    setShareState("preparing");
    try {
      const indexes = unlockedIndexes.slice(0, MAX_SHARED_FILES);
      const files = await Promise.all(
        indexes.map(async (index) => {
          const response = await fetch(`/api/jobs/${jobId}/result/${index}?download=1`);
          if (!response.ok) throw new Error(`fetch failed: ${response.status}`);
          const blob = await response.blob();
          return new File([blob], `headshot-${index + 1}.png`, { type: blob.type || "image/png" });
        }),
      );
      if (!navigator.canShare?.({ files })) {
        setShareState("unsupported");
        return;
      }
      await navigator.share({ files });
      trackShare("native", jobId);
      setShareState("idle");
    } catch {
      // A cancelled share sheet throws too, so this is not an error state.
      setShareState("idle");
    }
  };

  const canShareFiles = typeof navigator !== "undefined" && typeof navigator.canShare === "function";

  return (
    <div className="mt-12 space-y-6">
      <div className="rounded-2xl border border-neutral-200 bg-white p-6 sm:p-8">
        <h2 className="text-lg font-semibold text-neutral-900">Love your new {nouns}?</h2>
        <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <Link
            href={variant === "pet" ? "/upload?subject=pet" : appendVariantParam(`/customize/${jobId}`, variant)}
            className="flex items-center justify-center gap-2 rounded-xl bg-neutral-900 px-4 py-3 text-sm font-medium text-white transition-all hover:bg-neutral-800"
          >
            {msg(locale, "customizeAgain")}
          </Link>
          {canShareFiles && (
            <button
              type="button"
              onClick={shareFiles}
              disabled={shareState === "preparing" || unlockedIndexes.length === 0}
              className="flex items-center justify-center gap-2 rounded-xl border border-neutral-200 px-4 py-3 text-sm font-medium text-neutral-700 transition-all hover:bg-neutral-50 disabled:opacity-60"
            >
              {shareState === "preparing" ? "Preparing…" : `Send my ${nouns}`}
            </button>
          )}
          <Link
            href={appendVariantParam("/upload", variant)}
            onClick={() => trackGenerateMoreClick(jobId)}
            className="flex items-center justify-center gap-2 rounded-xl border border-neutral-200 px-4 py-3 text-sm font-medium text-neutral-700 transition-all hover:bg-neutral-50"
          >
            Generate more styles
          </Link>
        </div>
        {shareState === "unsupported" && (
          <p className="mt-3 text-sm text-neutral-500">
            This browser can&apos;t share files directly. Download them first, then send from your photos.
          </p>
        )}
      </div>

      <div className="rounded-2xl border border-neutral-200 bg-white p-6 sm:p-8">
        <h3 className="text-base font-semibold text-neutral-900">When someone asks where you got it</h3>
        <p className="mt-2 text-sm text-neutral-600">
          Send them here. Nothing in it for us to track beyond the visit, and nothing they have to enter.
        </p>
        <div className="mt-3 flex flex-col gap-2 sm:flex-row sm:items-center">
          <code className="flex-1 overflow-x-auto whitespace-nowrap rounded-lg bg-neutral-100 px-4 py-3 font-mono text-sm text-neutral-800">
            {FRIEND_LINK}
          </code>
          <button
            type="button"
            onClick={() => {
              void copy(`https://${FRIEND_LINK}`, "link");
              trackFriendLinkCopied(jobId);
            }}
            className="rounded-xl border border-neutral-200 px-4 py-3 text-sm font-medium text-neutral-700 transition-all hover:bg-neutral-50"
          >
            {copied === "link" ? "Copied" : "Copy link"}
          </button>
        </div>
        <p className="mt-4 text-sm text-neutral-600">Setting it as your profile photo? Here&apos;s a caption.</p>
        <div className="mt-2 flex flex-col gap-2 sm:flex-row sm:items-center">
          <p className="flex-1 rounded-lg bg-neutral-100 px-4 py-3 text-sm text-neutral-800">{caption}</p>
          <button
            type="button"
            onClick={() => {
              void copy(caption, "caption");
              trackCaptionCopied(jobId);
            }}
            className="rounded-xl border border-neutral-200 px-4 py-3 text-sm font-medium text-neutral-700 transition-all hover:bg-neutral-50"
          >
            {copied === "caption" ? "Copied" : "Copy caption"}
          </button>
        </div>
      </div>
    </div>
  );
}
```

The caption carries no link and no brand mark by default. That is deliberate: the buyer paid for a photo that passes as real, and forcing an AI disclosure into her profile post is the objection that killed the poll designs.

- [x] **Step 5: Render it from the results page**

In `ResultsPageClient.tsx`, replace the whole block from `{/* Post-purchase: sharing, upsell, review */}`'s opening `<div className="mt-12 space-y-6">` through the closing `</div>` of the four-cell grid card with:

```tsx
            <PostPurchaseActions
              appendVariantParam={appendVariantParam}
              jobId={jobId}
              locale={locale}
              nouns={nouns}
              unlockedIndexes={
                job?.unlockedIndexes ?? resultStyles.map((_, index) => index)
              }
              variant={variant}
            />
```

Keep the review-prompt card that follows it. Add the import, and remove `trackShare` from the results page's analytics import if nothing else there uses it:

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && grep -n "trackShare" "app/results/[jobId]/ResultsPageClient.tsx"
```

Confirm `msg` versus `t` naming in that file before assuming, and confirm the local name of the variant-appending helper:

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && grep -n "appendVariantParam\|const msg\|msg as\|from \"@/lib/i18n\"" "app/results/[jobId]/ResultsPageClient.tsx" | head -6
```

- [x] **Step 6: Run the test, typecheck, build**

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && npx tsx tests/test_post_purchase_actions.ts && npm run typecheck && npm run build
```

Expected: test PASS, no type errors, build succeeds.

- [x] **Step 7: Commit**

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && git add "app/results/[jobId]/components/PostPurchaseActions.tsx" "app/results/[jobId]/ResultsPageClient.tsx" lib/analytics.ts tests/test_post_purchase_actions.ts && git commit -m "Replace homepage share buttons with a private file share and spoken answer"
```

---

### Task 5: The share-nudge email

Research puts the median time to a referral at around 14 days, so day 10 is the earliest point worth asking. It goes only to paying customers who actually downloaded.

**Files:**
- Modify: `lib/email.ts`
- Test: `tests/test_share_nudge_email.ts`

- [x] **Step 1: Write the failing test**

Create `tests/test_share_nudge_email.ts`:

```typescript
import * as assert from "assert";
import { buildShareNudgeEmail } from "../lib/email";
import type { Job } from "../lib/types";

const job = {
  id: "job-1",
  status: "completed",
  paid: true,
  paidAmountCents: 2900,
  customerEmail: "buyer@example.com",
  variant: "women",
  createdAt: 1,
} as unknown as Job;

const { subject, html } = buildShareNudgeEmail(job);

// Paid customers must never see unlock or coupon copy: getting this wrong
// produced a chargeback dispute before (see the drip cron's comments).
for (const forbidden of ["unlock", "15% off", "COMEBACK15", "checkout", "Still thinking"]) {
  assert.ok(!html.includes(forbidden), `share nudge must not contain ${forbidden}`);
  assert.ok(!subject.includes(forbidden), `subject must not contain ${forbidden}`);
}

// It points at the durable friend link, tagged so the click is attributable.
assert.ok(html.includes("/friend?via=nudge"), "must link to the tagged friend link");
// And it is honest that there is no reward attached.
assert.ok(/nothing in it for/i.test(html), "must state there is no incentive");
// Unsubscribe is present and untagged.
assert.ok(html.includes("/unsubscribe"), "must offer unsubscribe");
assert.ok(!html.includes("/unsubscribe?via="), "unsubscribe must not be via-tagged");

console.log("share nudge email tests passed");
```

- [x] **Step 2: Run the test to verify it fails**

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && npx tsx tests/test_share_nudge_email.ts
```

Expected: FAIL — `buildShareNudgeEmail` is not exported.

- [x] **Step 3: Write the builder and sender**

In `lib/email.ts`, add after `buildPaidResultsReminderEmail`:

```typescript
/** Render-only build of the day-10 share nudge — no network, so tests can
 *  assert on the HTML without Resend configured. Paid customers only. */
export function buildShareNudgeEmail(job: Job): {
  subject: string;
  html: string;
  ctaUrl: string;
} {
  const friendUrl = withEmailVia(`${APP_URL}/friend`, "nudge");
  const unsubUrl = `${APP_URL}/api/jobs/${job.id}/unsubscribe`;
  const isWomen = job.variant === "women";
  const nouns = job.subjectKind === "pet" ? "pet portraits" : isWomen ? "portraits" : "headshots";
  const ctaColor = isWomen ? "#8b6b7a" : "#1c1917";

  const subject = `Know someone who needs ${nouns}?`;
  const html = renderBrandedEmail({
    preheader: `If someone asked where you got your ${nouns}, here's the link to send them.`,
    eyebrow: "A small favour",
    heading: `Know someone who<br/>needs new ${nouns}?`,
    intro:
      `Hope you're getting good use out of your ${nouns}. If anyone has asked where you got them, ` +
      `this is the link to send: it shows them a free preview of their own before they pay anything.`,
    ctaText: "Send a friend the link",
    ctaUrl: friendUrl,
    ctaColor,
    outro:
      "There's nothing in it for you and nothing in it for us beyond the visit — no code to enter, " +
      "no reward to claim. Just the easiest answer when someone asks.",
    unsubUrl,
  });
  return { subject, html, ctaUrl: friendUrl };
}

export async function sendShareNudgeEmail(job: Job): Promise<void> {
  if (!resend || !job.customerEmail) return;
  const { subject, html } = buildShareNudgeEmail(job);
  try {
    const { error } = await resend.emails.send(withBcc({
      from: FROM_EMAIL,
      to: job.customerEmail,
      subject,
      html,
    }));
    if (error) {
      console.error("[email] sendShareNudgeEmail error:", error);
      await enqueueRenderedEmail({
        to: job.customerEmail,
        from: FROM_EMAIL,
        subject,
        html,
        label: "sendShareNudgeEmail",
        cause: error,
      });
    }
  } catch (e) {
    console.error("[email] sendShareNudgeEmail exception:", e);
    await enqueueRenderedEmail({
      to: job.customerEmail,
      from: FROM_EMAIL,
      subject,
      html,
      label: "sendShareNudgeEmail",
      cause: e,
    });
  }
}
```

Add the import at the top of `lib/email.ts`:

```typescript
import { withEmailVia } from "./email-links";
```

Check the exact shape of `enqueueRenderedEmail`'s argument against a neighbouring caller before relying on it, and match `withBcc` usage:

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && grep -n "function enqueueRenderedEmail" -A 12 lib/email.ts
```

- [x] **Step 4: Tag the other outbound links**

Apply `withEmailVia(..., "nudge")` to the results CTA in `buildPaidResultsReminderEmail` and `buildDripReminderEmail` so email clicks stop being logged as webmail referrals. Leave every `unsubUrl` untagged — `withEmailVia` already refuses those, but do not rely on that alone.

- [x] **Step 5: Run the tests and typecheck**

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && npx tsx tests/test_share_nudge_email.ts && npx tsx tests/test_email_functions.ts && npm run typecheck
```

Expected: PASS, and the existing email tests still pass.

- [x] **Step 6: Commit**

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && git add lib/email.ts tests/test_share_nudge_email.ts && git commit -m "Add the day-10 share nudge email"
```

---

### Task 6: Day-10 cron branch and the one-time blast

**Files:**
- Modify: `app/api/cron/drip-reminder/route.ts`
- Create: `app/api/admin/send-friend-blast/route.ts`
- Test: `tests/test_share_nudge_email.ts` (extend)

- [x] **Step 1: Extend the test with the eligibility rules**

Append to `tests/test_share_nudge_email.ts`, before its `console.log`:

```typescript
import { readFileSync } from "fs";

const cron = readFileSync("app/api/cron/drip-reminder/route.ts", "utf8");

// The nudge rides the existing single fetch: a second full scan every 2 hours
// is not acceptable on a project Supabase suspended for egress (2026-06-25).
assert.strictEqual(
  (cron.match(/listRecentJobs\(/g) ?? []).length,
  1,
  "the cron must fetch jobs exactly once",
);
// It needs a 14-day window to see 10-day-old jobs.
assert.ok(/listRecentJobs\(14\)/.test(cron), "window must cover 10-day-old jobs");
assert.ok(cron.includes("sendShareNudgeEmail"), "cron should send the share nudge");
// Real buyers only: $0 coupon and feedback unlocks are genuine paid rows.
assert.ok(
  /paidAmountCents\s*\?\?\s*0\)\s*>\s*0|paidAmountCents\s*>\s*0/.test(cron),
  "the nudge must require real money",
);
// Only people who actually downloaded, and never twice.
assert.ok(cron.includes("downloadLearning"), "the nudge should require a download");
assert.ok(cron.includes("shareNudgeSentAt"), "the nudge must be idempotent");

const blast = readFileSync("app/api/admin/send-friend-blast/route.ts", "utf8");
assert.ok(blast.includes("isAdminAuthorized"), "the blast must be admin-protected");
assert.ok(blast.includes("dryRun"), "the blast must support a dry run");
assert.ok(/paidAmountCents/.test(blast), "the blast must target real buyers");
assert.ok(blast.includes("emailOptOut"), "the blast must honour opt-outs");
```

- [x] **Step 2: Add the job field**

In `lib/types.ts`, beside `feedbackRequestSentAt`, add:

```typescript
  /** Timestamp (ms) when the day-10 share nudge was sent. */
  shareNudgeSentAt?: number;
```

Add `"shareNudgeSentAt"` to the `updateJob` field allowlist in `lib/store.ts` — find it near the existing `"feedbackRequestSentAt"` entry:

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && grep -n '"feedbackRequestSentAt"' lib/store.ts
```

Without the allowlist entry the write is silently dropped and the nudge would resend every 2 hours.

- [x] **Step 3: Add the cron branch**

In `app/api/cron/drip-reminder/route.ts`, widen the fetch:

```typescript
  const allJobs = await listRecentJobs(14); // 7d for reminders, 14d for the day-10 share nudge
```

Then add a third loop after the abandoned-cart loop, before the response is returned:

```typescript
  // ── Day-10 share nudge: paying customers who downloaded ──
  // Research puts the median time to a referral near 14 days, so day 10 is the
  // earliest point worth asking. Paid-safe copy only: no unlock, no coupon.
  const SHARE_NUDGE_DELAY_MS = 10 * 24 * 60 * 60 * 1000;
  let nudgeSent = 0;
  let nudgeSkipped = 0;
  let nudgeErrors = 0;

  for (const job of allJobs) {
    const downloaded = (job.downloadLearning?.events.length ?? 0) > 0;
    if (
      !job.paid ||
      (job.paidAmountCents ?? 0) <= 0 ||
      !job.customerEmail ||
      job.emailOptOut === true ||
      job.refunded === true ||
      job.shareNudgeSentAt != null ||
      job.completedAt == null ||
      !downloaded ||
      now - job.completedAt < SHARE_NUDGE_DELAY_MS
    ) {
      nudgeSkipped++;
      continue;
    }
    try {
      await sendShareNudgeEmail(job);
      await updateJob(job.id, { shareNudgeSentAt: now });
      auditLog("share_nudge.sent", { jobId: job.id });
      nudgeSent++;
    } catch (err) {
      auditLog("share_nudge.error", {
        jobId: job.id,
        error: err instanceof Error ? err.message : String(err),
      });
      nudgeErrors++;
    }
  }
```

Add `sendShareNudgeEmail` to the `@/lib/email` import, and include `nudgeSent`, `nudgeSkipped` and `nudgeErrors` in the JSON the route returns — find its return statement and match the existing key style:

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && grep -n "return NextResponse.json" app/api/cron/drip-reminder/route.ts
```

- [x] **Step 4: Write the blast route**

Create `app/api/admin/send-friend-blast/route.ts`, following the `send-feedback-request` pattern exactly (admin auth, `dryRun`, `limit`, `onlyEmail`, `sinceDays`, audit logging). It targets buyers with `paidAmountCents > 0`, not opted out, not refunded, without `shareNudgeSentAt`, and sets `shareNudgeSentAt` on send so the cron does not then send the same person the same email.

```typescript
import { NextResponse } from "next/server";
import { isAdminAuthorized } from "@/lib/api-auth";
import { listRecentJobs, updateJob } from "@/lib/store";
import { sendShareNudgeEmail } from "@/lib/email";
import { auditLog } from "@/lib/logger";

/** One-time "send a friend the link" blast to existing buyers.
 *
 * This is the falsification test for the whole gift/referral thesis: if real
 * customers will not click a no-incentive link, the gift seat is not worth
 * building. Gate: >= 5 /friend clicks or >= 1 recipient upload in 14 days.
 *
 * Body (JSON, optional):
 *   { sinceDays?: number, dryRun?: boolean, limit?: number, onlyEmail?: string }
 */
export async function POST(request: Request) {
  if (!isAdminAuthorized(request, { allowCron: "always" })) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const body = await request.json().catch(() => ({}));
  const sinceDays = Math.max(1, Math.min(365, Number(body.sinceDays) || 90));
  const dryRun = body.dryRun === true;
  const limit = Math.max(1, Math.min(500, Number(body.limit) || 200));
  const onlyEmail =
    typeof body.onlyEmail === "string" && body.onlyEmail.includes("@")
      ? body.onlyEmail.trim().toLowerCase()
      : null;

  auditLog("admin.send_friend_blast.started", { sinceDays, dryRun, limit, onlyEmail });

  const jobs = await listRecentJobs(sinceDays);
  const seenEmails = new Set<string>();
  const targets: typeof jobs = [];

  for (const job of jobs) {
    const email = job.customerEmail?.trim().toLowerCase();
    if (
      !job.paid ||
      (job.paidAmountCents ?? 0) <= 0 ||
      !email ||
      job.emailOptOut === true ||
      job.refunded === true ||
      job.shareNudgeSentAt != null
    ) {
      continue;
    }
    if (onlyEmail && email !== onlyEmail) continue;
    // One send per person, not per job: repeat buyers have several rows.
    if (seenEmails.has(email)) continue;
    seenEmails.add(email);
    targets.push(job);
    if (targets.length >= limit) break;
  }

  if (dryRun) {
    auditLog("admin.send_friend_blast.dry_run", { targets: targets.length });
    return NextResponse.json({
      dryRun: true,
      targets: targets.length,
      emails: targets.map((job) => job.customerEmail),
    });
  }

  let sent = 0;
  let errors = 0;
  for (const job of targets) {
    try {
      await sendShareNudgeEmail(job);
      await updateJob(job.id, { shareNudgeSentAt: Date.now() });
      sent++;
    } catch (err) {
      auditLog("admin.send_friend_blast.error", {
        jobId: job.id,
        error: err instanceof Error ? err.message : String(err),
      });
      errors++;
    }
  }

  auditLog("admin.send_friend_blast.done", { sent, errors, targets: targets.length });
  return NextResponse.json({ sent, errors, targets: targets.length });
}
```

- [x] **Step 5: Run the tests, typecheck, build**

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && npx tsx tests/test_share_nudge_email.ts && npx tsx tests/test_drip_reminder_cron.ts && npm run typecheck && npm run build
```

Expected: all PASS, no type errors, build succeeds. If `test_drip_reminder_cron.ts` asserts a jobs-window number, update it to 14 and note why in the commit.

- [x] **Step 6: Commit**

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && git add app/api/cron/drip-reminder/route.ts app/api/admin/send-friend-blast/route.ts lib/types.ts lib/store.ts tests/test_share_nudge_email.ts && git commit -m "Send the share nudge at day 10 and add the one-time friend blast"
```

---

### Task 7: Full suite, PR, deploy, prod walk

- [x] **Step 1: Run everything**

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && npm run check
```

Expected: fully green. The suite was green on `origin/main` at `de0f060`, so any failure here is yours.

- [x] **Step 2: Open the PR**

Title: `Post-purchase share, heard-from question, day-10 nudge (Phase 1b)`. The body should state the measured baseline (1 `share` event from ~45 buyers in 30 days), what replaced the dead buttons and why nothing carries a customer's face, the blast gate with its probabilities, and that no pre-purchase surface changed.

- [x] **Step 3: Wait for CI, then merge**

Read the bound PR's status rather than polling. If Vercel reports "Deployment was blocked", the commit author is wrong — see the note in the header.

- [ ] **Step 4: Prod walk**

```bash
S=https://www.headshot-generators.com
curl -s -o /dev/null -w "/friend -> %{http_code} -> %{redirect_url}\n" "$S/friend"
```

Then, on a real paid results page in a mobile browser: confirm the X and LinkedIn buttons are gone, that "Send my headshots" opens the OS share sheet with the actual image files attached, that the copy-link and copy-caption buttons work, and that the download prompt now shows a third step which can be skipped. On desktop Chrome confirm the share button is either absent or shows the fallback text rather than erroring.

Then dry-run the blast before sending anything real:

```bash
curl -s -X POST "$S/api/admin/send-friend-blast" \
  -H "x-admin-key: $ADMIN_API_KEY" -H "Content-Type: application/json" \
  -d '{"dryRun":true}' | head -c 400
```

Expected: a target count in the low hundreds and a list of real buyer addresses. **Do not send the live blast without the founder's explicit go-ahead** — it is outbound mail to every recent customer, and it is theirs to approve.

- [ ] **Step 5: Report**

State what passed with real output, what the dry run counted, and that the live blast awaits approval.

---

## Self-review

**Spec coverage.** M4 is Task 4, minus the hosted share page the refuters killed. M5 is Tasks 2 and 3. M8 is Tasks 5 and 6. The `?via=` tagging in Task 1 is not in the spec; it closes an artefact the Phase 1a panel exposed in production, and without it email-driven orders are miscounted as webmail referrals. Deliberately excluded: the download-triggered Pro-to-Signature upgrade email, which is an AOV lever rather than a contagion one and belongs with the pricing work now that PR #29 has shipped the one-click upsell.

**Placeholders.** None. Every code step carries its code. Where a line or a local name could have drifted, the step opens with a `grep` to find the real one instead of asserting a number.

**Type consistency.** `DownloadHeardFrom` is derived from `DOWNLOAD_HEARD_FROM_OPTIONS` and is optional in `DownloadLearning`, in `DownloadResponseInput`, in the component's `onSubmit` and in the API body, so stored two-answer responses stay valid. `withEmailVia` takes the `ViaLabel` union from `lib/partner-attribution.ts`, the same source the rail validates against, so an email cannot emit a label the rail would drop. `trackShare`'s union becomes `"native" | "copy" | "fb_caption"` and every former caller is inside the replaced block. `shareNudgeSentAt` is added to the `Job` type **and** the `updateJob` allowlist; omitting the second would silently resend the email every two hours.

**Risk worth naming.** `navigator.canShare({ files })` is false on desktop and in some in-app browsers, and this cohort arrives largely through the Facebook in-app browser. The share button is hidden rather than broken there, so the measured share rate will understate desktop intent — the copy-link path is the fallback and is tracked separately, which is why `trackFriendLinkCopied` exists as its own event.
