# PRD: M3 — Rapid App Factory

**Status:** Draft
**Author:** AECO System Analysis
**Date:** 2026-03-21
**Goal:** Make AECO a 10x productivity machine for shipping small SaaS apps (like Headshot AI) in hours, not weeks.

---

## Problem Statement

AECO has 55 agents, 16 tool modules, full orchestration loops, and can plan/code/deploy/evaluate. But when you say **"build me Headshot AI"**, too much is left to the agents to figure out from scratch:

- No project templates → agents waste 40% of tokens reinventing boilerplate
- No auth tooling → every SaaS needs login, and agents can't wire it
- No email/notification tools → can't do password reset, onboarding emails, alerts
- No CI/CD generation → manual setup after every deploy
- No "small app" fast path → the full initiative flow (PM → Architect → Task Planner → Execute → Evaluate) is overkill for a 5-page SaaS
- No reusable patterns → lessons from Headshot AI don't accelerate the next app

**The gap isn't capability — it's speed. AECO can build anything, but it builds everything from zero.**

---

## Success Metrics

| Metric | Current | Target |
|--------|---------|--------|
| Time from "build X" to deployed MVP | ~4-8 hours | <1 hour |
| Token spend per small app MVP | ~$15-30 | <$5 |
| % of tasks requiring human intervention | ~30-40% | <5% |
| Agent idle time (waiting on missing tools) | High | Near-zero |

---

## What's Missing (Prioritized)

### P0 — Critical (blocks autonomous small app shipping)

#### 1. Project Scaffolder Tool (`scaffold_tools.py`)
**Why:** Every small SaaS has the same bones. Agents shouldn't reinvent them.

```
scaffold_project(
    name="headshot-ai",
    stack="nextjs-stripe-supabase",  # or "fastapi-react-postgres"
    features=["auth", "payments", "file-upload", "admin-dashboard"],
) → creates full project skeleton with:
    - Next.js app with Tailwind + shadcn/ui
    - Supabase auth (email + Google OAuth) pre-wired
    - Stripe checkout + webhook handler
    - Database schema (users, subscriptions, uploads)
    - API routes (CRUD + auth middleware)
    - Landing page template
    - .env.example with all required keys
    - Dockerfile + docker-compose.yml
    - GitHub Actions CI/CD (test + deploy)
    - Vercel/Railway deploy config
```

**Templates to ship with:**
- `nextjs-stripe-supabase` — Most common small SaaS stack
- `fastapi-react-postgres` — Python-heavy apps
- `landing-page-only` — Marketing/waitlist pages

**Effort:** 2-3 days
**Impact:** Eliminates 60-70% of boilerplate token spend

#### 2. Auth Tools (`auth_tools.py`)
**Why:** Every SaaS needs auth. Currently a hard stop that requires manual work.

```python
auth_setup_supabase(project_url, anon_key)  # Configure Supabase auth
auth_add_provider(provider="google")         # Add OAuth provider
auth_generate_middleware()                    # Create auth middleware files
auth_create_protected_route(path="/dashboard")
```

**Scope:** Supabase Auth (free tier, handles email + OAuth + magic links). Not rolling our own — that's insane for small apps.

**Effort:** 1-2 days
**Impact:** Removes the #1 blocker for SaaS shipping

#### 3. Fast App Workflow (`fast_app_graph.py`)
**Why:** The full initiative pipeline (7 nodes, 3 iterations) is overkill for "build me a headshot generator." Need a compressed 3-node flow.

```
fast_app_intake → scaffold + code → deploy + verify
```

**Node 1: Fast App Intake**
- User says "build me X with Y features"
- Workspace scanner checks if project exists
- If new: scaffold from template
- If existing: scan and understand

**Node 2: Scaffold + Code (parallel)**
- Run scaffolder tool if new project
- Assign coding tasks to engineers (max 3 concurrent)
- QA check with 1 retry
- No PM spec, no architect design — just build

**Node 3: Deploy + Verify**
- Deploy to Vercel/Railway
- Smoke test (load homepage, check API health)
- Return deployed URL + summary

**Trigger:** `POST /api/fast-app` or detect "build me [app]" in initiative goal

**Effort:** 2 days
**Impact:** 10x speed for small apps; full initiative flow remains for complex ones

#### 4. Email/Notification Tools (`email_tools.py`)
**Why:** Can't do password reset, welcome emails, or alerts without email.

```python
email_send(to, subject, body, html=True)          # Resend API (free 3k/month)
email_send_template(to, template="welcome", vars={})
email_setup_resend(api_key)                        # Configure provider
```

**Scope:** Resend (simplest API, free tier, works in 5 min). Template system: agents write HTML templates, tool sends them.

**Effort:** 1 day
**Impact:** Enables transactional email for every app

---

### P1 — High Value (significant productivity gains)

#### 5. CI/CD Generator
**Why:** After deploy, there's no automated pipeline. Every push requires manual deploy.

**Implementation:** Add to scaffolder templates:
```yaml
# .github/workflows/ci.yml (generated)
- on push to main: run tests → deploy to Vercel
- on PR: run tests → deploy preview
```

Plus a tool:
```python
cicd_generate(provider="github-actions", deploy_target="vercel")
```

