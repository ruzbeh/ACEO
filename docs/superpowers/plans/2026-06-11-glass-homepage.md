# Glass Homepage Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restyle the headshot-generators.com homepage into dark aurora glassmorphism (frosted glass cards, aurora gradient background, glow CTAs) with zero copy/funnel/analytics changes.

**Architecture:** CSS-only design system layer in `globals.css` (glass tokens + utilities + aurora orbs + reveal animation), one server `AuroraBackground` component, one tiny client `Reveal` component, then mechanical className swaps across the 12 landing components. Spec: `docs/superpowers/specs/2026-06-11-glass-homepage-design.md` (Agentic Company repo).

**Tech Stack:** Next.js (App Router), Tailwind v4 (`@import "tailwindcss"` + `@theme inline`), no new dependencies.

**Working directory:** `/Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio` — ALL paths below are relative to this repo.

---

## Critical context for the engineer

1. **The repo working tree is DIRTY with unrelated in-progress work** (deal-lander: `app/deal/`, `lib/deal-pricing.ts`, modified `middleware.ts`, api routes, `ResultsPageClient.tsx`, `lib/store.ts`, `lib/types.ts`). NEVER run `git add -A` or `git add .`. Stage only the exact files named in each commit step. Do not touch the deal files.
2. **Do NOT `git push`.** Pushing to main auto-deploys to production via Vercel. Commits stay local; the founder triggers deploy.
3. **Hard invariants** (breaking any of these is a task failure):
   - Zero copy/text changes. Zero DOM-order changes — the `order-1`…`order-5` classes in `Hero.tsx` implement a mobile CTA-above-fold layout from a GA funnel audit; never alter them.
   - `TrackedCTALink` props `href`/`location`/`label`/`variant` are analytics — never alter.
   - All `variant === "women"` / `isWomen` ternaries and their inline `style={...}` objects stay byte-identical. Women branches of conditional classNames stay untouched unless a step explicitly says otherwise. Only DEFAULT branches get glass classes.
   - `priority`, `sizes`, `fill` props on `next/image` elements stay untouched (LCP).
   - Functional classes stay: `overflow-hidden`, `min-w-0`, `relative`, `z-*`, `group`, `order-*`, `sm:hidden`, `divide-y` mechanics, the FAQ `grid-rows-[1fr]/[0fr]` animation trick, the BeforeAfter `opacity-0` range input.
