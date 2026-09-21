# Phase 1 — Attribution Rail Implementation Plan

> **SHIPPED 2026-09-22.** All 7 code tasks merged as [PR #42](https://github.com/ruzbeh/headshot-studio/pull/42) (merge `34d4c9c`). Full suite green including the build.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make a non-paid order identifiable end to end, so a partner, friend link or gift can be credited with real money from Stripe rather than guessed at.

**Architecture:** `?partner=CODE` and `?via=LABEL` become recognised acquisition touches. Partner credit is kept in its own 60-day first-touch cookie (`hs_partner`) because the existing `hs_acq` cookie is last-touch and is deliberately overwritten by any external referrer, so a partner-referred visitor who comes back through a Facebook ad would otherwise lose the credit. Both are merged into `job.acquisition` at job creation, spread into Stripe session metadata and mirrored into `payment_intent_data.metadata` so refund events carry them too. A `/stats` panel then counts real-money orders by source and partner.

**Tech Stack:** Next.js 15 App Router, TypeScript, Supabase (jsonb `jobs`), Stripe, standalone `tsx` test scripts under `tests/` run by `scripts/run-tests.mjs`.

**Repo:** `/Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio`. Line references are against `origin/main` at `b1ed9cf` (which includes the Phase 0 merge). **Before starting, run `git fetch origin main && git checkout -b feat/attribution-rail origin/main`.** The local checkout drifts far behind and misrepresents this code.

**Spec:** `docs/superpowers/specs/2026-09-21-contagious-acquisition-design.md` §4 M1 and §8 (in the Agentic Company repo).

---

## Scope

This plan is Phase 1a: the measurement spine only. It ships no customer-visible surface except the `/friend` redirect, touches nothing pre-purchase, and needs no database migration.

Deliberately **not** here, each its own later plan:
- The partner programme itself (`partners` table, `/partners` page, the server-applied client discount, payouts) — Phase 2a, and it depends on this rail existing.
- The post-purchase share surface, the "how did you hear about us?" question and the day-10 nudge — Phase 1b.
- The gift seat — Phase 2b, gated on the friend-blast result.

**Concurrency note:** another session is fixing `tests/test_lp_hero_rewrite.py`. Do not touch that file, the homepage copy, or any landing component. If `npm test` shows exactly those 7 failures, they are pre-existing and not yours; see Task 8.

---

## Background an engineer needs before touching anything

`lib/acquisition.ts` is a deliberately privacy-conservative module. It keeps campaign **labels** and the landing path, and never persists click IDs, full referrer URLs or IPs — `tests/test_acquisition.ts` asserts that `fbclid` is used to infer `source=facebook` but is never stored, and `tests/test_checkout_attribution_metadata.ts` asserts no route ever writes `acquisition_fbclid`/`acquisition_gclid` into Stripe. Keep both properties: the new fields are labels only.

Three behaviours matter for this work:

- **`hasExplicitAcquisitionTouch(searchParams)`** lists the params that count as a new touch (`utm_*`, `fbclid`, `gclid`, `msclkid`). `proxy.ts` rewrites `hs_acq` when there is no cookie, when this returns true, **or when the referrer is external** (`proxy.ts:43`). That last clause is why partner credit cannot live in `hs_acq`.
- **`isAcquisitionPrefetch(headers)`** stops Next.js prefetches creating a touch. Any new cookie must respect it, or a prefetched CTA can attribute a visit before the visitor clicks.
- **`serializeAcquisitionContext`/`parseAcquisitionContext`** use short keys (`s`, `m`, `l`, `d`, `at`, `c`, `co`, `t`, `r`) in a `URLSearchParams` string. A new field needs a key in both, and `parseAcquisitionContext` returns `undefined` unless `source`, `medium`, `landingPath` and a positive `capturedAt` all survive.

On the Stripe side, all six checkout routes build a `metadata` object and spread `acquisition_source/medium/campaign/landing/device`. Two gaps: `content` is captured in the cookie but never reaches Stripe, and `metadata` is only on the session, so a `charge.refunded` webhook has no way back to the attribution. Every route already passes `payment_intent_data: { statement_descriptor: "HEADSHOTGEN" }`, so adding `metadata` there is a one-line change per route.

`$0` unlocks are real rows in Stripe and in the jobs table: coupon redemptions and the feedback unlock both call `setJobPaid` with `paidAmountCents: 0`. Every count in the new panel must require real money, or the first partner payout will be computed off free unlocks.

---

## File structure

| File | Responsibility | Change |
|---|---|---|
| `lib/partner-attribution.ts` | Partner/via code shape: validation, normalisation, cookie name, TTL | **Create** |
| `lib/acquisition.ts` | Acquisition context: add `partner`, recognise `partner`/`via`, map `via` to a source | Modify |
| `proxy.ts` | Set the first-touch `hs_partner` cookie | Modify |
| `app/api/jobs/route.ts` | Merge the partner cookie into `job.acquisition` at creation | Modify |
| `app/friend/route.ts` | Durable spoken-answer link, redirects to `/?via=friend` | **Create** |
| `app/api/checkout/route.ts` and the 5 sibling checkout routes | Add `acquisition_partner`/`acquisition_content`, mirror metadata to the payment intent | Modify |
| `app/api/admin/stats/route.ts` | Aggregate real-money orders by source/medium/partner | Modify |
| `app/stats/StatsClient.tsx` | Render the acquisition panel | Modify |
| `tests/test_partner_attribution.ts` | Code-shape validation | **Create** |
| `tests/test_acquisition.ts` | Partner/via capture and round-trip | Modify |
| `tests/test_attribution_rail_wiring.ts` | Proxy + job-creation + `/friend` wiring | **Create** |
| `tests/test_checkout_attribution_metadata.ts` | New keys present in all six routes, mirrored to the intent | Modify |
| `tests/test_stats_acquisition_panel.ts` | Aggregation excludes `$0` and non-paid | **Create** |

---

### Task 1: Partner code shape

A partner or `via` label arrives from a URL typed by a human into a blog post or an email, so it must be normalised and bounded before it is stored or shown. Validation against a real `partners` table comes in Phase 2a; here the code is a label.

**Files:**
- Create: `lib/partner-attribution.ts`
- Test: `tests/test_partner_attribution.ts`

- [x] **Step 1: Write the failing test**

Create `tests/test_partner_attribution.ts`:

```typescript
import * as assert from "assert";
import {
  PARTNER_COOKIE,
  PARTNER_COOKIE_MAX_AGE_SECONDS,
  VIA_LABELS,
  isKnownViaLabel,
  normalizePartnerCode,
} from "../lib/partner-attribution";

assert.strictEqual(PARTNER_COOKIE, "hs_partner");
// 60 days: longer than the 30-day hs_acq window, matching the 60-day
// first-touch cookie the partner terms promise.
assert.strictEqual(PARTNER_COOKIE_MAX_AGE_SECONDS, 60 * 60 * 24 * 60);

// Normalisation: case-folded, trimmed, bounded.
assert.strictEqual(normalizePartnerCode("  CoachJane "), "coachjane");
assert.strictEqual(normalizePartnerCode("coach-jane_2"), "coach-jane_2");
assert.strictEqual(normalizePartnerCode("a".repeat(80)), "a".repeat(40));

// Rejected: empty, and anything outside [a-z0-9_-] so the label is safe to
// put in a cookie, in Stripe metadata and on a page without escaping.
for (const bad of ["", "   ", "coach jane", "coach.jane", "coach/jane", "coach:jane", "<script>", "café"]) {
  assert.strictEqual(normalizePartnerCode(bad), undefined, `should reject ${JSON.stringify(bad)}`);
}
assert.strictEqual(normalizePartnerCode(null), undefined);
assert.strictEqual(normalizePartnerCode(undefined), undefined);

// `via` is a closed set we author ourselves, unlike partner codes.
assert.deepStrictEqual([...VIA_LABELS], ["friend", "gift", "nudge", "blast", "analyzer"]);
assert.strictEqual(isKnownViaLabel("friend"), true);
assert.strictEqual(isKnownViaLabel("FRIEND"), true);
assert.strictEqual(isKnownViaLabel("unknown-label"), false);
assert.strictEqual(isKnownViaLabel(null), false);

console.log("partner attribution code shape tests passed");
```

- [x] **Step 2: Run the test to verify it fails**

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && npx tsx tests/test_partner_attribution.ts
```

Expected: FAIL with `Cannot find module '../lib/partner-attribution'`.

- [x] **Step 3: Write the implementation**

Create `lib/partner-attribution.ts`:

```typescript
/**
 * Partner and referral labels arrive in URLs that humans paste into blog
 * posts, emails and group comments, so they are normalised and bounded before
 * they reach a cookie, Stripe metadata or a page. Codes are validated against
 * the partners table in Phase 2a; here they are labels only.
 */

export const PARTNER_COOKIE = "hs_partner";

/**
 * 60 days, deliberately longer than the 30-day hs_acq window: partner terms
 * promise a 60-day first-touch attribution, and hs_acq is last-touch and gets
 * replaced by any external referrer.
 */
export const PARTNER_COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 60;

const MAX_PARTNER_CODE_LENGTH = 40;
const PARTNER_CODE_PATTERN = /^[a-z0-9_-]+$/;

/** Labels we author ourselves, unlike partner codes which are arbitrary. */
export const VIA_LABELS = ["friend", "gift", "nudge", "blast", "analyzer"] as const;

export type ViaLabel = (typeof VIA_LABELS)[number];

export function normalizePartnerCode(raw: string | null | undefined): string | undefined {
  if (!raw) return undefined;
  const candidate = raw.trim().toLowerCase().slice(0, MAX_PARTNER_CODE_LENGTH);
  if (!candidate || !PARTNER_CODE_PATTERN.test(candidate)) return undefined;
  return candidate;
}

export function isKnownViaLabel(raw: string | null | undefined): boolean {
  if (!raw) return false;
  return (VIA_LABELS as readonly string[]).includes(raw.trim().toLowerCase());
}

export function normalizeViaLabel(raw: string | null | undefined): ViaLabel | undefined {
  if (!isKnownViaLabel(raw)) return undefined;
  return raw!.trim().toLowerCase() as ViaLabel;
}
```

- [x] **Step 4: Run the test to verify it passes**

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && npx tsx tests/test_partner_attribution.ts
```

Expected: PASS, printing `partner attribution code shape tests passed`.

- [x] **Step 5: Commit**

Commit plainly. Do **not** pass `-c user.name`/`-c user.email`: this repo's local git config is `ruzbeh <ruzbeh.001234@gmail.com>` and is authorised on Vercel, while an override makes Vercel reject the deployment with "Deployment was blocked".

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && git add lib/partner-attribution.ts tests/test_partner_attribution.ts && git commit -m "Add partner and via label normalisation"
```

---

### Task 2: Teach the acquisition context about partner and via

**Files:**
- Modify: `lib/acquisition.ts`
- Test: `tests/test_acquisition.ts`

- [x] **Step 1: Write the failing test**

Append to the end of `tests/test_acquisition.ts`, immediately before its final `console.log` line:

```typescript
// --- partner and via capture -------------------------------------------------

// `?partner=` is an explicit touch, so it replaces a stale last-touch cookie.
assert.strictEqual(hasExplicitAcquisitionTouch(new URLSearchParams({ partner: "coachjane" })), true);
assert.strictEqual(hasExplicitAcquisitionTouch(new URLSearchParams({ via: "friend" })), true);
assert.strictEqual(hasExplicitAcquisitionTouch(new URLSearchParams({ partner: "coach jane" })), false);
assert.strictEqual(hasExplicitAcquisitionTouch(new URLSearchParams({ via: "not-a-label" })), false);

const partnerContext = buildAcquisitionContext({
  searchParams: new URLSearchParams({ partner: "CoachJane" }),
  landingPath: "/for/real-estate",
  currentHost: "www.headshot-generators.com",
  userAgent: "Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) Mobile/15E148",
  capturedAt,
});
assert.strictEqual(partnerContext.partner, "coachjane");
assert.strictEqual(partnerContext.source, "partner");
assert.strictEqual(partnerContext.medium, "referral");

// A `via` link is a friend/gift/nudge touch, not a partner one.
const viaContext = buildAcquisitionContext({
  searchParams: new URLSearchParams({ via: "friend" }),
  landingPath: "/",
  capturedAt,
});
assert.strictEqual(viaContext.source, "friend");
assert.strictEqual(viaContext.medium, "referral");
assert.strictEqual(viaContext.partner, undefined);
assert.strictEqual(viaContext.content, "friend");

// An explicit utm_source still wins over the inferred partner source, so an
// existing tagged campaign is never relabelled.
const taggedPartner = buildAcquisitionContext({
  searchParams: new URLSearchParams({ partner: "coachjane", utm_source: "facebook", utm_medium: "paid_social" }),
  landingPath: "/",
  capturedAt,
});
assert.strictEqual(taggedPartner.source, "facebook");
assert.strictEqual(taggedPartner.medium, "paid_social");
assert.strictEqual(taggedPartner.partner, "coachjane");

// An invalid partner code is dropped rather than stored.
assert.strictEqual(
  buildAcquisitionContext({
    searchParams: new URLSearchParams({ partner: "coach jane" }),
    landingPath: "/",
    capturedAt,
  }).partner,
  undefined,
);

// Round-trips through the cookie.
const partnerRoundTrip = parseAcquisitionContext(serializeAcquisitionContext(partnerContext));
assert.strictEqual(partnerRoundTrip?.partner, "coachjane");
assert.strictEqual(partnerRoundTrip?.source, "partner");

// Click IDs are still never persisted, now alongside a partner code.
const partnerWithClickId = buildAcquisitionContext({
  searchParams: new URLSearchParams({ partner: "coachjane", fbclid: "do-not-store-this-click-id" }),
  landingPath: "/",
  capturedAt,
});
assert.ok(!serializeAcquisitionContext(partnerWithClickId).includes("do-not-store-this-click-id"));
```

- [x] **Step 2: Run the test to verify it fails**

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && npx tsx tests/test_acquisition.ts
```

Expected: FAIL on the first new assertion, because `hasExplicitAcquisitionTouch` does not know `partner`.

- [x] **Step 3: Add `partner` to the context type**

In `lib/acquisition.ts`, add the field to `AcquisitionContext`, after `term`:

```typescript
  term?: string;
  /** Partner/affiliate code from `?partner=`. First-touch; see lib/partner-attribution.ts. */
  partner?: string;
```

- [x] **Step 4: Recognise the new params as an explicit touch**

Replace the whole `hasExplicitAcquisitionTouch` function with:

```typescript
export function hasExplicitAcquisitionTouch(searchParams: SearchParamsReader): boolean {
  // A partner code or a known via label is as much a deliberate touch as a
  // utm tag, but only when it is well formed — otherwise a typo in a pasted
  // link would overwrite a real campaign attribution with nothing.
  if (normalizePartnerCode(searchParams.get("partner"))) return true;
  if (isKnownViaLabel(searchParams.get("via"))) return true;
  return [
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_content",
    "utm_term",
    "fbclid",
    "gclid",
    "msclkid",
  ].some((key) => Boolean(searchParams.get(key)));
}
```

Add the import at the top of the file:

```typescript
import { isKnownViaLabel, normalizePartnerCode, normalizeViaLabel } from "./partner-attribution";
```

- [x] **Step 5: Derive source, medium, content and partner in `buildAcquisitionContext`**

In `buildAcquisitionContext`, insert these three lines directly after the existing `const referrerHost = ...` line:

```typescript
  const partner = normalizePartnerCode(options.searchParams.get("partner"));
  const via = normalizeViaLabel(options.searchParams.get("via"));
  const inferredReferral = partner ? { source: "partner", medium: "referral" } : via ? { source: via, medium: "referral" } : undefined;
```

Then change the `source` and `medium` lines so the inferred referral sits between the explicit utm tag and the click-ID inference:

```typescript
  const source =
    cleanLabel(options.searchParams.get("utm_source")) ?? inferredReferral?.source ?? click?.source ?? referrerHost ?? "direct";
  const medium =
    cleanLabel(options.searchParams.get("utm_medium")) ?? inferredReferral?.medium ?? click?.medium ?? (referrerHost ? "referral" : "none");
```

Then, in the returned object, change the `content` entry and add `partner`. Replace:

```typescript
    ...(cleanLabel(options.searchParams.get("utm_content")) && {
      content: cleanLabel(options.searchParams.get("utm_content")),
    }),
```

with:

```typescript
    ...((cleanLabel(options.searchParams.get("utm_content")) ?? via) && {
      content: cleanLabel(options.searchParams.get("utm_content")) ?? via,
    }),
    ...(partner && { partner }),
```

- [x] **Step 6: Carry `partner` through the cookie**

In `serializeAcquisitionContext`, add after the `referrerHost` line:

```typescript
  if (context.partner) params.set("p", context.partner);
```

In `parseAcquisitionContext`, inside the returned object, add after the `referrerHost` entry:

```typescript
      ...(normalizePartnerCode(params.get("p")) && { partner: normalizePartnerCode(params.get("p")) }),
```

- [x] **Step 7: Run the test to verify it passes**

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && npx tsx tests/test_acquisition.ts && npx tsx tests/test_partner_attribution.ts && npm run typecheck
```

Expected: both tests PASS and no type errors. The pre-existing assertions in `test_acquisition.ts` must still pass — in particular the one proving `fbclid` is never serialised.

- [x] **Step 8: Commit**

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && git add lib/acquisition.ts tests/test_acquisition.ts && git commit -m "Capture partner and via labels in the acquisition context"
```

---

### Task 3: First-touch partner cookie in the proxy

`hs_acq` is last-touch and `proxy.ts:43` rewrites it on any external referrer, so a partner-referred visitor who later arrives from a Facebook ad loses the credit. `hs_partner` is written once and left alone while valid.

**Files:**
- Modify: `proxy.ts`
- Test: `tests/test_attribution_rail_wiring.ts`

- [x] **Step 1: Write the failing test**

Create `tests/test_attribution_rail_wiring.ts`:

```typescript
import * as assert from "assert";
import { readFileSync } from "fs";

const proxy = readFileSync("proxy.ts", "utf8");

// The partner cookie is set from the shared constant, never a literal.
assert.ok(proxy.includes("PARTNER_COOKIE"), "proxy should use the PARTNER_COOKIE constant");
assert.ok(
  proxy.includes("PARTNER_COOKIE_MAX_AGE_SECONDS"),
  "proxy should use the shared 60-day TTL, not a hand-written number",
);
assert.ok(proxy.includes("maybeSetPartner"), "proxy should have a maybeSetPartner step");
assert.ok(
  proxy.includes("maybeSetPartner(request,"),
  "maybeSetPartner should be wired into the response chain",
);

// First-touch: the handler must bail out when the cookie already exists.
const partnerFn = proxy.slice(proxy.indexOf("function maybeSetPartner"));
const partnerBody = partnerFn.slice(0, partnerFn.indexOf("\n}\n") + 3);
assert.ok(
  partnerBody.includes("isAcquisitionPrefetch"),
  "a Next.js prefetch must not create a partner touch",
);
assert.ok(
  /if \(request\.cookies\.get\(PARTNER_COOKIE\)/.test(partnerBody),
  "maybeSetPartner must check for an existing cookie (first-touch, never overwritten)",
);
assert.ok(partnerBody.includes("httpOnly: true"), "partner cookie must be httpOnly");
assert.ok(partnerBody.includes("sameSite: \"lax\""), "partner cookie must be sameSite=lax");

// Job creation merges the cookie into the stored acquisition context.
const jobsRoute = readFileSync("app/api/jobs/route.ts", "utf8");
assert.ok(jobsRoute.includes("PARTNER_COOKIE"), "job creation should read the partner cookie");
assert.ok(
  jobsRoute.includes("normalizePartnerCode"),
  "job creation should normalise the cookie value before storing it",
);

// /friend is a durable, brandable link for the spoken answer.
const friendRoute = readFileSync("app/friend/route.ts", "utf8");
assert.ok(friendRoute.includes("via=friend"), "/friend should redirect to ?via=friend");
assert.ok(/redirect/i.test(friendRoute), "/friend should issue a redirect");

console.log("attribution rail wiring tests passed");
```

- [x] **Step 2: Run the test to verify it fails**

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && npx tsx tests/test_attribution_rail_wiring.ts
```

Expected: FAIL on the first assertion, `proxy should use the PARTNER_COOKIE constant`.

- [x] **Step 3: Add the handler to `proxy.ts`**

Insert this function immediately after `maybeSetAcquisition` (which ends just before the `/** Capture ?pw= query param ... */` comment):

```typescript
/**
 * First-touch partner credit. `hs_acq` is last-touch and is deliberately
 * replaced by any external referrer (see maybeSetAcquisition), so a visitor
 * who arrives from a partner's post and later returns through a Facebook ad
 * would lose the partner credit. This cookie is written once and then left
 * alone until it expires, matching the 60-day first-touch attribution the
 * partner terms promise.
 */
function maybeSetPartner(request: NextRequest, response: NextResponse): NextResponse {
  if (isAcquisitionPrefetch(request.headers)) return response;
  if (request.cookies.get(PARTNER_COOKIE)?.value) return response;

  const partner = normalizePartnerCode(request.nextUrl.searchParams.get("partner"));
  if (!partner) return response;

  response.cookies.set(PARTNER_COOKIE, partner, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    maxAge: PARTNER_COOKIE_MAX_AGE_SECONDS,
    path: "/",
  });
  return response;
}
```

Add the import beside the existing `@/lib/acquisition` import:

```typescript
import {
  PARTNER_COOKIE,
  PARTNER_COOKIE_MAX_AGE_SECONDS,
  normalizePartnerCode,
} from "@/lib/partner-attribution";
```

- [x] **Step 4: Wire it into the response chain**

Find the composed call near `proxy.ts:285`:

```typescript
      maybeSetPwExp(request, maybeSetAcquisition(request, maybeSetFlagSeed(request, NextResponse.next())))
