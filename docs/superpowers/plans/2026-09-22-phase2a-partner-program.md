# Phase 2a — Partner Program Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the partner label the rail already carries into a real programme: a validated partner, a discount their client can see, a payout figure that is safe to pay, and a page that explains the terms.

**Architecture:** A `partners` table becomes the source of truth for which codes are real. The paywall applies a server-side 15% discount when a job carries a valid partner, so the client gets something the partner can promise. A `charge.refunded` webhook branch marks refunds so they never get paid out. `/stats` gains a payout report computing 30% of net on first purchases only, past a 30-day hold.

**Tech Stack:** Next.js 15 App Router, TypeScript, Supabase (`partners` table, migration 008), Stripe, standalone `tsx` tests under `tests/`.

**Repo:** `/Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio`, branch from `origin/main`. Commit plainly with no `-c user.name`/`-c user.email` override — the repo's local config is authorised on Vercel and an override makes the deploy fail with "Deployment was blocked".

**Spec:** `docs/superpowers/specs/2026-09-21-contagious-acquisition-design.md` §4 M2. Depends on the rail in #42 and #44, both live.

---

## Read this first: you are building ahead of demand

`docs/partners/outreach-kit.md` records the recommendation **not** to build this until at least 3 partners are producing real orders, because partner tracking already works end to end without any of it. The founder asked for it anyway, which is their call to make.

Two consequences for how you build:

- **Nothing here may break the working manual path.** Today an unknown `?partner=` code still records `acquisition_partner` and still shows on `/stats`. After this ships, an unknown code must keep doing exactly that; the table gates the *discount and payout*, not the attribution.
- **Keep it small.** No partner dashboard, no self-serve signup, no automated payouts. The founder inserts rows by hand until volume justifies more.

---

## Background an engineer needs

- **`job.acquisition.partner`** is set at upload from the `hs_partner` cookie and spread into Stripe as `acquisition_partner` on both the session and the payment intent. That plumbing is done; do not rebuild it.
- **The discount branch already exists** in all four order routes: `...(stripeCouponId ? { discounts: [{ coupon: stripeCouponId }] } : { allow_promotion_codes: true })`. Stripe forbids `allow_promotion_codes: true` alongside `discounts`, and `app/api/checkout/route.ts:213` already encodes that as `allow_promotion_codes: !stripeCouponId`. A partner discount has to flow through this same branch rather than adding a second one.
- **`COUPON_CODES` is now `COMEBACK15:15` only.** The partner discount must not be an env code; it is a Stripe coupon id resolved from the partner row, so it can never be typed by a customer.
- **Supabase egress is a live constraint.** The project was suspended for it on 2026-06-25. Look a partner up only when `job.acquisition.partner` is actually present, and cache the result per instance.
- **`$0` rows are everywhere.** Coupon redemptions and the feedback unlock produce `paid` rows with `paidAmountCents: 0`. Every payout figure must require real money.
- **Store pattern to copy:** `lib/drops-store.ts` — Supabase-backed when configured, in-memory `Map` fallback for local dev and tests, with explicit row mapping. Follow it exactly.

---

## File structure

| File | Responsibility | Change |
|---|---|---|
| `supabase/migrations/008_partners.sql` | The `partners` table | **Create** |
| `lib/partners.ts` | Lookup, validation, per-instance cache, payout maths | **Create** |
| `app/api/checkout/route.ts` + 3 sibling order routes | Apply the partner client discount | Modify |
| `app/api/webhooks/stripe/route.ts` | `charge.refunded` branch | Modify |
| `app/api/admin/stats/route.ts` | Payout report | Modify |
| `app/stats/StatsClient.tsx` | Render payouts due | Modify |
| `app/partners/page.tsx` | Public terms page | **Create** |
| `scripts/add-partner.ts` | Insert a partner row from the CLI | **Create** |
| `tests/test_partners.ts` | Validation, cache, payout maths | **Create** |
| `tests/test_partner_discount.ts` | Discount wiring in all four routes | **Create** |

---

### Task 1: The partners table

**Files:**
- Create: `supabase/migrations/008_partners.sql`

