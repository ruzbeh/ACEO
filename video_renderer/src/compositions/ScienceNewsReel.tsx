import React from "react";
import { z } from "zod";
import {
  AbsoluteFill,
  Audio,
  Img,
  Sequence,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { loadFont } from "@remotion/google-fonts/Inter";

const { fontFamily } = loadFont();

// One beat of the reel: a caption line, its voiceover clip, how long it runs,
// an optional source citation, and an optional AI-generated background image
// (when the Imagen layer is wired; falls back to motion graphics if absent).
const segmentSchema = z.object({
  text: z.string(),
  audioSrc: z.string().optional(),
  durationSec: z.number().default(4),
  source: z.string().optional(),
  imageSrc: z.string().optional(),
});

export const scienceNewsSchema = z.object({
  segments: z.array(segmentSchema).min(1),
  brand: z.string().default("sciencedropdaily"),
  headerLabel: z.string().default("SCIENCE DROP"),
  disclaimer: z.string().default("Educational — not medical advice"),
  icon: z.string().default("🔬"),
  // Which body region the topic targets (legacy figure plumbing; figure removed).
  bodyFocus: z.enum(["head", "heart", "core", "muscle", "whole"]).default("whole"),
  // One premium cinematic hero image for the whole reel (Imagen primary). When set,
  // it becomes a continuous Ken-Burns backdrop; otherwise we fall back to clean
  // motion graphics. Best-effort upstream, so this is always optional.
  heroImage: z.string().optional(),
  musicSrc: z.string().optional(),
});

export type ScienceNewsProps = z.infer<typeof scienceNewsSchema>;

const FPS_FALLBACK = 30;

export const defaultProps: ScienceNewsProps = {
  segments: [
    { text: "A new compound just **rewrote** what we knew about aging.", durationSec: 4 },
    { text: "Scientists found it **clears** damaged cells in mice.", durationSec: 4, source: "Cell, 2026" },
    { text: "Human trials are the **next** step.", durationSec: 3 },
    { text: "Follow for tomorrow's discovery.", durationSec: 3 },
  ],
  brand: "sciencedropdaily",
  headerLabel: "SCIENCE DROP",
  disclaimer: "Educational — not medical advice",
  icon: "🧬",
  bodyFocus: "head",
};

const COLORS = {
  bg0: "#04070d",
  bg1: "#0a1626",
  accent: "#22d3ee",
  accent2: "#34d399",
  accent3: "#6366f1",
  text: "#f8fafc",
  mute: "#94a3b8",
};

function layout(segments: ScienceNewsProps["segments"], fps: number) {
  let t = 0;
  return segments.map((s) => {
    const from = t;
    const len = Math.max(1, Math.round((s.durationSec || 4) * fps));
    t += len;
    return { from, len, seg: s };
  });
}

// ── Motion-graphics layers (deterministic — no Math.random at render time) ──

// Drifting aurora blobs that slowly move + breathe.
const Aurora: React.FC = () => {
  const frame = useCurrentFrame();
  const blobs = [
    { c: COLORS.accent, x: 28, y: 22, r: 58 },
    { c: COLORS.accent2, x: 72, y: 62, r: 62 },
    { c: COLORS.accent3, x: 50, y: 92, r: 54 },
  ];
  return (
    <AbsoluteFill style={{ backgroundColor: COLORS.bg0 }}>
      {blobs.map((b, i) => {
        const x = b.x + Math.sin(frame / 90 + i * 2) * 11;
        const y = b.y + Math.cos(frame / 110 + i * 1.5) * 9;
        const a = 0.20 + 0.06 * Math.sin(frame / 50 + i);
        return (
          <AbsoluteFill
            key={i}
            style={{
              background: `radial-gradient(${b.r}% ${b.r}% at ${x}% ${y}%, ${b.c}00 0%, ${b.c} 0%, transparent 55%)`,
              opacity: a,
            }}
          />
        );
      })}
      <AbsoluteFill
        style={{ background: `radial-gradient(120% 80% at 50% 50%, transparent 55%, ${COLORS.bg0} 100%)` }}
      />
    </AbsoluteFill>
  );
};

// Floating particle field drifting upward (parallax via per-dot speed).
const Particles: React.FC = () => {
  const frame = useCurrentFrame();
  const { width, height } = useVideoConfig();
  const N = 42;
  const dots = [];
  for (let i = 0; i < N; i++) {
    const seed = i * 97.13;
    const baseX = (Math.sin(seed) * 0.5 + 0.5) * width;
    const x = baseX + Math.sin(frame / 60 + i) * 24;
    const speed = 0.45 + (i % 5) * 0.22;
    const yStart = (Math.sin(seed * 1.7) * 0.5 + 0.5) * height;
    let y = (yStart - frame * speed) % height;
    if (y < 0) y += height;
    const size = 2 + (i % 4) * 2;
    const op = 0.10 + (i % 3) * 0.09;
    dots.push(
      <div
        key={i}
        style={{
          position: "absolute",
          left: x,
          top: y,
          width: size,
          height: size,
          borderRadius: "50%",
          background: i % 2 ? COLORS.accent : COLORS.accent2,
          opacity: op,
          filter: "blur(0.5px)",
        }}
      />
    );
  }
  return <AbsoluteFill>{dots}</AbsoluteFill>;
};

// Big faint topic emoji that gently floats + pulses behind the text.
const IconGlyph: React.FC<{ icon: string }> = ({ icon }) => {
  const frame = useCurrentFrame();
  const float = Math.sin(frame / 30) * 16;
  const pulse = 1 + Math.sin(frame / 24) * 0.04;
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <div style={{ fontSize: 440, opacity: 0.07, transform: `translateY(${float}px) scale(${pulse})` }}>
        {icon}
      </div>
    </AbsoluteFill>
  );
};