```

Wrap it with the new step:

```typescript
      maybeSetPartner(request, maybeSetPwExp(request, maybeSetAcquisition(request, maybeSetFlagSeed(request, NextResponse.next()))))
```

Then check whether that composition appears more than once:

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && grep -n "maybeSetAcquisition(request" proxy.ts
```

Every call site that builds a response for a normal page request must be wrapped the same way. Wrap each one you find.

- [x] **Step 5: Confirm the proxy runs on the paths that carry partner links**

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && grep -n "matcher" -A 12 proxy.ts | tail -20
```

The matcher must cover `/`, `/for/:path*` and `/friend`. If it uses an exclusion pattern (everything except `_next`, static files and so on) these are already covered and nothing changes. If it uses an explicit include list, add `/friend`. Record which it is in the commit message.

- [x] **Step 6: Typecheck**

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && npm run typecheck
```

Expected: no errors.

- [x] **Step 7: Commit**

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && git add proxy.ts && git commit -m "Set a first-touch partner cookie in the proxy"
```

---

### Task 4: Merge the partner cookie into the job

The cookie is httpOnly, so the job row is where partner credit becomes durable. `app/api/jobs/route.ts:113` already calls `resolveRequestAcquisition`; the partner code is layered on top of whatever that returns.

**Files:**
- Modify: `app/api/jobs/route.ts`
- Test: `tests/test_attribution_rail_wiring.ts` (written in Task 3)

- [x] **Step 1: Read the current call site**

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && sed -n 105,125p app/api/jobs/route.ts
```

