"""Generate reel script variants from a product brief.

Script = {hook, headline, subheadline, cta_text, ken_burns_captions[]}
that feeds directly into the BeforeAfterReel composition.

Uses Claude via the anthropic SDK if AECO has an API key; otherwise returns
a hand-crafted default that matches the Headshot AI voice.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ReelScript:
    headline: str                         # Big text during reveal section
    subheadline: str                      # Smaller price/urgency text
    cta_text: str                         # Button text on last frame
    brand: str = "headshot-generators.com"
    hook_caption: str = ""                # Optional override of hook text
    problem_caption: str = ""             # Caption for "problem" section
    proof_stats: list[dict[str, str]] = field(default_factory=list)

    def to_props(
        self,
        before_image: str,
        after_images: list[str],
        audio_src: str | None = None,
    ) -> dict:
        """Shape into props for the Remotion composition."""
        return {
            "beforeImage": before_image,
            "afterImages": after_images,
            "headline": self.headline,
            "subheadline": self.subheadline,
            "ctaText": self.cta_text,
            "brand": self.brand,
            **({"audioSrc": audio_src} if audio_src else {}),
        }


_SYSTEM_PROMPT = """You are a direct-response copywriter for AI product reels
on Facebook/Instagram Reels. Write scripts that:
- Stop the scroll in the first 3 seconds
- Use concrete, specific numbers (not "fast" — say "2 minutes")
- Have exactly one strong CTA
- Avoid Meta-flagged claims (no "guaranteed", no "exaggerated before")
- Stay within 25 seconds total

Return STRICT JSON only, no prose."""

_USER_PROMPT_TMPL = """Product brief:
{brief}

Target audience: {audience}
Active ad promises: {promises}

Generate {n} distinct reel scripts. Each must have these fields:
- headline: 3-6 words, bold value prop ("8 Pro Headshots in 2 Minutes")
- subheadline: price + trust signal ("$19 · Money-back guarantee")
- cta_text: the final-frame button text ("Try free today")
- hook_caption: 4-8 word punch-in-the-face opener (optional; "" to use default)
- problem_caption: the "before" caption, 6-14 words (optional)
- brand: brand name (usually "headshot-generators.com")

Output JSON: {{"scripts": [ReelScript, ReelScript, ...]}}
"""


def _default_script() -> ReelScript:
    return ReelScript(
        headline="8 Pro Headshots in 2 Minutes",
        subheadline="$19 · Money-back guarantee",
        cta_text="Try free at headshot-generators.com",
        brand="headshot-generators.com",
        problem_caption="Your LinkedIn photo is the **first thing** recruiters see.",
        proof_stats=[
            {"value": "2,000+", "label": "Happy customers"},
            {"value": "4.8 / 5", "label": "Average rating"},
            {"value": "2 min", "label": "Turnaround"},
            {"value": "$300+", "label": "vs photographer cost"},
        ],
    )


async def write_scripts(
    brief: str,
    audience: str = "US professionals, 28-55, active on LinkedIn",
    promises: str = "8 headshots · $19 · 2 minutes · money-back guarantee",
    n: int = 3,
) -> list[ReelScript]:
    """Generate N reel script variants. Falls back to a curated default if no LLM configured."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.warning("No ANTHROPIC_API_KEY — returning 1 curated default script")
        return [_default_script()]

    try:
        from anthropic import AsyncAnthropic  # type: ignore
    except ImportError:
        logger.warning("anthropic SDK not installed — returning default")
        return [_default_script()]

    client = AsyncAnthropic(api_key=api_key)
    resp = await client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=2000,
        system=_SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": _USER_PROMPT_TMPL.format(
                    brief=brief.strip(), audience=audience, promises=promises, n=n
                ),
            }
        ],
    )
    text = resp.content[0].text if resp.content else "{}"
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Extract JSON block even if there's stray prose
        import re
        m = re.search(r"\{.*\}", text, re.DOTALL)
        data = json.loads(m.group(0)) if m else {"scripts": []}

    out: list[ReelScript] = []
    for s in data.get("scripts", [])[:n]:
        out.append(
            ReelScript(
                headline=s.get("headline", "8 Pro Headshots in 2 Minutes"),
                subheadline=s.get("subheadline", "$19 · Money-back guarantee"),
                cta_text=s.get("cta_text", "Try free today"),
                brand=s.get("brand", "headshot-generators.com"),
                hook_caption=s.get("hook_caption", ""),
                problem_caption=s.get("problem_caption", ""),
            )
        )
    return out or [_default_script()]


def script_to_json(s: ReelScript) -> str:
    return json.dumps(asdict(s), indent=2)