// ── Anatomical "hologram" figure ───────────────────────────────────────────
// A translucent x-ray body whose internal organs are visible; the topic's organ
// lights up (brain/heart/lungs/gut), the whole body ignites on the hook, recedes
// behind the mid captions, then BLOOMS on the payoff — "take care of this → you
// upgrade." Hand-built glowing vector (no AI imagery); deterministic.
type Region = "head" | "heart" | "core" | "muscle" | "whole";

// Front-view body silhouette in a 1080×1920 viewBox (head/neck/torso bust).
const BODY_PATH =
  "M 392 612 C 432 556 482 548 540 548 C 598 548 648 556 688 612 " +
  "C 726 680 716 800 704 940 C 694 1060 704 1200 672 1330 " +
  "C 650 1420 430 1420 408 1330 C 376 1200 386 1060 376 940 " +
  "C 364 800 354 680 392 612 Z";
const NECK_PATH = "M 500 430 L 580 430 L 588 556 L 492 556 Z";

const REGION_ORGANS: Record<Region, string[]> = {
  head: ["brain"],
  heart: ["heart", "lungs"],
  core: ["stomach", "intestine"],
  muscle: ["body"],
  whole: ["brain", "heart", "lungs", "stomach", "intestine"],
};

const AnatomyFigure: React.FC<{ focus: Region }> = ({ focus }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const D = durationInFrames;
  const heroes = new Set(REGION_ORGANS[focus] ?? REGION_ORGANS.whole);

  // Bookend opacity envelope: ignite on hook → recede behind mid captions → bloom on payoff.
  const env = interpolate(
    frame,
    [0, 0.12 * D, 0.24 * D, 0.72 * D, 0.86 * D, D],
    [0, 0.62, 0.2, 0.18, 0.85, 0.72],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );
  const bloom = interpolate(frame, [0.78 * D, 0.9 * D, D], [0, 1, 0.92], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const breathe = 1 + Math.sin(frame / 28) * 0.01;
  const scanY = (frame * 2.4) % 1920;

  // Per-organ glow: faint by default; flares bright when it's the topic's hero (+pulse, +payoff bloom).
  const lit = (id: string, base = 0.2): number => {
    if (!heroes.has(id)) return base;
    const pulse = 0.5 + 0.5 * Math.sin(frame / 12);
    return Math.min(1, base + 0.5 + bloom * 0.5 + pulse * 0.12);
  };
  const bodyHero = heroes.has("body");

  return (
    <AbsoluteFill style={{ opacity: env }}>
      <svg
        width="100%"
        height="100%"
        viewBox="0 0 1080 1920"
        preserveAspectRatio="xMidYMid meet"
        style={{ transform: `scale(${breathe})`, transformOrigin: "50% 42%" }}
      >
        <defs>
          <linearGradient id="glass" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={COLORS.accent} stopOpacity="0.18" />
            <stop offset="55%" stopColor={COLORS.accent3} stopOpacity="0.1" />
            <stop offset="100%" stopColor={COLORS.accent} stopOpacity="0.05" />
          </linearGradient>
          <filter id="organBlur" x="-80%" y="-80%" width="260%" height="260%">
            <feGaussianBlur stdDeviation="5" result="b" />
            <feMerge>
              <feMergeNode in="b" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          <clipPath id="bodyClip">
            <path d={BODY_PATH} />
            <circle cx="540" cy="300" r="132" />
          </clipPath>
        </defs>

        {/* translucent glass body + rim light */}
        <g filter="url(#organBlur)">
          <path d={NECK_PATH} fill="url(#glass)" stroke={COLORS.accent} strokeWidth="2.5" strokeOpacity="0.4" />
          <circle cx="540" cy="300" r="132" fill="url(#glass)" stroke={COLORS.accent} strokeWidth="2.5" strokeOpacity="0.5" />
          <path
            d={BODY_PATH}
            fill="url(#glass)"
            stroke={COLORS.accent}
            strokeWidth={bodyHero ? 3.4 + bloom * 3 : 2.6}
            strokeOpacity={bodyHero ? 0.85 : 0.5}
          />
        </g>

        {/* horizontal scan sweep, clipped to the body */}
        <g clipPath="url(#bodyClip)">
          <rect x="0" y={scanY} width="1080" height="40" fill={COLORS.accent} opacity="0.07" />
        </g>

        {/* spine */}
        {Array.from({ length: 11 }).map((_, i) => (
          <rect key={i} x="531" y={580 + i * 56} width="18" height="30" rx="7" fill={COLORS.text} opacity="0.14" filter="url(#organBlur)" />
        ))}

        {/* brain */}
        <g filter="url(#organBlur)" opacity={lit("brain")}>
          <ellipse cx="540" cy="284" rx="104" ry="86" fill={COLORS.accent} opacity="0.45" />
          <path
            d="M 540 206 C 502 214 502 252 522 272 C 498 286 512 320 540 320 C 568 320 582 286 558 272 C 578 252 578 214 540 206 Z"
            fill="none"
            stroke={COLORS.bg0}
            strokeWidth="4"
            strokeOpacity="0.45"
          />
        </g>

        {/* lungs */}
        <g filter="url(#organBlur)" opacity={lit("lungs")}>
          <path d="M 524 642 C 472 652 458 742 484 824 C 500 860 528 850 530 802 L 530 650 Z" fill={COLORS.accent2} opacity="0.5" />
          <path d="M 556 642 C 608 652 622 742 596 824 C 580 860 552 850 550 802 L 550 650 Z" fill={COLORS.accent2} opacity="0.5" />
        </g>

        {/* heart */}
        <g filter="url(#organBlur)" opacity={lit("heart")}>
          <path
            d="M 540 724 C 520 694 472 708 480 748 C 487 790 540 818 540 818 C 540 818 593 790 600 748 C 608 708 560 694 540 724 Z"
            fill="#fb7185"
            opacity="0.85"
          />
        </g>

        {/* stomach */}
        <g filter="url(#organBlur)" opacity={lit("stomach")}>
          <path d="M 562 884 C 522 880 508 920 538 944 C 578 968 616 944 602 910 C 594 894 582 886 562 884 Z" fill={COLORS.accent2} opacity="0.5" />
        </g>

        {/* intestines */}
        <g filter="url(#organBlur)" opacity={lit("intestine")}>
          <path
            d="M 474 980 C 474 952 606 952 606 986 C 606 1016 484 1012 484 1046 C 484 1076 596 1072 596 1102 C 596 1130 500 1128 500 1154"
            fill="none"
            stroke={COLORS.accent2}
            strokeWidth="16"
            strokeLinecap="round"
            opacity="0.5"
          />
        </g>
      </svg>
    </AbsoluteFill>
  );
};

// Quick accent pulse at the start of each beat (sequence-relative frame).
const BeatFlash: React.FC = () => {
  const frame = useCurrentFrame();
  const op = interpolate(frame, [0, 5, 16], [0.16, 0.09, 0], { extrapolateRight: "clamp" });
  return (
    <AbsoluteFill
      style={{ background: `radial-gradient(circle at 50% 45%, ${COLORS.accent}, transparent 60%)`, opacity: op }}
    />
  );
};

// Optional AI-generated scene image with a slow Ken Burns + readability overlay.
const SceneImage: React.FC<{ src: string; len: number }> = ({ src, len }) => {
  const frame = useCurrentFrame();
  const scale = interpolate(frame, [0, len], [1.06, 1.2], { extrapolateRight: "clamp" });
  return (
    <AbsoluteFill>
      <Img src={src} style={{ width: "100%", height: "100%", objectFit: "cover", transform: `scale(${scale})` }} />
      <AbsoluteFill
        style={{
          background:
            "linear-gradient(180deg, rgba(4,7,13,0.55) 0%, rgba(4,7,13,0.25) 38%, rgba(4,7,13,0.80) 100%)",
        }}
      />
    </AbsoluteFill>
  );
};

// One premium cinematic hero image for the WHOLE reel — a single continuous slow
// zoom + drift (one coherent film still under the captions), with a readability
// gradient so white text stays legible top-to-bottom.
const HeroImage: React.FC<{ src: string }> = ({ src }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const d = durationInFrames || 1;
  const scale = interpolate(frame, [0, d], [1.04, 1.18], { extrapolateRight: "clamp" });
  const drift = interpolate(frame, [0, d], [-14, 14], { extrapolateRight: "clamp" });
  return (
    <AbsoluteFill>
      <Img
        src={src}
        style={{
          width: "100%",
          height: "100%",
          objectFit: "cover",
          transform: `scale(${scale}) translateY(${drift}px)`,
        }}
      />
      <AbsoluteFill
        style={{
          background:
            "linear-gradient(180deg, rgba(4,7,13,0.58) 0%, rgba(4,7,13,0.20) 40%, rgba(4,7,13,0.84) 100%)",
        }}
      />
    </AbsoluteFill>
  );
};

// Kinetic caption — words pop in with overshoot; **bold** words glow in accent.
const KineticCaption: React.FC<{ text: string; len: number }> = ({ text, len }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const tokens: { word: string; accent: boolean }[] = [];
  text.split("**").forEach((chunk, i) => {
    const accent = i % 2 === 1;
    chunk
      .split(/\s+/)
      .filter(Boolean)
      .forEach((word) => {
        const isPunct = /^[^\p{L}\p{N}]+$/u.test(word);
        const isDash = /^[—–-]+$/u.test(word);
        // A lone em/en dash is a separator, not trailing punctuation: render it as
        // its own NEUTRAL token so a "**word** — next" reads with even spacing on
        // both sides instead of gluing into an accent-colored "word—next".
        if (isPunct && !isDash && tokens.length > 0) {
          tokens[tokens.length - 1].word += word;
        } else {
          tokens.push({ word, accent: isDash ? false : accent });
        }
      });
  });
  const stagger = Math.max(1.5, Math.min(4, (len * 0.5) / Math.max(1, tokens.length)));
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", padding: "0 90px" }}>
      <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "center", gap: "0 22px", maxWidth: 920 }}>
        {tokens.map((tok, i) => {
          const appear = spring({ frame: frame - i * stagger, fps, config: { damping: 11, stiffness: 150, mass: 0.7 } });
          const op = interpolate(appear, [0, 1], [0, 1]);
          const y = interpolate(appear, [0, 1], [44, 0]);
          const sc = interpolate(appear, [0, 0.6, 1], [0.8, 1.08, 1]); // slight overshoot
          return (
            <span
              key={i}
              style={{
                fontFamily,
                fontWeight: 800,
                fontSize: 86,
                lineHeight: 1.12,
                letterSpacing: "-0.02em",
                color: tok.accent ? COLORS.accent : COLORS.text,
                opacity: op,
                transform: `translateY(${y}px) scale(${sc})`,
                textShadow: tok.accent
                  ? `0 0 26px ${COLORS.accent}aa, 0 6px 28px rgba(0,0,0,0.7)`
                  : "0 6px 28px rgba(0,0,0,0.75)",
                display: "inline-block",
              }}
            >
              {tok.word}
            </span>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

const Header: React.FC<{ label: string }> = ({ label }) => {
  const frame = useCurrentFrame();
  const glow = 0.3 + 0.18 * Math.sin(frame / 18);
  return (
    <AbsoluteFill style={{ justifyContent: "flex-start", alignItems: "center", paddingTop: 90 }}>
      <div
        style={{
          fontFamily,
          fontWeight: 800,
          fontSize: 34,
          letterSpacing: "0.32em",
          color: COLORS.bg0,
          background: `linear-gradient(90deg, ${COLORS.accent}, ${COLORS.accent2})`,
          padding: "12px 28px",
          borderRadius: 999,
          boxShadow: `0 8px 34px rgba(34,211,238,${glow})`,
        }}
      >
        {label}
      </div>
    </AbsoluteFill>
  );
};

const Watermark: React.FC<{ brand: string }> = ({ brand }) => (
  <AbsoluteFill style={{ justifyContent: "flex-start", alignItems: "flex-end", padding: 44 }}>
    <div
      style={{
        fontFamily,
        fontWeight: 700,
        fontSize: 28,
        color: COLORS.text,
        opacity: 0.9,
        background: "rgba(255,255,255,0.08)",
        padding: "8px 16px",
        borderRadius: 999,
      }}
    >
      @{brand}
    </div>
  </AbsoluteFill>
);

const SourceChip: React.FC<{ source: string }> = ({ source }) => (
  <AbsoluteFill style={{ justifyContent: "flex-end", alignItems: "center", paddingBottom: 280 }}>
    <div
      style={{
        fontFamily,
        fontWeight: 600,
        fontSize: 30,
        color: COLORS.text,
        background: "rgba(34,211,238,0.16)",
        border: `1px solid ${COLORS.accent}55`,
        padding: "8px 20px",
        borderRadius: 12,
      }}
    >
      Source: {source}
    </div>
  </AbsoluteFill>
);

const Disclaimer: React.FC<{ text: string }> = ({ text }) => (
  <AbsoluteFill style={{ justifyContent: "flex-end", alignItems: "center", paddingBottom: 150 }}>
    <div style={{ fontFamily, fontWeight: 500, fontSize: 24, color: COLORS.mute, opacity: 0.8 }}>{text}</div>
  </AbsoluteFill>
);

const ProgressBar: React.FC = () => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const pct = interpolate(frame, [0, durationInFrames], [0, 100], { extrapolateRight: "clamp" });
  return (
    <AbsoluteFill style={{ justifyContent: "flex-end" }}>
      <div style={{ height: 8, width: "100%", background: "rgba(255,255,255,0.10)" }}>
        <div
          style={{
            height: "100%",
            width: `${pct}%`,
            background: `linear-gradient(90deg, ${COLORS.accent}, ${COLORS.accent2})`,
            boxShadow: `0 0 16px ${COLORS.accent}`,
          }}
        />
      </div>
    </AbsoluteFill>
  );
};

export const ScienceNewsReel: React.FC<ScienceNewsProps> = ({
  segments,
  brand,
  headerLabel,
  disclaimer,
  heroImage,
  musicSrc,
}) => {
  const { fps } = useVideoConfig();
  const blocks = layout(segments, fps || FPS_FALLBACK);
  return (
    <AbsoluteFill style={{ backgroundColor: COLORS.bg0, fontFamily }}>
      {musicSrc && <Audio src={musicSrc} volume={0.12} />}
      {/* Backdrop: premium hero image when available, else clean motion graphics. */}
      {heroImage ? (
        <>
          <HeroImage src={heroImage} />
          <Particles />
        </>
      ) : (
        <>
          <Aurora />
          <Particles />
        </>
      )}
      {/* Per-beat content */}
      {blocks.map(({ from, len, seg }, i) => (
        <Sequence key={i} from={from} durationInFrames={len}>
          {seg.imageSrc && <SceneImage src={seg.imageSrc} len={len} />}
          {seg.audioSrc && <Audio src={seg.audioSrc} />}
          <BeatFlash />
          <KineticCaption text={seg.text} len={len} />
          {seg.source && <SourceChip source={seg.source} />}
        </Sequence>
      ))}
      {/* Persistent overlays */}
      <Header label={headerLabel} />
      <Watermark brand={brand} />
      <Disclaimer text={disclaimer} />
      <ProgressBar />
    </AbsoluteFill>
  );
};