Expected: a `const requestAcquisition = resolveRequestAcquisition({ ... })` call taking `cookieHeader`, `userAgent` and `fallbackLandingPath`.

- [x] **Step 2: Layer the partner code on top**

Directly after that `const requestAcquisition = resolveRequestAcquisition({ ... });` statement, add:

```typescript
    // The partner cookie is first-touch and httpOnly, so the job row is where
    // the credit becomes durable — job.acquisition is what checkout copies
    // into Stripe metadata.
    const partnerFromCookie = normalizePartnerCode(
      request.headers.get("cookie")?.match(new RegExp(`(?:^|;\\s*)${PARTNER_COOKIE}=([^;]+)`))?.[1],
    );
    const acquisition = partnerFromCookie
      ? { ...requestAcquisition, partner: partnerFromCookie }
      : requestAcquisition;
```

Add the import beside the existing `@/lib/acquisition` import:

```typescript
import { PARTNER_COOKIE, normalizePartnerCode } from "@/lib/partner-attribution";
```

- [x] **Step 3: Use the merged value everywhere the old one was used**

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && grep -n "requestAcquisition" app/api/jobs/route.ts
```

Expected: the declaration plus uses near lines 153 and 161 (the lead-stub reuse branch and the create branch). Replace every use **after** the new `const acquisition` declaration with `acquisition`, leaving the declaration itself alone. Re-run the grep and confirm `requestAcquisition` now appears only in its own declaration and in the `acquisition` expression.

- [x] **Step 4: Run the wiring test and typecheck**

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && npx tsx tests/test_attribution_rail_wiring.ts; npm run typecheck
```

