import React from "react";
import { z } from "zod";
import {
  AbsoluteFill,
  Audio,
  Img,
  Sequence,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { loadFont } from "@remotion/google-fonts/Inter";

const { fontFamily } = loadFont();

// ─────────────────────────────────────────────────────────────────────────────
// Schema — Python wrapper passes this as JSON via --props
// ─────────────────────────────────────────────────────────────────────────────
export const beforeAfterSchema = z.object({
  beforeImage: z.string(), // URL or staticFile("...") path
  afterImages: z.array(z.string()).min(3).max(6),
  headline: z.string(), // "8 headshots in 2 minutes"
  subheadline: z.string(), // "$19 · Money-back guarantee"
  ctaText: z.string().default("Link in bio"),
  brand: z.string().default("headshot-generators.com"),
  audioSrc: z.string().optional(), // optional music track
  // Section durations in seconds (total = 25s by default; see Root.tsx)
  sections: z
    .object({
      hook: z.number().default(3),
      problem: z.number().default(3),
      reveal: z.number().default(10),
      proof: z.number().default(4),
      cta: z.number().default(5),
    })
    .default({ hook: 3, problem: 3, reveal: 10, proof: 4, cta: 5 }),
});

export type BeforeAfterProps = z.infer<typeof beforeAfterSchema>;

// Defaults — used for live preview in the Remotion studio
export const defaultProps: BeforeAfterProps = {
  beforeImage: staticFile("demo/before.jpg"),
  afterImages: [
    staticFile("demo/after1.jpg"),
    staticFile("demo/after2.jpg"),
    staticFile("demo/after3.jpg"),
    staticFile("demo/after4.jpg"),
  ],
  headline: "8 Pro Headshots in 2 Minutes",
  subheadline: "$19 · Money-back guarantee",
  ctaText: "Try free at headshot-generators.com",
  brand: "AI Headshot Studio",
  sections: { hook: 3, problem: 3, reveal: 10, proof: 4, cta: 5 },
};

// Palette — matches site (neutral-900 bg, amber-500 accent)
const COLORS = {
  bg: "#0c0a09",
  accent: "#f59e0b",
  text: "#fafaf9",
  mute: "#a8a29e",
  success: "#10b981",
};

// ─────────────────────────────────────────────────────────────────────────────
// Ken Burns helper — slow zoom + slight pan for life
// ─────────────────────────────────────────────────────────────────────────────
const KenBurns: React.FC<{ src: string; direction?: "in" | "out"; from?: number; to?: number }> = ({
  src,
  direction = "in",
  from = 1,
  to = 1.08,
}) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const scale = interpolate(frame, [0, durationInFrames], direction === "in" ? [from, to] : [to, from], {
    extrapolateRight: "clamp",
  });
  return (
    <AbsoluteFill style={{ backgroundColor: COLORS.bg }}>
      <Img src={src} style={{ width: "100%", height: "100%", objectFit: "cover", transform: `scale(${scale})` }} />
    </AbsoluteFill>
  );
};