- [ ] **Step 1: Write the migration**

```sql
-- Migration 008: Partner programme.
-- The attribution rail already records acquisition_partner for ANY code; this
-- table gates only the client discount and the payout, so an unknown code
-- still attributes normally and simply earns nothing.
create table if not exists public.partners (
  code text primary key,                       -- lowercase [a-z0-9_-], matches normalizePartnerCode
  name text not null,
  email text not null,                         -- payout address AND self-referral guard
  commission_percent int not null default 30,
  client_discount_percent int not null default 15,
  stripe_coupon_id text,                       -- the client discount coupon; null = no discount
  active boolean not null default true,
  segment text,                                -- reviewer | coach | creator | realtor | other
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists partners_active_idx on public.partners (active);
```

- [ ] **Step 2: Apply it**

Migrations in this project are run by hand in the Supabase dashboard SQL editor, the same way 004 and 007 were. Paste the file and run it, then confirm:

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && set -a; source <(grep -E "^(SUPABASE_URL|SUPABASE_SERVICE_ROLE_KEY)=" .env.local); set +a
curl -s "$SUPABASE_URL/rest/v1/partners?select=code&limit=1" -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY"
```

Expected: `[]` rather than an error about a missing relation.

- [ ] **Step 3: Commit**

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && git add supabase/migrations/008_partners.sql && git commit -m "Add partners table"
```

---

### Task 2: Partner lookup and payout maths

**Files:**
- Create: `lib/partners.ts`
- Test: `tests/test_partners.ts`

- [ ] **Step 1: Write the failing test**

Create `tests/test_partners.ts`:

```typescript
import * as assert from "assert";
import { computePartnerPayouts, isPayoutEligible, type PartnerOrder } from "../lib/partners";

const partner = { code: "coachjane", email: "jane@example.com", commissionPercent: 30 };
const DAY = 24 * 60 * 60 * 1000;
const now = 1_790_000_000_000;
const old = now - 40 * DAY;   // past the 30-day hold
const fresh = now - 5 * DAY;  // still inside the hold

const order = (o: Partial<PartnerOrder> = {}): PartnerOrder => ({
  partnerCode: "coachjane",
  customerEmail: "buyer@example.com",
  amountPaidCents: 2465,   // $29 less the 15% client discount
  paidAt: old,
  refunded: false,
  ...o,
});

// Commission is 30% of what the client actually paid, not of list price.
assert.strictEqual(isPayoutEligible(order(), now), true);
const payouts = computePartnerPayouts([order()], [partner], now);
assert.strictEqual(payouts.length, 1);
assert.strictEqual(payouts[0].partnerCode, "coachjane");
assert.strictEqual(payouts[0].orders, 1);
assert.strictEqual(payouts[0].payoutCents, 740);   // round(2465 * 0.30)

// Refunded orders never pay out.
assert.strictEqual(isPayoutEligible(order({ refunded: true }), now), false);
// $0 unlocks are paid rows with no revenue.
assert.strictEqual(isPayoutEligible(order({ amountPaidCents: 0 }), now), false);
// Inside the 30-day hold, the money is not safe to send yet.
assert.strictEqual(isPayoutEligible(order({ paidAt: fresh }), now), false);
// Self-referral: the partner buying through their own link earns nothing.
assert.strictEqual(
  isPayoutEligible(order({ customerEmail: "JANE@example.com" }), now, partner.email),
  false,
);

// First purchase only: a repeat order from the same customer does not pay twice.
const repeat = computePartnerPayouts(
  [order(), order({ paidAt: old + DAY })],
  [partner],
  now,
);
assert.strictEqual(repeat[0].orders, 1, "commission is first purchase only");

// Held and refunded orders are reported separately so the founder can see why
// a number is lower than expected.
const mixed = computePartnerPayouts(
  [order(), order({ customerEmail: "b2@example.com", paidAt: fresh }), order({ customerEmail: "b3@example.com", refunded: true })],
  [partner],
  now,
);
assert.strictEqual(mixed[0].orders, 1);
assert.strictEqual(mixed[0].heldOrders, 1);
assert.strictEqual(mixed[0].refundedOrders, 1);

// A code with no partner row earns nothing but must not throw: unknown codes
// still attribute, they just do not pay.
assert.deepStrictEqual(computePartnerPayouts([order({ partnerCode: "ghost" })], [partner], now), []);

console.log("partner payout tests passed");
```