Expected: the test still fails, but now only on the `app/friend/route.ts` assertions (Task 5). Typecheck clean.

- [x] **Step 5: Commit**

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && git add app/api/jobs/route.ts && git commit -m "Store first-touch partner credit on the job"
```

---

### Task 5: The `/friend` link

A short, sayable URL for the moment a customer is asked where she got her photo. It carries no discount and no personal data.

**Files:**
- Create: `app/friend/route.ts`
- Test: `tests/test_attribution_rail_wiring.ts` (written in Task 3)

- [x] **Step 1: Write the implementation**

Create `app/friend/route.ts`:

```typescript
import { NextResponse } from "next/server";

/**
 * Durable link for the spoken answer to "where did you get that photo?".
 * Short and sayable, and it survives copy changes on the landing page. The
 * redirect carries `?via=friend` so the proxy records a referral touch and
 * the resulting order is attributable in Stripe metadata.
 */
export function GET(request: Request) {
  const target = new URL("/?via=friend", request.url);
  return NextResponse.redirect(target, { status: 302 });
}
```

A 302 rather than a 308: the destination is a marketing page that may move, and a permanent redirect would be cached in browsers indefinitely.

- [x] **Step 2: Run the wiring test to verify it passes**

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && npx tsx tests/test_attribution_rail_wiring.ts
```