**Effort:** 1 day (it's just file generation)
**Impact:** Continuous deployment from day 1

#### 6. Component Library / Pattern Registry
**Why:** Agents rebuild the same UI patterns (pricing table, hero section, auth form, dashboard layout) every time.

**Implementation:** A `patterns/` directory with pre-built, copy-paste-ready components:
```
patterns/
  ui/
    pricing-table.tsx      # 3-tier pricing with Stripe checkout
    hero-section.tsx       # Landing page hero with CTA
    auth-form.tsx          # Login/signup with Supabase
    dashboard-layout.tsx   # Sidebar + main content
    file-upload.tsx        # Drag-and-drop with preview
    image-gallery.tsx      # Grid with lightbox
  api/
    stripe-webhook.ts      # Webhook handler boilerplate
    supabase-middleware.ts  # Auth middleware
    file-upload-api.ts     # S3/Supabase storage upload
  db/
    user-schema.sql        # Users + subscriptions
    saas-schema.sql        # Full SaaS starter schema
```

Tool:
```python
pattern_use(name="pricing-table", target_path="src/components/PricingTable.tsx", vars={"plans": [...]})
```

**Effort:** 3-4 days (building the pattern library)
**Impact:** Agents copy + customize instead of writing from scratch. ~50% fewer tokens per UI task.

#### 7. Environment Provisioner (`env_tools.py`)
**Why:** After scaffolding, agents can't create the actual Supabase project, Stripe product, or Vercel project.

```python
env_provision_supabase(project_name)  # Create Supabase project via API
env_provision_stripe_product(name, price)  # Create Stripe product + price
env_provision_vercel(project_name, framework="nextjs")  # Create Vercel project
env_write_secrets(path=".env.local", vars={"SUPABASE_URL": "..."})
```

**Effort:** 2-3 days
**Impact:** Zero-touch from "build X" to running infra. Currently requires manual setup of every service.

---

### P2 — Nice to Have (polish & scale)

#### 8. Smoke Test Tool (`smoke_tools.py`)
**Why:** After deploy, no automated verification that the app actually works.

```python
smoke_test_url(url, checks=["status_200", "has_text('Sign Up')", "screenshot"])
smoke_test_api(base_url, endpoints=[{"path": "/api/health", "expect_status": 200}])
```

**Effort:** 1 day
**Impact:** Catch deploy failures before calling it "shipped"

#### 9. App Analytics Injection
**Why:** Every shipped app should auto-report metrics back to AECO's telemetry.

**Implementation:** Scaffolder injects a tiny analytics snippet:
```js
// Auto-injected by AECO scaffolder
fetch('/api/telemetry', { method: 'POST', body: JSON.stringify({
  event: 'page_view', page: window.location.pathname, ts: Date.now()
})})
```

Plus a telemetry API route that forwards to AECO's `telemetry_ingest()`.

**Effort:** 0.5 days
**Impact:** Evaluator gets real user data automatically. Closes the measure → iterate loop.

#### 10. Multi-App Portfolio Dashboard
**Why:** When AECO manages 3-5 small apps, need a single view of all deployments, metrics, spend.

**Implementation:** Extend existing dashboard with:
- App registry (name, URL, stack, status, MRR)
- Cross-app metrics comparison
- Aggregated spend by app

**Effort:** 2 days
**Impact:** Founder can see entire portfolio at a glance

---

## Implementation Order

```
Week 1:  Scaffolder (P0.1) + Auth Tools (P0.2) + Email Tools (P0.4)
Week 2:  Fast App Workflow (P0.3) + CI/CD Generator (P1.5) + Smoke Test (P2.8)
Week 3:  Component Library (P1.6) + Env Provisioner (P1.7)
Week 4:  Analytics Injection (P2.9) + Portfolio Dashboard (P2.10) + Integration testing
```

**Total: ~4 weeks to go from "AECO can build things" to "AECO ships SaaS apps in under an hour."**

---

## Example: Headshot AI in the New World

```
User: "Build Headshot AI — AI headshot generator, $29/pack of 10, Facebook ads funnel,
       Stripe payments, Supabase auth, file upload to S3."

AECO (Fast App Flow):
  1. scaffold_project("headshot-ai", "nextjs-stripe-supabase",
       features=["auth", "payments", "file-upload"]) .............. 10 sec
  2. Pattern: pricing-table (1 plan, $29) ......................... 5 sec
  3. Pattern: file-upload (drag-and-drop, max 10 photos) .......... 5 sec
  4. Frontend engineer: build upload → generation flow ............. 8 min
  5. Backend engineer: wire Replicate API for AI headshots ......... 5 min
  6. Frontend engineer: results gallery + download ................. 5 min
  7. QA check → pass ............................................. 2 min
  8. deploy_production() → https://headshot-ai.vercel.app ......... 30 sec
  9. smoke_test_url() → all green ................................ 10 sec
  10. Facebook Ads agent: create campaign ($20/day, lookalike) ..... 3 min

Total: ~25 minutes, ~$2 in tokens
Deployed, with auth, payments, and ads running.
```

---

## What This PRD Does NOT Cover

- **AI model hosting** (Replicate/Modal/RunPod) — agents call external APIs, we don't host models
- **Custom domain setup** — manual DNS; could automate later via Cloudflare API
- **Legal/compliance** (terms of service, privacy policy) — agents can generate drafts but legal review is human
- **Customer support** — out of scope for now; could add Intercom/Crisp integration later

---

## Decision

This PRD fills the gap between "AECO has all the pieces" and "AECO ships products fast." The 55 agents are the workforce. This PRD gives them the **factory floor** — templates, tools, and workflows optimized for the most common case: small SaaS apps.

Without this: AECO is a talented team with no office.
With this: AECO is a production line.