- [ ] **Step 2: Run it and watch it fail**

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && npx tsx tests/test_partners.ts
```

Expected: `Cannot find module '../lib/partners'`.

- [ ] **Step 3: Write the module**

Create `lib/partners.ts`. Follow `lib/drops-store.ts`: Supabase when configured, in-memory `Map` otherwise.

```typescript
import { getSupabaseServer, isSupabaseEnabled } from "./supabase-server";
import { normalizePartnerCode } from "./partner-attribution";

export interface Partner {
  code: string;
  name: string;
  email: string;
  commissionPercent: number;
  clientDiscountPercent: number;
  stripeCouponId: string | null;
  active: boolean;
}

export interface PartnerOrder {
  partnerCode: string;
  customerEmail: string;
  /** What the customer actually paid, in cents. $0 unlocks are excluded. */
  amountPaidCents: number;
  paidAt: number;
  refunded: boolean;
}

export interface PartnerPayout {
  partnerCode: string;
  partnerEmail: string;
  orders: number;
  payoutCents: number;
  heldOrders: number;
  refundedOrders: number;
}

/** Commission is held until the refund window closes. */
export const PAYOUT_HOLD_MS = 30 * 24 * 60 * 60 * 1000;

export function isPayoutEligible(
  order: PartnerOrder,
  now: number,
  partnerEmail?: string,
): boolean {
  if (order.refunded) return false;
  // Coupon redemptions and the feedback unlock are paid rows with no revenue.
  if (order.amountPaidCents <= 0) return false;
  if (now - order.paidAt < PAYOUT_HOLD_MS) return false;
  if (
    partnerEmail &&
    order.customerEmail.trim().toLowerCase() === partnerEmail.trim().toLowerCase()
  ) {
    return false;
  }
  return true;
}

export function computePartnerPayouts(
  orders: PartnerOrder[],
  partners: Array<Pick<Partner, "code" | "email" | "commissionPercent">>,
  now: number,
): PartnerPayout[] {
  const byCode = new Map(partners.map((p) => [p.code, p]));
  const result = new Map<string, PartnerPayout>();
  // First purchase only, per customer per partner.
  const countedCustomers = new Map<string, Set<string>>();

  for (const order of [...orders].sort((a, b) => a.paidAt - b.paidAt)) {
    const partner = byCode.get(order.partnerCode);
    if (!partner) continue; // unknown code: attributes, earns nothing

    const entry =
      result.get(partner.code) ??
      {
        partnerCode: partner.code,
        partnerEmail: partner.email,
        orders: 0,
        payoutCents: 0,
        heldOrders: 0,
        refundedOrders: 0,
      };

    if (order.refunded) {
      entry.refundedOrders += 1;
    } else if (order.amountPaidCents > 0 && now - order.paidAt < PAYOUT_HOLD_MS) {
      entry.heldOrders += 1;
    } else if (isPayoutEligible(order, now, partner.email)) {
      const seen = countedCustomers.get(partner.code) ?? new Set<string>();
      const customer = order.customerEmail.trim().toLowerCase();
      if (!seen.has(customer)) {
        seen.add(customer);
        countedCustomers.set(partner.code, seen);
        entry.orders += 1;
        entry.payoutCents += Math.round((order.amountPaidCents * partner.commissionPercent) / 100);
      }
    }
    result.set(partner.code, entry);
  }

  return [...result.values()].filter(
    (p) => p.orders > 0 || p.heldOrders > 0 || p.refundedOrders > 0,
  );
}

// ---- storage ----

const memoryPartners = new Map<string, Partner>();
/** Per-instance cache: a partner row changes rarely and Supabase egress is a
 *  live constraint (the project was suspended for it on 2026-06-25). */