Expected: PASS, printing `attribution rail wiring tests passed`.

- [x] **Step 3: Verify the redirect and the cookie locally**

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && npm run build
```

Expected: the build succeeds and the route list includes `/friend`.

- [x] **Step 4: Commit**

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && git add app/friend/route.ts tests/test_attribution_rail_wiring.ts && git commit -m "Add the /friend referral link"
```

---

### Task 6: Carry partner and content into Stripe

Two gaps: `content` never reaches Stripe although it is captured, and `metadata` lives only on the session, so a `charge.refunded` event cannot be traced back to an attribution or a payout.

**Files:**
- Modify: `app/api/checkout/route.ts`, `app/api/checkout/redirect/route.ts`, `app/api/checkout/upgrade/route.ts`, `app/api/checkout/upgrade/redirect/route.ts`, `app/api/subscription/checkout/route.ts`, `app/api/subscription/checkout/redirect/route.ts`
- Test: `tests/test_checkout_attribution_metadata.ts`

- [x] **Step 1: Extend the existing test**

In `tests/test_checkout_attribution_metadata.ts`, add the two new keys to the `for` loop's key list, so it reads:

```typescript
  for (const key of [
    "landing_variant",
    "acquisition_source",
    "acquisition_medium",
    "acquisition_campaign",
    "acquisition_landing",
    "acquisition_device",
    "acquisition_partner",
    "acquisition_content",
  ]) {
```

Then, after the two `assert.ok(!source.includes(...))` click-ID assertions and still inside the loop, add:

```typescript
  // Session metadata alone is not enough: charge.refunded carries the payment
  // intent, not the session, so a refund cannot be traced back to a partner
  // payout unless the intent carries the same metadata.
  assert.ok(
    source.includes("payment_intent_data") ? /payment_intent_data:\s*\{[^}]*metadata/s.test(source) : true,
    `${route} should mirror metadata into payment_intent_data`,
  );
```

Finally update the count in the last line so it reflects the new total:

```typescript
console.log("checkout attribution metadata tests passed");
```

- [x] **Step 2: Run the test to verify it fails**

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && npx tsx tests/test_checkout_attribution_metadata.ts
```

Expected: FAIL with `app/api/checkout/route.ts should put acquisition_partner into Stripe metadata`.

- [x] **Step 3: Add the two keys in all six routes**

In each of the six routes, find the `metadata` object that already spreads the acquisition fields and add these two lines after the `acquisition_device` line. In the four order routes the object is named `job`:

```typescript
      ...(job.acquisition?.partner ? { acquisition_partner: job.acquisition.partner } : {}),
      ...(job.acquisition?.content ? { acquisition_content: job.acquisition.content } : {}),
```

In the two subscription routes the object is `linkedJob` and the existing lines use optional chaining on it, so match that style:

```typescript
      ...(linkedJob?.acquisition?.partner ? { acquisition_partner: linkedJob.acquisition.partner } : {}),
      ...(linkedJob?.acquisition?.content ? { acquisition_content: linkedJob.acquisition.content } : {}),
```

Check each route for the exact variable name before editing:

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && grep -n "acquisition_device" app/api/checkout/route.ts app/api/checkout/redirect/route.ts app/api/checkout/upgrade/route.ts app/api/checkout/upgrade/redirect/route.ts app/api/subscription/checkout/route.ts app/api/subscription/checkout/redirect/route.ts
```

- [x] **Step 4: Mirror the metadata onto the payment intent**

In the four order routes, each has `payment_intent_data: { statement_descriptor: "HEADSHOTGEN" }`. Change each to:

```typescript
        payment_intent_data: { statement_descriptor: "HEADSHOTGEN", metadata },
```

Confirm the local variable really is called `metadata` in each route before editing:

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && grep -n "const metadata\|payment_intent_data" app/api/checkout/route.ts app/api/checkout/redirect/route.ts app/api/checkout/upgrade/route.ts app/api/checkout/upgrade/redirect/route.ts
```

If a route names it differently, use that route's own name. The two subscription routes use `subscription_data: { metadata }` and have no payment intent, so leave them as they are.

- [x] **Step 5: Run the test and typecheck**

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && npx tsx tests/test_checkout_attribution_metadata.ts && npm run typecheck
```

Expected: PASS and no type errors.

- [x] **Step 6: Commit**

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && git add app/api/checkout app/api/subscription tests/test_checkout_attribution_metadata.ts && git commit -m "Send partner and content attribution to Stripe and the payment intent"
```

---

### Task 7: The `/stats` acquisition panel

Without a readout the rail is invisible and the Phase 2a gate cannot be judged. Every count must require real money: coupon redemptions and feedback unlocks are genuine `paid` rows with `paidAmountCents: 0`.

**Files:**
- Modify: `app/api/admin/stats/route.ts`
- Modify: `app/stats/StatsClient.tsx`
- Test: `tests/test_stats_acquisition_panel.ts`

- [x] **Step 1: Write the failing test**

Create `tests/test_stats_acquisition_panel.ts`:

```typescript
import * as assert from "assert";
import { summarizeAcquisition } from "../lib/acquisition-summary";