4. **Verification cadence:** `npm run build` at tasks 3, 9, 14 and final visual verification at task 15. This is visual work — the build is the regression gate; screenshots are the acceptance test. (No unit tests: there is no behavior change to test; the repo's test convention `npx tsx tests/...` covers logic, not styling.)
5. **Section-wrapper mapping rule** (used by many tasks): landing sections alternate two backgrounds today. Translate exactly:
   - `border-t border-border bg-background` → `border-t border-white/5 bg-transparent`
   - `border-t border-border bg-card` → `border-t border-white/5 bg-white/[0.02]`
   (Sections must become transparent/near-transparent so the page-level aurora shows through.)

---

### Task 1: Glass design system in globals.css

**Files:**
- Modify: `app/globals.css`

- [ ] **Step 1: Add glass tokens to `:root`**

In `app/globals.css`, inside the existing `:root` block, after the line `--radius: 0.75rem;`, add:

```css
  /* Glass design system tokens */
  --glass-bg: rgba(255, 255, 255, 0.05);
  --glass-bg-strong: rgba(255, 255, 255, 0.08);
  --glass-border: rgba(255, 255, 255, 0.1);
  --glass-highlight: inset 0 1px 0 rgba(255, 255, 255, 0.08);
```

- [ ] **Step 2: Replace the old `.glass` utility and add the glass/aurora/reveal CSS**

Replace this existing block:

```css
/* Subtle glass effect */
.glass {
  background: rgba(20, 20, 20, 0.8);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
}
```

with:

```css
/* Glass design system */
.glass {
  background: rgba(20, 20, 20, 0.8);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
}

.glass-card {
  background: var(--glass-bg);
  border: 1px solid var(--glass-border);
  border-radius: 1rem;
  box-shadow: var(--glass-highlight);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
}

.glass-pill {
  background: var(--glass-bg);
  border: 1px solid var(--glass-border);
  border-radius: 9999px;
  box-shadow: var(--glass-highlight);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
}

.glass-strong {
  background: var(--glass-bg-strong);
  border: 1px solid var(--glass-border);
  box-shadow: var(--glass-highlight);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
}

.glow-amber {
  box-shadow: 0 0 28px rgba(251, 191, 36, 0.35), inset 0 1px 0 rgba(255, 255, 255, 0.45);
}

@supports not (backdrop-filter: blur(1px)) {
  .glass-card, .glass-pill, .glass-strong {
    background: rgba(20, 20, 20, 0.9);
  }
}

/* Aurora background orbs (transform-only animation; GPU cheap) */
.aurora-orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(60px);
  will-change: transform;
  pointer-events: none;
}

.aurora-amber {
  background: radial-gradient(circle, rgba(251, 191, 36, 0.22) 0%, transparent 70%);
  animation: aurora-a 38s ease-in-out infinite alternate;
}

.aurora-violet {
  background: radial-gradient(circle, rgba(139, 92, 246, 0.18) 0%, transparent 70%);
  animation: aurora-b 46s ease-in-out infinite alternate;
}

.aurora-pink {
  background: radial-gradient(circle, rgba(244, 114, 182, 0.1) 0%, transparent 70%);
  animation: aurora-c 52s ease-in-out infinite alternate;
}

@keyframes aurora-a {
  from { transform: translate3d(0, 0, 0) scale(1); }
  to { transform: translate3d(60px, 40px, 0) scale(1.15); }
}

@keyframes aurora-b {
  from { transform: translate3d(0, 0, 0) scale(1.1); }
  to { transform: translate3d(-70px, 30px, 0) scale(0.95); }
}

@keyframes aurora-c {
  from { transform: translate3d(0, 0, 0) scale(1); }
  to { transform: translate3d(40px, -50px, 0) scale(1.2); }
}

/* Scroll reveal (class applied by Reveal.tsx only after hydration,
   so non-JS / pre-hydration users always see content) */
.reveal {
  opacity: 0;
  transform: translateY(24px);
  transition: opacity 0.7s ease, transform 0.7s ease;
}

.reveal-visible {
  opacity: 1;
  transform: none;
}

@media (prefers-reduced-motion: reduce) {
  .aurora-orb { animation: none; }
  .reveal { opacity: 1; transform: none; transition: none; }
}
```

- [ ] **Step 3: Upgrade `.text-gradient` to the amber→pink sweep**

Replace:

```css
.text-gradient {
  background: linear-gradient(135deg, #fbbf24, #f59e0b);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}
```

with:

```css
.text-gradient {
  background: linear-gradient(120deg, #fde68a, #fbbf24 45%, #f472b6 110%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}
```

(Used by the Hero h1 accent word. The women variant disables it via inline style — untouched.)

- [ ] **Step 4: Commit**

```bash
git add app/globals.css
git commit -m "feat(design): glass design system — tokens, glass utilities, aurora orbs, reveal animation"
```

---

### Task 2: AuroraBackground component + homepage mount

**Files:**
- Create: `components/landing/AuroraBackground.tsx`
- Modify: `app/page.tsx`

- [ ] **Step 1: Create `components/landing/AuroraBackground.tsx`** (server component, no directive):

```tsx
type AuroraBackgroundProps = {
  /** Local section accent (CTA/pricing) vs full-page layer */
  intense?: boolean;
};

export function AuroraBackground({ intense = false }: AuroraBackgroundProps) {
  if (intense) {
    return (
      <div aria-hidden="true" className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="aurora-orb aurora-amber left-[10%] top-[-160px] h-[480px] w-[480px]" />
        <div className="aurora-orb aurora-violet right-[5%] top-[20%] h-[420px] w-[420px]" />
      </div>
    );
  }
  return (
    <div aria-hidden="true" className="pointer-events-none absolute inset-0 overflow-hidden">
      <div className="aurora-orb aurora-amber left-[8%] top-[-180px] h-[540px] w-[540px]" />
      <div className="aurora-orb aurora-violet right-[2%] top-[-100px] h-[560px] w-[560px]" />
      <div className="aurora-orb aurora-pink left-[35%] top-[420px] h-[480px] w-[480px]" />
      <div className="aurora-orb aurora-violet left-[-120px] top-[38%] h-[440px] w-[440px] opacity-70" />
      <div className="aurora-orb aurora-amber right-[-100px] top-[72%] h-[460px] w-[460px] opacity-60" />
    </div>
  );
}
```

- [ ] **Step 2: Mount in `app/page.tsx`**

Add the import next to the other landing imports:

```tsx
import { AuroraBackground } from "@/components/landing/AuroraBackground";
```

Change the root div and insert the layer as its first child:

```tsx
    <div className="relative min-h-screen min-w-0 w-full max-w-full overflow-x-hidden bg-background">
      <AuroraBackground />
      <Header />
```

(was `<div className="min-h-screen min-w-0 w-full max-w-full overflow-x-hidden bg-background">` directly followed by `<Header />`). Later DOM siblings paint above the absolutely-positioned layer; no z-index changes needed. `Header` is `sticky z-50` already.

- [ ] **Step 3: Commit**

```bash
git add components/landing/AuroraBackground.tsx app/page.tsx
git commit -m "feat(landing): page-level aurora background layer"
```

---

### Task 3: Reveal client component

**Files:**
- Create: `components/landing/Reveal.tsx`

- [ ] **Step 1: Create `components/landing/Reveal.tsx`**

Design notes: the `reveal` (hidden) class is added ONLY client-side after mount, so server HTML is always visible (no blank page pre-hydration — this page takes paid mobile traffic). Elements already in the viewport at mount are never hidden. classList is used directly to avoid re-renders.

```tsx
"use client";

import { useEffect, useRef, type ReactNode } from "react";

type RevealProps = {
  children: ReactNode;
  className?: string;
};

export function Reveal({ children, className }: RevealProps) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    // Never hide content already on screen at hydration time.
    if (el.getBoundingClientRect().top < window.innerHeight) return;

    el.classList.add("reveal");
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          el.classList.add("reveal-visible");
          observer.disconnect();
        }
      },
      { threshold: 0.15 },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  return (
    <div ref={ref} className={className}>
      {children}
    </div>
  );
}
```

- [ ] **Step 2: Build checkpoint**

Run: `npm run build`
Expected: compiles with no errors (pre-existing warnings unrelated to these files are acceptable).

- [ ] **Step 3: Commit**

```bash
git add components/landing/Reveal.tsx
git commit -m "feat(landing): IntersectionObserver scroll-reveal component"
```

---

### Task 4: Hero restyle

**Files:**
- Modify: `components/landing/Hero.tsx`

All edits below touch ONLY default-variant class strings; every `isWomen`/`variant === "women"` branch and inline style stays byte-identical.

- [ ] **Step 1: Section wrapper transparent** (line ~21)

`relative min-w-0 overflow-hidden bg-background lg:min-h-[90vh]` → `relative min-w-0 overflow-hidden bg-transparent lg:min-h-[90vh]`

- [ ] **Step 2: Inline gradient orb — keep for women only** (lines ~22-33)

The page aurora replaces the default orb, but `/for/women` renders Hero WITHOUT the page aurora and needs its rose orb. Replace the whole orb block:

```tsx
      {/* Subtle gradient orb */}
      <div className="pointer-events-none absolute left-1/2 top-0 -translate-x-1/2 -translate-y-1/2">
        <div
          className={variant === "women"
            ? "h-[600px] w-[600px] rounded-full blur-[120px]"
            : "h-[600px] w-[600px] rounded-full bg-amber-500/10 blur-[120px]"}
          style={variant === "women" ? {
            background: "radial-gradient(circle, #d9c9cf 0%, transparent 70%)",
            opacity: 0.45,
          } : undefined}
        />
      </div>
```

with:

```tsx
      {/* Rose gradient orb — women variant only; default gets the page-level aurora */}
      {variant === "women" ? (
        <div className="pointer-events-none absolute left-1/2 top-0 -translate-x-1/2 -translate-y-1/2">
          <div
            className="h-[600px] w-[600px] rounded-full blur-[120px]"
            style={{
              background: "radial-gradient(circle, #d9c9cf 0%, transparent 70%)",
              opacity: 0.45,
            }}
          />
        </div>
      ) : null}
```

- [ ] **Step 3: Badge pill — default branch glass-green** (line ~52)

In the badge ternary, default branch only:
`order-1 mb-6 inline-flex self-center items-center gap-2 rounded-full border border-green-200 bg-green-50 px-4 py-2 lg:order-none lg:self-start` → `order-1 mb-6 inline-flex self-center items-center gap-2 rounded-full border border-green-500/25 bg-green-500/10 px-4 py-2 backdrop-blur-sm lg:order-none lg:self-start`

Badge text default branch (line ~75): `text-sm font-medium text-green-700` → `text-sm font-medium text-green-300`

- [ ] **Step 4: Value-stack box → glass card** (line ~101)

`order-5 mx-auto mt-8 max-w-md rounded-xl border border-border bg-card p-5 text-left lg:order-none lg:mx-0` → `order-5 glass-card mx-auto mt-8 max-w-md p-5 text-left lg:order-none lg:mx-0`

Inside it (line ~124): `mt-4 flex items-baseline justify-between border-t border-border pt-3` → `mt-4 flex items-baseline justify-between border-t border-white/10 pt-3`

- [ ] **Step 5: Primary CTA → gradient + glow** (line ~140, inside the template literal — default ternary branches only)

`bg-accent hover:bg-amber-400` → `bg-gradient-to-br from-amber-300 via-amber-400 to-amber-500 hover:brightness-110`

and in the same template literal the static `shadow-lg` → `glow-amber` (women's inline `boxShadow` overrides it, so the women look is unchanged).

- [ ] **Step 6: Before/after visuals** (lines ~176, ~191, ~205)

- Before-image frame: `aspect-[3/4] overflow-hidden rounded-2xl border border-border bg-card` → `aspect-[3/4] overflow-hidden rounded-2xl border border-white/10 bg-white/5`
- Arrow circle: `flex h-12 w-12 items-center justify-center rounded-full border border-border bg-card` → `glass-pill flex h-12 w-12 items-center justify-center`
- After-image frame: `aspect-[3/4] overflow-hidden rounded-2xl border border-accent/30 bg-card shadow-lg shadow-accent/10` → `aspect-[3/4] overflow-hidden rounded-2xl border border-accent/40 bg-white/5 shadow-[0_0_24px_rgba(251,191,36,0.18)]`

- [ ] **Step 7: Stats box + guarantee badge** (lines ~220, ~236-258)

- Stats box: `mt-6 rounded-xl border border-border bg-card/50 p-4` → `glass-card mt-6 p-4`
- Guarantee badge, default ternary branch only: `mt-4 flex items-center justify-center gap-2 rounded-lg border border-green-200 bg-green-50 p-3` → `mt-4 flex items-center justify-center gap-2 rounded-lg border border-green-500/25 bg-green-500/10 p-3 backdrop-blur-sm`
- Guarantee icon default branch: `h-5 w-5 text-green-600` → `h-5 w-5 text-green-400`
- Guarantee text default branch: `text-sm font-medium text-green-800` → `text-sm font-medium text-green-300`

- [ ] **Step 8: Commit**

```bash
git add components/landing/Hero.tsx
git commit -m "feat(landing): glass hero — pills, glass cards, gradient glow CTA"
```

---

### Task 5: Header — floating glass bar

**Files:**
- Modify: `components/landing/Header.tsx`

Header is shared by ~17 pages including light-mode ones (`isDark` ternary). Light branches keep their colors; only structure + dark branches change.

- [ ] **Step 1: Floating rounded glass bar** (lines ~34-36)

Replace the header template literal:

```tsx
sticky top-0 z-50 w-full min-w-0 max-w-full border-b backdrop-blur-xl ${
      isDark ? "border-border bg-background/80" : "border-neutral-200 bg-light-bg/80"
    }
```

with:

```tsx
sticky top-3 z-50 mx-auto w-[calc(100%-1.5rem)] min-w-0 max-w-6xl rounded-2xl border backdrop-blur-xl ${
      isDark ? "border-white/10 bg-white/[0.05] shadow-[inset_0_1px_0_rgba(255,255,255,0.08)]" : "border-neutral-200 bg-light-bg/80"
    }
```

(Keep everything else in the element — only the className changes.)

- [ ] **Step 2: Header CTA — dark default branch → amber gradient** (lines ~66-81)

In the non-women template literal, dark branch only:
`bg-primary text-primary-foreground hover:bg-neutral-200` → `bg-gradient-to-br from-amber-300 via-amber-400 to-amber-500 text-accent-foreground hover:brightness-110`

Light branch (`bg-neutral-900 text-neutral-50 hover:bg-neutral-800`) and the women branch + its inline style stay untouched. `location="header"`, `label={ctaLabel}`, conditional `href` stay untouched.

- [ ] **Step 3: Nav links** — no change (muted→foreground hover already reads well on glass).

- [ ] **Step 4: Commit**

```bash
git add components/landing/Header.tsx
git commit -m "feat(landing): floating glass header bar + gradient CTA"
```

---

### Task 6: SocialProof restyle

**Files:**
- Modify: `components/landing/SocialProof.tsx`

Preserve: `ref={sectionRef}` (fires `trackSocialProofViewed`), all `isWomen` star ternaries + `#d4a574` inline styles.

- [ ] **Step 1: Section wrapper** (line ~36): apply mapping rule → `min-w-0 border-t border-white/5 bg-white/[0.02] py-20 overflow-x-hidden`

- [ ] **Step 2: Stats-bar dividers** (lines ~53 and ~73 — identical string, replace BOTH): `h-12 w-px bg-border hidden sm:block` → `h-12 w-px bg-white/10 hidden sm:block`

- [ ] **Step 3: Testimonial cards** (line ~83):

`group min-w-0 rounded-2xl border border-border bg-background p-5 transition-all hover:border-accent/50 hover:shadow-lg hover:shadow-accent/5` → `group min-w-0 glass-card p-5 transition-all hover:border-accent/50 hover:shadow-lg hover:shadow-accent/5`

- [ ] **Step 4: Avatar circle → gradient** (lines ~85-87):

`flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full bg-accent text-xs font-bold text-accent-foreground` → `flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-amber-300 to-amber-500 text-xs font-bold text-accent-foreground`

- [ ] **Step 5: Commit**

```bash
git add components/landing/SocialProof.tsx
git commit -m "feat(landing): glass social-proof cards"
```

---

### Task 7: ExampleStyles restyle

**Files:**
- Modify: `components/landing/ExampleStyles.tsx`

Preserve: h2 inline style ternary (women typography), `key={label}`, `group` class (drives image zoom + overlay), `next/image` props.

- [ ] **Step 1: Section wrapper** (line ~9): mapping rule → `min-w-0 border-t border-white/5 bg-transparent py-20 overflow-x-hidden`

- [ ] **Step 2: Style cards — glass frame + hover lift** (lines ~30-33):

`group relative min-w-0 shrink-0 overflow-hidden rounded-2xl border border-border bg-card transition-all duration-300 hover:border-accent/50 hover:shadow-xl hover:shadow-accent/5 w-40 sm:w-44` → `group relative min-w-0 shrink-0 overflow-hidden rounded-2xl border border-white/10 bg-white/[0.04] backdrop-blur-sm transition-all duration-300 hover:-translate-y-1 hover:border-accent/50 hover:shadow-xl hover:shadow-accent/5 w-40 sm:w-44`

- [ ] **Step 3: Commit**

```bash
git add components/landing/ExampleStyles.tsx
git commit -m "feat(landing): glass example-style cards with hover lift"
```

---

### Task 8: BeforeAfter restyle

**Files:**
- Modify: `components/landing/BeforeAfter.tsx`

Preserve: `clipPath` inline style, slider `left/transform` inline style, the invisible `opacity-0` range input (do NOT style it), `onClick` handlers, `aria-*` props, active-thumbnail ternary structure.

- [ ] **Step 1: Section wrapper** (top of component): apply the mapping rule for whichever of the two section strings it carries.

- [ ] **Step 2: Comparison frame** (line ~59):

`relative aspect-[4/5] overflow-hidden rounded-2xl border border-border bg-secondary` → `relative aspect-[4/5] overflow-hidden rounded-2xl border border-white/10 bg-white/5`

- [ ] **Step 3: Slider handle** (line ~90):

`flex h-12 w-12 items-center justify-center rounded-full border-2 border-white bg-background shadow-xl` → `flex h-12 w-12 items-center justify-center rounded-full border-2 border-white/80 bg-black/40 shadow-xl backdrop-blur`

- [ ] **Step 4: Overlay label badges** (lines ~110-115):

- Before: `absolute left-4 top-4 rounded-full bg-background/80 px-3 py-1 text-xs font-medium text-foreground backdrop-blur` → `absolute left-4 top-4 rounded-full border border-white/10 bg-black/50 px-3 py-1 text-xs font-medium text-foreground backdrop-blur`
- After: `absolute right-4 top-4 rounded-full bg-accent/90 px-3 py-1 text-xs font-medium text-accent-foreground backdrop-blur` → unchanged (accent pill already reads as glass over imagery).

- [ ] **Step 5: Thumbnail buttons — inactive ternary branch only** (lines ~134-153):

`border-border hover:border-accent/50` → `border-white/10 hover:border-accent/50` (active branch `border-accent shadow-lg` unchanged).

- [ ] **Step 6: Commit**

```bash
git add components/landing/BeforeAfter.tsx
git commit -m "feat(landing): glass before/after comparison"
```

---

### Task 9: HowItWorks restyle

**Files:**
- Modify: `components/landing/HowItWorks.tsx`

Preserve: `group`/`relative` on step wrappers, `z-10` on icon tiles, connector conditional render.

- [ ] **Step 1: Section wrapper** (line ~47): mapping rule → `min-w-0 border-t border-white/5 bg-transparent py-20 overflow-x-hidden`

- [ ] **Step 2: Connector line** (line ~66):

`absolute left-1/2 top-6 hidden h-px w-full bg-gradient-to-r from-border via-accent/30 to-border sm:block` → `absolute left-1/2 top-6 hidden h-px w-full bg-gradient-to-r from-white/10 via-accent/40 to-white/10 sm:block`

- [ ] **Step 3: Icon tiles → glass** (lines ~70-72):

`relative z-10 flex h-14 w-14 items-center justify-center rounded-2xl border border-border bg-card text-accent transition-all duration-300 group-hover:border-accent group-hover:shadow-lg group-hover:shadow-accent/10` → `glass-card relative z-10 flex h-14 w-14 items-center justify-center text-accent transition-all duration-300 group-hover:border-accent group-hover:shadow-lg group-hover:shadow-accent/10`

- [ ] **Step 4: Step number pill → gradient badge** (lines ~74-76):

`mt-6 inline-flex items-center justify-center rounded-full border border-border bg-card px-4 py-1.5 text-xs font-semibold text-muted-foreground` → `mt-6 inline-flex items-center justify-center rounded-full border border-amber-400/30 bg-gradient-to-r from-amber-400/15 to-pink-400/10 px-4 py-1.5 text-xs font-semibold text-amber-200`

- [ ] **Step 5: Build checkpoint**

Run: `npm run build`
Expected: compiles clean.

- [ ] **Step 6: Commit**

```bash
git add components/landing/HowItWorks.tsx
git commit -m "feat(landing): glass how-it-works steps with gradient badges"
```

---

### Task 10: TrustBadges restyle

**Files:**
- Modify: `components/landing/TrustBadges.tsx`

- [ ] **Step 1: Section wrapper** (line ~43): mapping rule → `min-w-0 border-t border-white/5 bg-white/[0.02] py-16 overflow-x-hidden`

- [ ] **Step 2: Badge cards** (lines ~51-59):

`flex flex-col items-center gap-4 rounded-2xl border border-border bg-background p-6 text-center transition-all hover:border-accent/50` → `glass-card flex flex-col items-center gap-4 p-6 text-center transition-all hover:border-accent/50`

- [ ] **Step 3: Inner icon tiles** (lines ~55-57):

`flex h-12 w-12 items-center justify-center rounded-xl border border-border bg-card text-accent` → `flex h-12 w-12 items-center justify-center rounded-xl border border-white/10 bg-white/5 text-accent`

(No `backdrop-filter` — nested inside `.glass-card`; the no-nested-blur rule.)

- [ ] **Step 4: Commit**

```bash
git add components/landing/TrustBadges.tsx
git commit -m "feat(landing): glass trust badges"
```

---

### Task 11: FAQ restyle

**Files:**
- Modify: `components/landing/FAQ.tsx`

Preserve: `id="faq"`, `onClick` toggle, `rotate-180` in the open chevron branch, the `grid-rows-[1fr]/[0fr]` + `overflow-hidden` animation mechanics, `WOMEN_FAQS` content swap.

- [ ] **Step 1: Section wrapper** (line ~75): mapping rule → `min-w-0 border-t border-white/5 bg-transparent py-20 overflow-x-hidden`

- [ ] **Step 2: Accordion container → glass** (line ~86):

`mt-12 divide-y divide-border rounded-2xl border border-border bg-card` → `glass-card mt-12 divide-y divide-white/10 overflow-hidden`

(`overflow-hidden` added so the row hover tint clips to the rounded corners.)

- [ ] **Step 3: Trigger row hover** (lines ~89-93):

`flex w-full items-center justify-between gap-4 px-6 py-5 text-left transition-colors hover:bg-secondary/50` → `flex w-full items-center justify-between gap-4 px-6 py-5 text-left transition-colors hover:bg-white/[0.04]`

- [ ] **Step 4: Chevron circle — closed ternary branch only** (lines ~95-99):

closed branch `border-border bg-card text-muted-foreground` → `border-white/10 bg-white/5 text-muted-foreground` (open branch `border-accent bg-accent text-accent-foreground rotate-180` unchanged).

- [ ] **Step 5: Commit**

```bash
git add components/landing/FAQ.tsx
git commit -m "feat(landing): glass FAQ accordion"
```

---

### Task 12: CTA / pricing section restyle

**Files:**
- Modify: `components/landing/CTA.tsx`

Highest-risk file: dense `isWomen` ternaries with inline mauve styles. Touch ONLY the strings named below; every `style={isWomen ? ... : undefined}` stays byte-identical. Preserve `id="pricing"` and all `TrackedCTALink` props (`location={`cta_${name.toLowerCase()}`}` etc.).

- [ ] **Step 1: Section wrapper + local intense aurora** (line ~55)

- Import at top: `import { AuroraBackground } from "./AuroraBackground";`
- Section: `min-w-0 border-t border-border bg-card py-20 overflow-x-hidden` → `relative min-w-0 border-t border-white/5 bg-white/[0.02] py-20 overflow-x-hidden`
- Insert `<AuroraBackground intense />` immediately after the `<section ...>` opening tag.
- Inner container div (line ~56) `mx-auto min-w-0 max-w-6xl px-4 sm:px-6` → `relative mx-auto min-w-0 max-w-6xl px-4 sm:px-6` (content above the orbs).

- [ ] **Step 2: Pricing tier cards — both `popular` ternary branches** (lines ~77-81)

- popular: `border-accent bg-accent/5 shadow-lg shadow-accent/10 scale-[1.02]` → `border-amber-400/50 bg-white/[0.06] backdrop-blur-md shadow-[0_0_40px_rgba(251,191,36,0.15)] scale-[1.02]`
- non-popular: `border-border bg-background hover:border-accent/50` → `border-white/10 bg-white/[0.03] backdrop-blur-md hover:border-accent/50`

- [ ] **Step 3: "Most Popular" badge** (lines ~85-87):

`rounded-full bg-accent px-3 py-1 text-xs font-semibold text-accent-foreground` → `rounded-full bg-gradient-to-r from-amber-300 to-amber-500 px-3 py-1 text-xs font-semibold text-accent-foreground`

- [ ] **Step 4: Tier CTA — default-variant popular branch only** (lines ~122-130):

`bg-accent text-accent-foreground hover:bg-amber-400 shadow-md` → `bg-gradient-to-br from-amber-300 via-amber-400 to-amber-500 text-accent-foreground hover:brightness-110 glow-amber`

(non-popular `bg-primary text-primary-foreground hover:bg-neutral-200` stays — white secondary CTA gives hierarchy; women branch untouched.)

- [ ] **Step 5: Guarantee card — default branch only** (lines ~141-170):

- card: `mx-auto mt-12 max-w-2xl rounded-2xl border-2 border-green-200 bg-green-50 p-6 text-center sm:p-8` → `mx-auto mt-12 max-w-2xl rounded-2xl border border-green-500/25 bg-green-500/10 p-6 text-center backdrop-blur-sm sm:p-8`
- shield icon: `h-10 w-10 text-green-600` → `h-10 w-10 text-green-400`
- h3: `mt-3 text-xl font-semibold text-green-900` → `mt-3 text-xl font-semibold text-green-200`
- body: `mt-2 text-green-800` → `mt-2 text-green-300/90`
- trust strip icons (line ~181): `h-4 w-4 shrink-0 text-green-500` → `h-4 w-4 shrink-0 text-green-400`

(The `border-2`→`border` change applies only inside the default branch string; the women branch keeps `border-2` and its inline rose colors.)

- [ ] **Step 6: Commit**

```bash
git add components/landing/CTA.tsx
git commit -m "feat(landing): glass pricing cards + intensified aurora CTA section"
```

---

### Task 13: FindMyHeadshots restyle

**Files:**
- Modify: `components/landing/FindMyHeadshots.tsx`

Preserve: form logic, `role="alert"`, `disabled={loading}`, women button branch + inline style.

- [ ] **Step 1: Section wrapper** (line ~52): mapping rule → `min-w-0 border-t border-white/5 bg-white/[0.02] py-16 overflow-x-hidden`

- [ ] **Step 2: Icon tile** (lines ~55-59): `flex h-12 w-12 items-center justify-center rounded-xl border border-border bg-background` → `flex h-12 w-12 items-center justify-center rounded-xl border border-white/10 bg-white/5`

- [ ] **Step 3: Email input → glass** (lines ~68-75):

`rounded-xl border border-border bg-background px-4 py-3 text-foreground placeholder:text-muted-foreground focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/20 transition-all sm:min-w-[280px]` → `rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-foreground backdrop-blur-sm placeholder:text-muted-foreground focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/20 transition-all sm:min-w-[280px]`

- [ ] **Step 4: Submit button** — no change (white `bg-primary` secondary CTA; women branch untouched).

- [ ] **Step 5: Commit**

```bash
git add components/landing/FindMyHeadshots.tsx
git commit -m "feat(landing): glass find-my-headshots form"
```

---

### Task 14: Footer + StickyMobileCTA restyle

**Files:**
- Modify: `components/landing/Footer.tsx`
- Modify: `components/landing/StickyMobileCTA.tsx`

- [ ] **Step 1: Footer — gradient hairline + transparent bg** (line ~13)

`min-w-0 border-t border-border bg-background py-16 overflow-x-hidden` → `min-w-0 bg-transparent py-16 overflow-x-hidden`

and insert as the FIRST child inside `<footer>` (before the existing container div):

```tsx
      <div aria-hidden="true" className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-amber-400/30 to-transparent" />
```

For the absolute hairline to anchor, the footer className also needs `relative`: final string `relative min-w-0 bg-transparent py-16 overflow-x-hidden`.

- [ ] **Step 2: Footer logo tile** (lines ~19-23): `flex h-8 w-8 items-center justify-center rounded-lg bg-accent` → `flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-amber-300 to-amber-500`

- [ ] **Step 3: Footer legal bar** (lines ~98-105): `mt-12 flex flex-col items-center justify-between gap-4 border-t border-border pt-8 sm:flex-row` → `mt-12 flex flex-col items-center justify-between gap-4 border-t border-white/10 pt-8 sm:flex-row`

(The 9 nav links keep `text-muted-foreground hover:text-foreground` — already correct on glass.)

- [ ] **Step 4: StickyMobileCTA — glass bar** (line ~28)

`fixed bottom-0 left-0 right-0 z-50 border-t border-border bg-background/95 px-4 py-4 backdrop-blur-xl sm:hidden` → `fixed bottom-0 left-0 right-0 z-50 border-t border-white/10 bg-[#0a0a0a]/75 px-4 py-4 backdrop-blur-xl sm:hidden`

- [ ] **Step 5: StickyMobileCTA — default CTA branch → gradient glow** (lines ~33-37, default ternary branch ONLY)

`flex w-full items-center justify-center gap-2 rounded-full bg-primary px-6 py-3.5 text-center text-sm font-semibold text-primary-foreground shadow-lg transition-all hover:bg-neutral-200 active:scale-[0.98]` → `flex w-full items-center justify-center gap-2 rounded-full bg-gradient-to-br from-amber-300 via-amber-400 to-amber-500 px-6 py-3.5 text-center text-sm font-semibold text-accent-foreground glow-amber transition-all hover:brightness-110 active:scale-[0.98]`

(Women branch + `{ background: "#8b6b7a", color: "#fff" }` inline style untouched. `location="sticky_mobile_cta"`, `label="Try it free"`, conditional href untouched.)

- [ ] **Step 6: StickyMobileCTA microcopy** (line ~45): `mt-1 text-center text-xs text-stone-400` → `mt-1 text-center text-xs text-muted-foreground`

- [ ] **Step 7: Build checkpoint**

Run: `npm run build`
Expected: compiles clean.

- [ ] **Step 8: Commit**

```bash
git add components/landing/Footer.tsx components/landing/StickyMobileCTA.tsx
git commit -m "feat(landing): glass footer + sticky mobile CTA"
```

---

### Task 15: Reveal wiring + final visual verification

**Files:**
- Modify: `app/page.tsx`

- [ ] **Step 1: Wrap below-fold sections in `<Reveal>`**

Add import: `import { Reveal } from "@/components/landing/Reveal";`

In the JSX, wrap each below-fold section — preserving the flag conditionals EXACTLY:

```tsx
      <main className="min-w-0 w-full max-w-full overflow-x-hidden">
        <Hero ctaVariant={heroCtaVariant} />
        {proofAboveFold ? <SocialProof position="above_fold" /> : null}
        <Reveal><ExampleStyles /></Reveal>
        <Reveal><BeforeAfter /></Reveal>
        {proofAboveFold ? null : (
          <Reveal>
            <SocialProof position="below_styles" />
          </Reveal>
        )}
        <Reveal><HowItWorks /></Reveal>
        <Reveal><TrustBadges /></Reveal>
        <Reveal><FAQ /></Reveal>
        <Reveal><CTA /></Reveal>
        <Reveal><FindMyHeadshots /></Reveal>
      </main>
```

Hero and the above-fold SocialProof are NOT wrapped (LCP / above-fold content must never start hidden).

- [ ] **Step 2: Full build**

Run: `npm run build`
Expected: compiles clean.

- [ ] **Step 3: Visual verification (dev server + browser screenshots)**

Run `npm run dev`, then screenshot and CHECK each:

| Page | Width | Checks |
|---|---|---|
| `/` | 1280px | aurora visible through sections; glass cards render (not opaque gray); header floats rounded; headline gradient amber→pink; CTA glows; FAQ opens/closes; slider drags |
| `/` | 390px | CTA above fold; sticky bottom glass bar; no horizontal scroll; reveal animates on scroll |
| `/for/women` | 390px | rose palette intact (mauve #8b6b7a buttons, rose orb, #f5e8ed guarantee); NO amber gradient bleed into women elements |
| `/lp` | 390px | glass Header/Footer/FAQ blend with its bespoke hero; nothing broken |
| `/blog` (or `/terms`) | 1280px | floating header looks right on a non-landing page |

If any check fails: fix in the relevant component, re-screenshot, only then proceed.

- [ ] **Step 4: Commit**

```bash
git add app/page.tsx
git commit -m "feat(landing): scroll-reveal below-fold sections"
```

- [ ] **Step 5: STOP — do not push.** Report screenshots to the founder. Push to main (= production deploy via Vercel) only on their explicit go. Post-deploy canary: landing→upload-started rate in the daily report (baseline ~35.3%).