const partnerCache = new Map<string, { partner: Partner | null; at: number }>();
const PARTNER_CACHE_TTL_MS = 5 * 60 * 1000;

interface PartnerRow {
  code: string;
  name: string;
  email: string;
  commission_percent: number;
  client_discount_percent: number;
  stripe_coupon_id: string | null;
  active: boolean;
}

function rowToPartner(row: PartnerRow): Partner {
  return {
    code: row.code,
    name: row.name,
    email: row.email,
    commissionPercent: row.commission_percent,
    clientDiscountPercent: row.client_discount_percent,
    stripeCouponId: row.stripe_coupon_id,
    active: row.active,
  };
}

/** Returns the active partner for a code, or null. Never throws: a lookup
 *  failure must not break checkout, it just means no discount. */
export async function getActivePartner(rawCode: string | null | undefined): Promise<Partner | null> {
  const code = normalizePartnerCode(rawCode);
  if (!code) return null;

  const cached = partnerCache.get(code);
  if (cached && Date.now() - cached.at < PARTNER_CACHE_TTL_MS) return cached.partner;

  let partner: Partner | null = null;
  if (isSupabaseEnabled()) {
    try {
      const supabase = getSupabaseServer();
      if (supabase) {
        const { data } = await supabase
          .from("partners")
          .select("*")
          .eq("code", code)
          .eq("active", true)
          .maybeSingle();
        partner = data ? rowToPartner(data as PartnerRow) : null;
      }
    } catch {
      return null; // never break checkout over a partner lookup
    }
  } else {
    partner = memoryPartners.get(code) ?? null;
  }

  partnerCache.set(code, { partner, at: Date.now() });
  return partner;
}

/** Test/dev seam for the in-memory fallback. */
export function __setMemoryPartner(partner: Partner): void {
  memoryPartners.set(partner.code, partner);
  partnerCache.delete(partner.code);
}
```

- [ ] **Step 4: Run the test**

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && npx tsx tests/test_partners.ts && npm run typecheck
```

Expected: PASS, no type errors.

- [ ] **Step 5: Commit**

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && git add lib/partners.ts tests/test_partners.ts && git commit -m "Add partner lookup and payout maths"
```

---

### Task 3: The client discount

The partner promises their audience something. This is that something, applied server-side so it can never be typed, shared or scraped.

**Files:**
- Modify: `app/api/checkout/route.ts`, `app/api/checkout/redirect/route.ts`, `app/api/checkout/upgrade/route.ts`, `app/api/checkout/upgrade/redirect/route.ts`
- Test: `tests/test_partner_discount.ts`

- [ ] **Step 1: Write the failing test**

Create `tests/test_partner_discount.ts`:

```typescript
import * as assert from "assert";
import { readFileSync } from "fs";

const routes = [
  "app/api/checkout/route.ts",
  "app/api/checkout/redirect/route.ts",
  "app/api/checkout/upgrade/route.ts",
  "app/api/checkout/upgrade/redirect/route.ts",
];

for (const route of routes) {
  const source = readFileSync(route, "utf8");
  assert.ok(source.includes("getActivePartner"), `${route} should resolve the partner`);
  assert.ok(
    source.includes("job.acquisition?.partner"),
    `${route} should only look up when the job carries a partner (Supabase egress)`,
  );
  // A typed coupon must win, so the customer never loses a discount they
  // entered, and the two never stack into a bigger one.
  assert.ok(
    /stripeCouponId\s*\?\?|stripeCouponId\s*\|\|/.test(source),
    `${route} should prefer an explicit coupon over the partner discount`,
  );
  // Stripe rejects allow_promotion_codes alongside discounts.
  assert.ok(
    !/allow_promotion_codes:\s*true[\s\S]{0,80}discounts:/.test(source),
    `${route} must not pass both allow_promotion_codes and discounts`,
  );
}

console.log("partner discount wiring tests passed");
```

- [ ] **Step 2: Run it and watch it fail**

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && npx tsx tests/test_partner_discount.ts
```

Expected: FAIL on `app/api/checkout/route.ts should resolve the partner`.