const paidSession = (overrides: Record<string, unknown> = {}) => ({
  payment_status: "paid",
  amount_total: 2900,
  currency: "usd",
  metadata: { jobId: "j1", acquisition_source: "facebook", acquisition_medium: "paid_social" },
  ...overrides,
});

// Real-money orders are grouped by source.
const bySource = summarizeAcquisition([
  paidSession(),
  paidSession({ metadata: { jobId: "j2", acquisition_source: "facebook", acquisition_medium: "paid_social" } }),
  paidSession({ metadata: { jobId: "j3", acquisition_source: "friend", acquisition_medium: "referral" } }),
]);
assert.strictEqual(bySource.totalOrders, 3);
assert.strictEqual(bySource.totalRevenueCents, 8700);
assert.deepStrictEqual(
  bySource.sources.map((s) => [s.source, s.orders]),
  [["facebook", 2], ["friend", 1]],
);
// Non-paid share is what the day-120 gate reads.
assert.strictEqual(bySource.nonPaidOrders, 1);

// $0 unlocks are paid rows but not revenue: coupon redemptions and the
// feedback unlock both reach Stripe/jobs with amount_total 0.
const withFreeUnlocks = summarizeAcquisition([
  paidSession(),
  paidSession({ amount_total: 0, metadata: { jobId: "j4", acquisition_source: "friend" } }),
  paidSession({ amount_total: null, metadata: { jobId: "j5", acquisition_source: "friend" } }),
]);
assert.strictEqual(withFreeUnlocks.totalOrders, 1, "$0 sessions must not count as orders");
assert.strictEqual(withFreeUnlocks.nonPaidOrders, 0);

// Unpaid and abandoned sessions are ignored.
const withAbandoned = summarizeAcquisition([
  paidSession(),
  paidSession({ payment_status: "unpaid" }),
  paidSession({ payment_status: "no_payment_required" }),
]);
assert.strictEqual(withAbandoned.totalOrders, 1);

// Partner credit is reported separately from source, because a partner-referred
// visitor who returns via Facebook keeps source=facebook but keeps the partner.
const withPartners = summarizeAcquisition([
  paidSession({ metadata: { jobId: "j6", acquisition_source: "partner", acquisition_partner: "coachjane" } }),
  paidSession({ metadata: { jobId: "j7", acquisition_source: "facebook", acquisition_partner: "coachjane" } }),
  paidSession({ metadata: { jobId: "j8", acquisition_source: "facebook" } }),
]);
assert.deepStrictEqual(
  withPartners.partners.map((p) => [p.partner, p.orders, p.revenueCents]),
  [["coachjane", 2, 5800]],
);

// A session with no attribution is still counted, labelled rather than dropped.
const unlabelled = summarizeAcquisition([paidSession({ metadata: { jobId: "j9" } })]);
assert.strictEqual(unlabelled.sources[0].source, "unknown");

// Duplicate sessions for one job (retried checkout) count once.
const duplicated = summarizeAcquisition([paidSession(), paidSession()]);
assert.strictEqual(duplicated.totalOrders, 1, "one job must not count twice");

console.log("stats acquisition summary tests passed");
```

- [x] **Step 2: Run the test to verify it fails**

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && npx tsx tests/test_stats_acquisition_panel.ts
```

Expected: FAIL with `Cannot find module '../lib/acquisition-summary'`.

- [x] **Step 3: Write the aggregation**

Create `lib/acquisition-summary.ts`:

```typescript
/**
 * Groups real-money Stripe checkout sessions by acquisition source and
 * partner. `$0` sessions are excluded on purpose: coupon redemptions and the
 * feedback unlock both produce genuine `paid` rows with no revenue, and
 * counting them would inflate a partner payout.
 */

export interface AcquisitionSessionLike {
  payment_status?: string | null;
  amount_total?: number | null;
  metadata?: Record<string, string | undefined> | null;
}

export interface AcquisitionGroup {
  source: string;
  medium?: string;
  orders: number;
  revenueCents: number;
}

export interface AcquisitionPartnerGroup {
  partner: string;
  orders: number;
  revenueCents: number;
}

export interface AcquisitionSummary {
  totalOrders: number;
  totalRevenueCents: number;
  /** Orders whose source is not a paid channel — the day-120 gate reads this. */
  nonPaidOrders: number;
  sources: AcquisitionGroup[];
  partners: AcquisitionPartnerGroup[];
}

const PAID_CHANNEL_SOURCES = new Set(["facebook", "facebook.com", "instagram", "google", "bing", "linkedin"]);

export function summarizeAcquisition(sessions: AcquisitionSessionLike[]): AcquisitionSummary {
  const sourceMap = new Map<string, AcquisitionGroup>();
  const partnerMap = new Map<string, AcquisitionPartnerGroup>();
  const countedJobIds = new Set<string>();
  let totalOrders = 0;
  let totalRevenueCents = 0;
  let nonPaidOrders = 0;

  for (const session of sessions) {
    if (session.payment_status !== "paid") continue;
    const amount = session.amount_total ?? 0;
    if (amount <= 0) continue;

    const metadata = session.metadata ?? {};
    const jobId = metadata.jobId ?? metadata.linkedJobId;
    // A retried checkout can leave several paid sessions for one job.
    if (jobId) {
      if (countedJobIds.has(jobId)) continue;
      countedJobIds.add(jobId);
    }

    const source = metadata.acquisition_source ?? "unknown";
    const medium = metadata.acquisition_medium;
    const partner = metadata.acquisition_partner;

    totalOrders += 1;
    totalRevenueCents += amount;
    if (!PAID_CHANNEL_SOURCES.has(source)) nonPaidOrders += 1;

    const sourceEntry = sourceMap.get(source) ?? { source, ...(medium && { medium }), orders: 0, revenueCents: 0 };
    sourceEntry.orders += 1;
    sourceEntry.revenueCents += amount;
    sourceMap.set(source, sourceEntry);

    if (partner) {
      const partnerEntry = partnerMap.get(partner) ?? { partner, orders: 0, revenueCents: 0 };
      partnerEntry.orders += 1;
      partnerEntry.revenueCents += amount;
      partnerMap.set(partner, partnerEntry);
    }
  }

  const byOrdersDesc = <T extends { orders: number }>(a: T, b: T) => b.orders - a.orders;

  return {
    totalOrders,
    totalRevenueCents,
    nonPaidOrders,
    sources: [...sourceMap.values()].sort(byOrdersDesc),
    partners: [...partnerMap.values()].sort(byOrdersDesc),
  };
}
```

