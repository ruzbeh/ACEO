# Glass Homepage Redesign — Aurora Glassmorphism

**Date:** 2026-06-11 · **Status:** approved (founder, in-session) · **Repo:** headshot-studio

## Concept

Full visual-layer redesign of the headshot-generators.com homepage in a dark
"aurora glass" language: deep near-black base, an amber/violet/pink gradient-mesh
aurora background, frosted-glass cards with hairline white borders and inset top
highlights, a gradient-glow primary CTA, and an amber→pink gradient headline accent.
Mockup approved in-session. **Visual layer only** — no copy, structure, or funnel
changes.

## Approach (approved: A — CSS-only)

No new dependencies. Everything is CSS tokens/utilities plus one tiny
IntersectionObserver client component for scroll reveals. Rejected alternatives:
framer-motion (~30kb on a paid-traffic conversion page) and WebGL shader aurora
(mobile battery/perf cost).

## Design system layer (`app/globals.css`)

- **Glass tokens:** `--glass-bg: rgba(255,255,255,0.05)`,
  `--glass-bg-strong: rgba(255,255,255,0.08)`, `--glass-border: rgba(255,255,255,0.10)`,
  inset highlight `inset 0 1px 0 rgba(255,255,255,0.08)`.
- **Utilities:** `.glass-card` (bg + border + `backdrop-filter: blur(14px)` + inset
  highlight + 16px radius), `.glass-pill` (badge/chip variant), `.glass-strong`
  (header/sticky-bar variant, higher alpha + more blur), `.glow-amber`
  (`0 0 28px rgba(251,191,36,0.35)`).
- **`.text-gradient` upgrade:** amber→pink sweep
  (`linear-gradient(120deg, #fde68a, #fbbf24 45%, #f472b6 110%)`).
- **Aurora background:** one absolutely-positioned page-level layer
  (`pointer-events-none`) behind all sections — three radial-gradient orbs
  (amber ~0.22α, violet ~0.18α, pink ~0.10α) with large blur, drifting via
  slow transform-only keyframes (30–45s). Replaces the Hero's single inline orb.
- **Performance/fallback rules:** `backdrop-filter` only on top-level cards, never
  nested; `prefers-reduced-motion: reduce` → static aurora, no reveal animation;
  `@supports not (backdrop-filter: blur(1px))` → solid `rgba(20,20,20,0.9)` card
  background.

## Motion (`components/landing/Reveal.tsx`)

New ~30-line `"use client"` component: IntersectionObserver (threshold ~0.15,
fire once), toggles a class driving an opacity/translateY CSS transition.
Sections stay server components; Reveal wraps section content as a client leaf.
Hero content is NOT wrapped (LCP must not start hidden).

## Per-section treatment

| Component | Change |
|---|---|
| `Header.tsx` | Sticky floating rounded glass bar (`.glass-strong`), replaces full-width border line |
| `Hero.tsx` | Inline orb removed (page aurora instead); badge → glass pill; value-stack box, stats box, guarantee badge → `.glass-card`; CTA → amber gradient pill + `.glow-amber` + inset highlight; after-image card gets amber border glow |
| `SocialProof.tsx` | Testimonial cards → `.glass-card`; avatar rings get gradient border |
| `ExampleStyles.tsx` | Style chips → glass pills; image grid gets glass frames + hover lift |
| `BeforeAfter.tsx` | Comparison cards in glass frames |
| `HowItWorks.tsx` | Step cards → `.glass-card` with gradient number badges |
| `TrustBadges.tsx` | Glass strip |
| `FAQ.tsx` | Accordion items → glass (white/5 bg, white/10 border) |
| `CTA.tsx` | Full glass panel, locally intensified aurora, large glow CTA |
| `FindMyHeadshots.tsx` | Glass input + card |
| `Footer.tsx` | Transparent over faint aurora, gradient hairline top border |
| `StickyMobileCTA.tsx` | `.glass-strong` bar + glow CTA; same size/position |
| `app/page.tsx` | Mounts the aurora background layer |

## Invariants (hard)

- Zero copy changes. Zero DOM-order changes (mobile CTA `order-*` from the
  2026-05-18 GA audit stays exactly as-is).
- `TrackedCTALink` analytics props, `heroCta`/`socialProofAboveFold` flag logic,
  `SocialProofCounter` untouched.
- `variant="women"` inline style overrides keep working (inline styles beat
  utility classes; glass surfaces are neutral white-alpha). `/for/women` must
  remain readable and on its rose palette.
- Hero image `priority`/`sizes` attributes untouched (LCP).

## Blast radius (accepted)

Shared components mean spillover: `/lp` (paid lander) inherits glass
Header/Footer/FAQ only — its hero is bespoke. `/for/women` inherits the full
glass system under its palette overrides. ~17 pages (blog, terms, etc.) get the
glass Header/Footer. Accepted as brand-cohesive.

## Rollout & success criteria

No feature flag — single code path, pure visual layer. Deploy via push to main
(Vercel auto-deploy). Canary metric: landing→upload-started rate in the daily
report (baseline ~35.3% from the 2026-05-18 audit); regression there triggers
revert. Visual verification before push: build + screenshots of `/`, `/lp`,
`/for/women` at mobile and desktop widths.