- [ ] **Step 3: Apply the discount in each route**

In every one of the four routes, find where `stripeCouponId` is computed:

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && grep -n "const stripeCouponId" app/api/checkout/route.ts app/api/checkout/redirect/route.ts app/api/checkout/upgrade/route.ts app/api/checkout/upgrade/redirect/route.ts
```

Immediately after that line, add:

```typescript
    // Partner client discount: server-applied, so it can never be typed,
    // shared or scraped the way an env coupon code could. A coupon the
    // customer entered wins, so nobody loses a discount they asked for and
    // the two never stack. Looked up only when the job carries a partner,
    // because Supabase egress is a live constraint.
    const partner = job.acquisition?.partner ? await getActivePartner(job.acquisition.partner) : null;
    const effectiveCouponId = stripeCouponId ?? partner?.stripeCouponId ?? null;
```

Then replace every use of `stripeCouponId` **inside the Stripe session object** with `effectiveCouponId`. Leave the log lines alone so `hasCoupon` still reports what the customer typed. In `app/api/checkout/route.ts` that includes the `allow_promotion_codes: !stripeCouponId` at roughly line 213, which becomes `allow_promotion_codes: !effectiveCouponId`.

Add the import:

```typescript
import { getActivePartner } from "@/lib/partners";
```

- [ ] **Step 4: Check each route really switched**

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && grep -n "discounts: \[{ coupon:\|allow_promotion_codes" app/api/checkout/route.ts app/api/checkout/redirect/route.ts app/api/checkout/upgrade/route.ts app/api/checkout/upgrade/redirect/route.ts
```

Every one of those lines must reference `effectiveCouponId`, not `stripeCouponId`.

- [ ] **Step 5: Run the tests**

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && npx tsx tests/test_partner_discount.ts && npx tsx tests/test_checkout_attribution_metadata.ts && npm run typecheck
```

Expected: all PASS.

- [ ] **Step 6: Create the Stripe coupon and note its id**

One 15%-off coupon shared by all partners at the default rate, created once:

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && set -a; source <(grep -E "^STRIPE_SECRET_KEY=" .env.local); set +a
cat > scripts/_mint_partner_coupon.ts <<'TS'
import Stripe from "stripe";
async function main() {
  const stripe = new Stripe(process.env.STRIPE_SECRET_KEY!.trim(), { apiVersion: "2026-02-25.clover" });
  const coupon = await stripe.coupons.create({
    percent_off: 15,
    duration: "once",
    name: "Partner client discount (15% off)",
    metadata: { kind: "partner_client_discount" },
  });
  console.log("PARTNER_CLIENT_COUPON_ID =", coupon.id);
}
main().catch((e) => { console.error("FAILED:", e.message); process.exit(1); });
TS
npx tsx scripts/_mint_partner_coupon.ts; rm -f scripts/_mint_partner_coupon.ts
```

Record the printed id. It goes in each partner row's `stripe_coupon_id`, not in an env var, so a partner can later be given a different rate without a deploy.

- [ ] **Step 7: Commit**

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && git add app/api/checkout tests/test_partner_discount.ts && git commit -m "Apply the partner client discount server-side"
```

---

### Task 4: Refunds must not pay out

`charge.refunded` carries the payment intent, which is why Phase 1a mirrored the metadata onto it. This is where that pays off.

**Files:**
- Modify: `app/api/webhooks/stripe/route.ts`

- [ ] **Step 1: Confirm the job already has refund fields**

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && grep -n '"refunded"\|"stripeRefundId"' lib/store.ts && grep -n "refunded?:" lib/types.ts
```

Expected: both already exist in the `updateJob` allowlist and on the `Job` type. Do not add new fields.

- [ ] **Step 2: Add the branch**

In `app/api/webhooks/stripe/route.ts`, beside the existing `if (event.type === "checkout.session.completed")`, add:

```typescript
  if (event.type === "charge.refunded") {
    const charge = event.data.object as Stripe.Charge;
    // The session's metadata was mirrored onto the payment intent in Phase 1a
    // precisely so a refund can be traced back to the order it reverses.
    const jobId = charge.metadata?.jobId;
    if (jobId) {
      await updateJob(jobId, { refunded: true, stripeRefundId: charge.id });
      auditLog("charge.refunded", { jobId, chargeId: charge.id });
    } else {
      auditLog("charge.refunded_unmatched", { chargeId: charge.id });
    }
    return NextResponse.json({ received: true });
  }
```

Place it before the `checkout.session.completed` branch so it returns early. Confirm `updateJob` and `auditLog` are already imported in this file, and check the `Stripe` type import name matches what the file uses.

- [ ] **Step 3: Enable the event in Stripe**

The webhook endpoint must be subscribed to `charge.refunded` or the branch never fires. Check and add it in the Stripe dashboard under Developers → Webhooks, or verify with:

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && set -a; source <(grep -E "^STRIPE_SECRET_KEY=" .env.local); set +a
curl -s https://api.stripe.com/v1/webhook_endpoints -u "$STRIPE_SECRET_KEY:" | python3 -c "
import json,sys
for e in json.load(sys.stdin).get('data',[]):
    print(e['url']); print('  events:', e['enabled_events'])
"
```

If `charge.refunded` is absent, add it. **Without this the code is dead.**

- [ ] **Step 4: Typecheck and commit**

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && npm run typecheck && git add app/api/webhooks/stripe/route.ts && git commit -m "Mark jobs refunded from the charge.refunded webhook"
```

---

### Task 5: Payout report on /stats

**Files:**
- Modify: `app/api/admin/stats/route.ts`, `app/stats/StatsClient.tsx`

- [ ] **Step 1: Build the order list in the stats route**

`loadAcquisitionSince` already pages Stripe sessions for the acquisition panel. Extend it to also return partner orders rather than adding a second pass over Stripe. For each paid session with `amount_total > 0` and an `acquisition_partner`, emit a `PartnerOrder` using `metadata.jobId`, the customer email from the session, `amount_total`, the session's `created`, and the refunded flag from the matching job.

Look up refunds from the jobs already loaded in the handler (`listRecentJobs(30)`), not with a new query — Supabase egress is a live constraint.

Then:

```typescript
  const partnerRows = await listActivePartners();
  const partnerPayouts = computePartnerPayouts(partnerOrders, partnerRows, Date.now());
```

Add `listActivePartners()` to `lib/partners.ts` following the same Supabase-or-memory pattern, selecting `code, email, commission_percent` where `active`.

Add `partnerPayouts` to the JSON response.

- [ ] **Step 2: Render it**

In `app/stats/StatsClient.tsx`, add a section after the acquisition panel, matching the existing card markup:

```tsx
      {stats.partnerPayouts && stats.partnerPayouts.length > 0 && (
        <section className="rounded-2xl border border-stone-200 bg-white p-5 sm:p-6">
          <h2 className="text-lg font-semibold text-stone-900">Partner payouts due</h2>
          <p className="mt-1 text-sm text-stone-500">
            30% of what the client paid, first purchase only, past the 30-day refund hold.
          </p>
          <table className="mt-4 w-full text-sm">
            <thead>
              <tr className="text-left text-stone-500">
                <th className="py-1 font-medium">Partner</th>
                <th className="py-1 text-right font-medium">Payable</th>
                <th className="py-1 text-right font-medium">Due</th>
                <th className="py-1 text-right font-medium">Held</th>
                <th className="py-1 text-right font-medium">Refunded</th>
              </tr>
            </thead>
            <tbody>
              {stats.partnerPayouts.map((row) => (
                <tr key={row.partnerCode} className="border-t border-stone-100">
                  <td className="py-1.5 text-stone-900">{row.partnerCode}</td>
                  <td className="py-1.5 text-right text-stone-700">{row.orders}</td>
                  <td className="py-1.5 text-right font-medium text-stone-900">
                    ${(row.payoutCents / 100).toFixed(2)}
                  </td>
                  <td className="py-1.5 text-right text-stone-500">{row.heldOrders}</td>
                  <td className="py-1.5 text-right text-stone-500">{row.refundedOrders}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
```