- [x] **Step 4: Run the test to verify it passes**

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && npx tsx tests/test_stats_acquisition_panel.ts
```

Expected: PASS, printing `stats acquisition summary tests passed`.

- [x] **Step 5: Feed it from the stats route**

`app/api/admin/stats/route.ts` already pages `stripe.checkout.sessions.list` inside `loadStripeFunnelSince`, but that function filters to a job cohort and returns only id sets. Add a second, independent loader beneath it so the acquisition panel covers every real order in the window, not just jobs in the 30-day cohort:

```typescript
async function loadAcquisitionSince(sinceMs: number): Promise<AcquisitionSummary | null> {
  const stripe = getStripe();
  if (!stripe) return null;

  const sessions: AcquisitionSessionLike[] = [];
  let startingAfter: string | undefined;
  try {
    for (let pageNumber = 0; pageNumber < 20; pageNumber++) {
      const page = await stripe.checkout.sessions.list({
        created: { gte: Math.floor(sinceMs / 1000) },
        limit: 100,
        ...(startingAfter ? { starting_after: startingAfter } : {}),
      });
      for (const session of page.data) {
        sessions.push({
          payment_status: session.payment_status,
          amount_total: session.amount_total,
          metadata: session.metadata ?? undefined,
        });
      }
      if (!page.has_more || page.data.length === 0) break;
      startingAfter = page.data.at(-1)?.id;
      if (!startingAfter) break;
    }
    return summarizeAcquisition(sessions);
  } catch (error) {
    console.error("[admin/stats] acquisition summary failed", error);
    return null;
  }
}
```

Add the imports at the top of the route:

```typescript
import { summarizeAcquisition } from "@/lib/acquisition-summary";
import type { AcquisitionSessionLike, AcquisitionSummary } from "@/lib/acquisition-summary";
```

Then, next to the existing Stripe call in the handler, call it for a 30-day window and add the result to the response object:

```typescript
  const acquisition30d = await loadAcquisitionSince(Date.now() - 30 * 24 * 60 * 60 * 1000);
```

and inside the final `return NextResponse.json({ ... })`, add:

```typescript
    acquisition30d,
```

Find the existing Stripe call and the response object first:

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && grep -n "loadStripeFunnelSince(\|return NextResponse.json({" app/api/admin/stats/route.ts
```

Egress note: this adds Stripe API calls, not Supabase reads. Do not add a jsonb scan here — the Supabase project was suspended for egress on 2026-06-25, and `listRecentJobs(30)` is already loaded in this handler.

- [x] **Step 6: Render the panel**

In `app/stats/StatsClient.tsx`, add a section following the existing pattern (a `<section className="rounded-2xl border border-stone-200 bg-white p-5 sm:p-6">` with an `<h2 className="text-lg font-semibold text-stone-900">`). Place it directly after the "7-day conversion funnel" section so the two revenue readouts sit together:

```tsx
      {data.acquisition30d && (
        <section className="rounded-2xl border border-stone-200 bg-white p-5 sm:p-6">
          <h2 className="text-lg font-semibold text-stone-900">Acquisition (30d, real money only)</h2>
          <p className="mt-1 text-sm text-stone-500">
            Paid Stripe sessions above $0. Coupon and feedback unlocks are excluded.
          </p>
          <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3">
            <Kpi label="Orders" value={String(data.acquisition30d.totalOrders)} compact />
            <Kpi
              label="Revenue"
              value={`$${(data.acquisition30d.totalRevenueCents / 100).toFixed(0)}`}
              compact
            />
            <Kpi
              label="Non-paid orders"
              value={String(data.acquisition30d.nonPaidOrders)}
              sub="partner, friend, gift, search"
              accent={data.acquisition30d.nonPaidOrders > 0}
              compact
            />
          </div>
          <table className="mt-4 w-full text-sm">
            <thead>
              <tr className="text-left text-stone-500">
                <th className="py-1 font-medium">Source</th>
                <th className="py-1 text-right font-medium">Orders</th>
                <th className="py-1 text-right font-medium">Revenue</th>
              </tr>
            </thead>
            <tbody>
              {data.acquisition30d.sources.map((row) => (
                <tr key={row.source} className="border-t border-stone-100">
                  <td className="py-1.5 text-stone-900">{row.source}</td>
                  <td className="py-1.5 text-right text-stone-700">{row.orders}</td>
                  <td className="py-1.5 text-right text-stone-700">${(row.revenueCents / 100).toFixed(0)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {data.acquisition30d.partners.length > 0 && (
            <>
              <h3 className="mt-6 text-sm font-semibold text-stone-900">By partner</h3>
              <table className="mt-2 w-full text-sm">
                <tbody>
                  {data.acquisition30d.partners.map((row) => (
                    <tr key={row.partner} className="border-t border-stone-100">
                      <td className="py-1.5 text-stone-900">{row.partner}</td>
                      <td className="py-1.5 text-right text-stone-700">{row.orders}</td>
                      <td className="py-1.5 text-right text-stone-700">${(row.revenueCents / 100).toFixed(0)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
        </section>
      )}
```

The component's data is typed where `StatsClient` declares its state. Add the field to that type:

```typescript
  acquisition30d?: {
    totalOrders: number;
    totalRevenueCents: number;
    nonPaidOrders: number;
    sources: Array<{ source: string; medium?: string; orders: number; revenueCents: number }>;
    partners: Array<{ partner: string; orders: number; revenueCents: number }>;
  } | null;
```

Find where to put it:

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && grep -n "funnel7d" app/stats/StatsClient.tsx | head -5
```

Match whatever shape that type declaration uses, and confirm `Kpi`'s props (`label`, `value`, `sub`, `accent`, `compact`) against its definition near the bottom of the file before using them.

- [x] **Step 7: Typecheck and build**

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && npm run typecheck && npm run build
```

Expected: no type errors, build succeeds.

- [x] **Step 8: Commit**

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && git add lib/acquisition-summary.ts app/api/admin/stats/route.ts app/stats/StatsClient.tsx tests/test_stats_acquisition_panel.ts && git commit -m "Add a real-money acquisition panel to /stats"
```

---

### Task 8: Full suite, PR, deploy, prod walk

- [x] **Step 1: Run everything**

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && npm run check
```