// Fade in/out helper
const FadeIn: React.FC<{ children: React.ReactNode; fadeIn?: number; fadeOut?: number; duration: number }> = ({
  children,
  fadeIn = 8,
  fadeOut = 8,
  duration,
}) => {
  const frame = useCurrentFrame();
  const opacity = interpolate(
    frame,
    [0, fadeIn, duration - fadeOut, duration],
    [0, 1, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );
  return <AbsoluteFill style={{ opacity }}>{children}</AbsoluteFill>;
};

// Caption chip — bold bg pill at bottom third
const Caption: React.FC<{ text: string; color?: string; accent?: string }> = ({
  text,
  color = COLORS.text,
  accent = COLORS.accent,
}) => {
  return (
    <AbsoluteFill style={{ justifyContent: "flex-end", alignItems: "center", paddingBottom: 360 }}>
      <div
        style={{
          fontFamily,
          fontWeight: 800,
          fontSize: 72,
          lineHeight: 1.1,
          letterSpacing: "-0.02em",
          color,
          textAlign: "center",
          padding: "32px 48px",
          maxWidth: 900,
          textShadow: "0 4px 24px rgba(0,0,0,0.6)",
          borderRadius: 16,
          background: `linear-gradient(180deg, rgba(0,0,0,0) 0%, rgba(0,0,0,0.35) 50%, rgba(0,0,0,0.55) 100%)`,
        }}
      >
        {text.split("**").map((chunk, i) =>
          i % 2 === 1 ? (
            <span key={i} style={{ color: accent }}>
              {chunk}
            </span>
          ) : (
            <span key={i}>{chunk}</span>
          )
        )}
      </div>
    </AbsoluteFill>
  );
};

// Brand watermark — top-right
const Watermark: React.FC<{ brand: string }> = ({ brand }) => (
  <AbsoluteFill style={{ justifyContent: "flex-start", alignItems: "flex-end", padding: 40 }}>
    <div
      style={{
        fontFamily,
        fontWeight: 700,
        fontSize: 28,
        color: COLORS.text,
        opacity: 0.9,
        background: "rgba(0,0,0,0.4)",
        padding: "8px 16px",
        borderRadius: 999,
      }}
    >
      {brand}
    </div>
  </AbsoluteFill>
);

// ─────────────────────────────────────────────────────────────────────────────
// Main composition
// ─────────────────────────────────────────────────────────────────────────────
export const BeforeAfterReel: React.FC<BeforeAfterProps> = ({
  beforeImage,
  afterImages,
  headline,
  subheadline,
  ctaText,
  brand,
  audioSrc,
  sections,
}) => {
  const { fps } = useVideoConfig();
  const S = {
    hook: Math.round(sections.hook * fps),
    problem: Math.round(sections.problem * fps),
    reveal: Math.round(sections.reveal * fps),
    proof: Math.round(sections.proof * fps),
    cta: Math.round(sections.cta * fps),
  };
  let t = 0;
  const hookStart = t;
  t += S.hook;
  const problemStart = t;
  t += S.problem;
  const revealStart = t;
  t += S.reveal;
  const proofStart = t;
  t += S.proof;
  const ctaStart = t;

  // How many after clips during reveal; each ~ (reveal / count) frames long
  const afterCount = Math.min(afterImages.length, 4);
  const afterClipLen = Math.floor(S.reveal / afterCount);

  return (
    <AbsoluteFill style={{ backgroundColor: COLORS.bg, fontFamily }}>
      {audioSrc && <Audio src={audioSrc} volume={0.35} />}

      {/* ── HOOK: Before image zooms in, bold question overlay ── */}
      <Sequence from={hookStart} durationInFrames={S.hook}>
        <FadeIn duration={S.hook}>
          <KenBurns src={beforeImage} direction="in" from={1} to={1.12} />
          <AbsoluteFill
            style={{
              background:
                "linear-gradient(180deg, rgba(12,10,9,0.75) 0%, rgba(12,10,9,0.2) 40%, rgba(12,10,9,0.6) 100%)",
            }}
          />
          <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", padding: 80 }}>
            <HookText />
          </AbsoluteFill>
          <Watermark brand={brand} />
        </FadeIn>
      </Sequence>

      {/* ── PROBLEM: still before, different framing, new caption ── */}
      <Sequence from={problemStart} durationInFrames={S.problem}>
        <FadeIn duration={S.problem}>
          <KenBurns src={beforeImage} direction="out" from={1.12} to={1} />
          <AbsoluteFill
            style={{ background: "linear-gradient(0deg, rgba(0,0,0,0.65) 0%, rgba(0,0,0,0) 40%)" }}
          />
          <Caption text="Your LinkedIn photo is the **first thing** recruiters see." />
          <Watermark brand={brand} />
        </FadeIn>
      </Sequence>

      {/* ── REVEAL: after images swap in succession, each with a style label ── */}
      {afterImages.slice(0, afterCount).map((src, i) => {
        const from = revealStart + i * afterClipLen;
        const isFirst = i === 0;
        return (
          <Sequence key={src + i} from={from} durationInFrames={afterClipLen}>
            <FadeIn duration={afterClipLen} fadeIn={6} fadeOut={6}>
              <KenBurns src={src} direction={i % 2 === 0 ? "in" : "out"} from={1.02} to={1.1} />
              <AbsoluteFill
                style={{
                  background: "linear-gradient(0deg, rgba(0,0,0,0.55) 0%, rgba(0,0,0,0) 35%)",
                }}
              />
              {isFirst ? (
                <Caption text={`**${headline}**`} />
              ) : (
                <Caption text={`Style ${i + 1} of 8 · ${subheadline}`} />
              )}
              <StyleBadge index={i} />
              <Watermark brand={brand} />
            </FadeIn>
          </Sequence>
        );
      })}

      {/* ── PROOF: social proof numbers slide in ── */}
      <Sequence from={proofStart} durationInFrames={S.proof}>
        <FadeIn duration={S.proof}>
          <AbsoluteFill
            style={{
              background:
                "radial-gradient(ellipse at 50% 30%, rgba(245,158,11,0.15), rgba(12,10,9,1) 70%)",
            }}
          />
          <SocialProofStack />
          <Watermark brand={brand} />
        </FadeIn>
      </Sequence>

      {/* ── CTA: final offer + big button ── */}
      <Sequence from={ctaStart} durationInFrames={S.cta}>
        <FadeIn duration={S.cta}>
          <AbsoluteFill style={{ backgroundColor: COLORS.bg }} />
          <CTAScreen headline={headline} subheadline={subheadline} ctaText={ctaText} />
          <Watermark brand={brand} />
        </FadeIn>
      </Sequence>
    </AbsoluteFill>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// Section-specific sub-components
// ─────────────────────────────────────────────────────────────────────────────
const HookText: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const scaleIn = spring({ frame, fps, config: { damping: 12 } });
  return (
    <div style={{ textAlign: "center", transform: `scale(${scaleIn})` }}>
      <div
        style={{
          fontFamily,
          fontWeight: 900,
          fontSize: 130,
          lineHeight: 0.95,
          color: COLORS.text,
          letterSpacing: "-0.04em",
          textShadow: "0 8px 40px rgba(0,0,0,0.8)",
        }}
      >
        Your LinkedIn
      </div>
      <div
        style={{
          fontFamily,
          fontWeight: 900,
          fontSize: 130,
          lineHeight: 0.95,
          color: COLORS.accent,
          letterSpacing: "-0.04em",
          textShadow: "0 8px 40px rgba(0,0,0,0.8)",
          marginTop: 8,
        }}
      >
        photo?
      </div>
    </div>
  );
};

const StyleBadge: React.FC<{ index: number }> = ({ index }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const labels = ["Corporate", "Startup Founder", "Creative Studio", "Casual Pro", "Editorial", "Executive"];
  const label = labels[index % labels.length];
  const slide = spring({ frame, fps, config: { damping: 15 } });
  const y = interpolate(slide, [0, 1], [-100, 0]);
  return (
    <AbsoluteFill style={{ justifyContent: "flex-start", alignItems: "center", paddingTop: 140 }}>
      <div
        style={{
          fontFamily,
          fontWeight: 700,
          fontSize: 36,
          color: COLORS.bg,
          background: COLORS.accent,
          padding: "14px 32px",
          borderRadius: 999,
          transform: `translateY(${y}px)`,
          boxShadow: "0 8px 32px rgba(245,158,11,0.35)",
        }}
      >
        {label}
      </div>
    </AbsoluteFill>
  );
};

const SocialProofStack: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const stats = [
    { value: "2,000+", label: "Happy customers" },
    { value: "4.8 / 5", label: "Average rating" },
    { value: "2 min", label: "Turnaround" },
    { value: "$300+", label: "vs photographer cost" },
  ];
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <div style={{ display: "flex", flexDirection: "column", gap: 36, alignItems: "center" }}>
        <div
          style={{
            fontFamily,
            fontSize: 42,
            fontWeight: 700,
            color: COLORS.mute,
            textTransform: "uppercase",
            letterSpacing: "0.2em",
          }}
        >
          The proof
        </div>
        {stats.map((s, i) => {
          const delay = i * 6;
          const appear = spring({ frame: frame - delay, fps, config: { damping: 14 } });
          const op = interpolate(appear, [0, 1], [0, 1]);
          const y = interpolate(appear, [0, 1], [40, 0]);
          return (
            <div
              key={s.label}
              style={{
                opacity: op,
                transform: `translateY(${y}px)`,
                textAlign: "center",
              }}
            >
              <div style={{ fontFamily, fontSize: 110, fontWeight: 900, color: COLORS.accent, lineHeight: 1 }}>
                {s.value}
              </div>
              <div style={{ fontFamily, fontSize: 36, color: COLORS.text, fontWeight: 500, marginTop: 4 }}>
                {s.label}
              </div>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

const CTAScreen: React.FC<{ headline: string; subheadline: string; ctaText: string }> = ({
  headline,
  subheadline,
  ctaText,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const pulse = spring({ frame: frame % 45, fps, config: { damping: 10 } });
  const scale = interpolate(pulse, [0, 1], [0.95, 1]);
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", padding: 80 }}>
      <div style={{ textAlign: "center", display: "flex", flexDirection: "column", gap: 32 }}>
        <div
          style={{
            fontFamily,
            fontWeight: 900,
            fontSize: 110,
            lineHeight: 1.02,
            color: COLORS.text,
            letterSpacing: "-0.04em",
          }}
        >
          {headline}
        </div>
        <div style={{ fontFamily, fontSize: 48, color: COLORS.accent, fontWeight: 600 }}>{subheadline}</div>
        <div
          style={{
            marginTop: 60,
            fontFamily,
            fontWeight: 800,
            fontSize: 54,
            color: COLORS.bg,
            background: COLORS.accent,
            padding: "28px 56px",
            borderRadius: 999,
            boxShadow: `0 12px 40px rgba(245,158,11,${0.35 + 0.15 * pulse})`,
            transform: `scale(${scale})`,
          }}
        >
          {ctaText}
        </div>
      </div>
    </AbsoluteFill>
  );
};