Add the matching field to the component's stats type.

- [ ] **Step 3: Typecheck, build, commit**

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && npm run typecheck && npm run build && git add app/api/admin/stats/route.ts app/stats/StatsClient.tsx lib/partners.ts && git commit -m "Show partner payouts due on /stats"
```

---

### Task 6: The terms page and the CLI

**Files:**
- Create: `app/partners/page.tsx`, `scripts/add-partner.ts`

- [ ] **Step 1: Write the page**

A single static page stating the terms from `docs/partners/outreach-kit.md`: 30% of what the client pays, first purchase only, 60-day first-touch cookie, monthly PayPal, $25 minimum, 30-day hold, disclosure required, no self-referral. Close with "email <address> and I'll set up your link" — no signup form, because there is no volume to justify one.

Follow an existing static page such as `app/privacy/page.tsx` for layout, header and footer. Add `/partners` to `publicPaths` in `app/sitemap.ts`.

- [ ] **Step 2: Write the CLI**

`scripts/add-partner.ts` inserts a row, taking code, name, email, segment and the coupon id from argv or env, validating the code through `normalizePartnerCode` so an invalid code cannot be inserted.

- [ ] **Step 3: Build and commit**

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && npm run build && git add app/partners scripts/add-partner.ts app/sitemap.ts && git commit -m "Add the partners terms page and an add-partner script"
```

---

### Task 7: Suite, PR, deploy, verify

- [ ] **Step 1: Full check**

```bash
cd /Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio && npm run check
```

Expected: fully green. `origin/main` was green before this branch, so any failure is yours.

- [ ] **Step 2: PR, CI, merge**

Body should state that unknown partner codes still attribute and simply earn nothing, that the discount is server-applied and cannot be typed, that payouts require real money past a 30-day hold with self-referral excluded, and that the `charge.refunded` event had to be enabled in the Stripe dashboard.

- [ ] **Step 3: Verify on production with a real partner code**

Insert a test partner, then walk it:

```bash
S=https://www.headshot-generators.com
curl -s -D- -o /dev/null "$S/?partner=testcoach" | grep -i "set-cookie: hs_partner"
curl -s -o /dev/null -w "/partners -> %{http_code}\n" "$S/partners"
```

Then create a checkout session for a real unpaid job carrying that partner and confirm in Stripe that `amount_total` is 15% below list and the metadata has `acquisition_partner`. **Expire the session afterwards** rather than leaving it open.

Deactivate the test partner when done:

```sql
update public.partners set active = false where code = 'testcoach';
```

- [ ] **Step 4: Report**

State what passed with real output. Then stop: recruiting partners is founder work, and the outreach kit is ready.

---

## Self-review

**Spec coverage.** §4 M2 asks for the `/partners` page and terms (Task 6), the partner row (Task 1), the server-applied client discount (Task 3), the self-buy guard and payout report (Tasks 2 and 5), and the `charge.refunded` handler (Task 4). The partner kit and segment order live in `docs/partners/outreach-kit.md` rather than here, since they are founder work. Deliberately omitted: Rewardful or Dub integration, which the spec lists as a day-120 decision once the channel has proven itself.

**Placeholders.** None. Every code step carries its code, and steps whose line numbers could drift open with a `grep`.

**Type consistency.** `PartnerOrder` and `PartnerPayout` are defined once in `lib/partners.ts` and consumed unchanged by the stats route and the client type. `computePartnerPayouts` takes `Pick<Partner, "code" | "email" | "commissionPercent">`, which `listActivePartners` satisfies. `getActivePartner` returns `Partner | null` and every call site handles null, because an unknown code must still attribute.

**Risks worth naming.** Two. The `charge.refunded` event must be enabled on the Stripe endpoint or Task 4 is dead code that silently pays out refunded orders — Step 3 of that task is not optional. And the per-instance partner cache means deactivating a partner takes up to five minutes to stop the discount; that is the right trade against a Supabase read on every checkout, but it should be stated in the terms rather than discovered.