Expected: lint, typecheck, every `tests/` file and the build all pass, **except** possibly the 7 pre-existing failures in `tests/test_lp_hero_rewrite.py`. Those assert homepage copy that no longer exists, fail identically on a pristine `origin/main`, and another session is fixing them. Confirm the count is exactly 7 and that every named failure is in that one file:

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && python3 -m pytest -q 2>&1 | tail -12
```

Any failure outside `test_lp_hero_rewrite.py` is yours. Fix it before continuing.

- [x] **Step 2: Open the PR**

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && git push -u origin feat/attribution-rail && gh pr create --title "Attribution rail: partner and referral credit end to end (Phase 1)" --body "$(cat <<'EOF'
## Why

Every order today is attributable only to a paid channel; there is no way to credit a partner, a friend link or a gift with real money. This is the measurement spine the rest of the acquisition work gates on, and it is the piece every reviewer of the strategy independently asked for first.

## What

- `?partner=CODE` and `?via=friend|gift|nudge|blast|analyzer` are now recognised acquisition touches, validated and normalised in `lib/partner-attribution.ts` (lowercase, `[a-z0-9_-]`, 40 chars) so a pasted link cannot inject anything into a cookie, Stripe metadata or a page.
- Partner credit lives in its own `hs_partner` cookie: first-touch, 60 days, never overwritten while valid. It cannot live in `hs_acq`, which is last-touch and is deliberately replaced by any external referrer, so a partner-referred visitor returning through a Facebook ad would otherwise lose the credit.
- The cookie is merged into `job.acquisition` at job creation, since it is httpOnly and the job row is what checkout reads.
- All six checkout routes now send `acquisition_partner` and `acquisition_content` (content was captured but never reached Stripe), and the four order routes mirror the whole metadata object into `payment_intent_data`, so a future `charge.refunded` can be traced back to a partner payout.
- `/friend` is a short, sayable link that redirects to `?via=friend`.
- `/stats` gains a 30-day acquisition panel grouped by source and partner.

## Real money only

Coupon redemptions and the image-feedback unlock are genuine `paid` rows with `paidAmountCents: 0`. Every count in the new panel requires `payment_status === "paid"` **and** `amount_total > 0`, and de-duplicates by `jobId` so a retried checkout is one order. Without that the first partner payout would be computed off free unlocks.

## Privacy

Labels only. No click IDs, no full referrer URLs, no query strings. The existing assertions that `fbclid`/`gclid` are never persisted still pass, and a new test proves a click ID is not serialised when a partner code is present.

## Tests

New: `tests/test_partner_attribution.ts`, `tests/test_attribution_rail_wiring.ts`, `tests/test_stats_acquisition_panel.ts`. Extended: `tests/test_acquisition.ts` (partner/via capture, cookie round-trip, utm precedence) and `tests/test_checkout_attribution_metadata.ts` (new keys in all six routes, metadata mirrored to the intent). Each was confirmed to fail first.

The 7 failures in `tests/test_lp_hero_rewrite.py` are pre-existing, fail identically on a pristine `origin/main`, and are being fixed separately.

## Not in this PR

The partner programme itself (`partners` table, `/partners` page, the client discount, payouts) is Phase 2a and depends on this rail. The post-purchase share surface, the "how did you hear about us?" question and the day-10 nudge are Phase 1b. No pre-purchase surface changes here.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [x] **Step 3: Wait for CI, then merge**

Check the bound PR's status rather than polling `gh pr checks`. The Vercel check must be green. If it reports "Deployment was blocked", the commit author is wrong — see the note in Task 1 Step 5.

- [ ] **Step 4: Prod walk** — in progress at time of writing

A green suite has hidden four real bugs on this codebase before, so verify against production after the deploy. Substitute a real job id you create through the site.

```bash
S=https://www.headshot-generators.com
curl -s -o /dev/null -w "/friend -> %{http_code} -> %{redirect_url}\n" "$S/friend"
curl -s -D- -o /dev/null "$S/?partner=TESTCOACH" | grep -i "set-cookie: hs_partner"
curl -s -D- -o /dev/null "$S/?partner=bad%20code" | grep -ci "set-cookie: hs_partner"
```

Expected: `/friend` redirects carrying `via=friend`; a valid partner code sets an httpOnly `hs_partner` cookie; an invalid one sets nothing (count `0`).

Then walk a real order: visit `/?partner=TESTCOACH`, create a job, and take it through checkout with a test coupon. Confirm in the Stripe dashboard that **both** the session and the payment intent carry `acquisition_partner=testcoach`, and that `/stats` shows the order under both the source table and the partner table. Confirm a `$0` coupon unlock does **not** appear in either.

- [x] **Step 5: Report**

State what passed with actual output, and name anything unverified. Then stop; Phase 1b is a separate plan.

---

## Self-review

**Spec coverage.** Spec §4 M1 asks for `?partner=`, `?via=`, `/friend`, `/upload?gift=CODE`, the `hs_partner` first-touch cookie, `acquisition_partner`/`acquisition_content` in Stripe, mirroring into `payment_intent_data`, and a `/stats` panel. All are covered except `?gift=CODE`, which is deliberately deferred: it needs the `gifts` table from Phase 2b, and `gift` is already in `VIA_LABELS` so the rail is ready for it. Spec §8 steps 1, 2, 3, 4 and 6 are covered; step 5 (`charge.refunded`) is Phase 2a, and this PR's payment-intent metadata is its prerequisite. GA4 event additions belong with the Phase 1b surfaces that fire them.

**Placeholders.** None. Every code step carries its code; every command states expected output. Where a line number could have drifted, the step opens with a `grep` to locate the real one rather than asserting a number.

**Type consistency.** `normalizePartnerCode` returns `string | undefined` and is used that way in the proxy, the job route, `parseAcquisitionContext` and the tests. `AcquisitionContext.partner` is optional throughout, and the cookie key `p` is added to both `serializeAcquisitionContext` and `parseAcquisitionContext`. `summarizeAcquisition` returns `AcquisitionSummary`, and the `StatsClient` type mirrors its field names (`totalOrders`, `totalRevenueCents`, `nonPaidOrders`, `sources`, `partners`) exactly. `VIA_LABELS` is the single source for the label set, consumed by `isKnownViaLabel` and `normalizeViaLabel`.

**One risk worth naming.** `PAID_CHANNEL_SOURCES` in `lib/acquisition-summary.ts` decides what counts as "non-paid", and it is a hardcoded set. If a new ad channel is added and not listed, its orders would be miscounted as organic and could flatter the day-120 gate. The panel shows the full source table beside the number so the error is visible rather than silent.
