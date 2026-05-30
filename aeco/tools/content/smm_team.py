"""Social-media manager "team" — reviews + optimizes a rendered reel pre-upload.

Each role is an LLM call via OpenRouter (one vision-capable model, openai/gpt-4o-mini
by default):
  - Copywriter   → hooky YouTube title, description, hashtags, tags
  - Reviewer     → quality + medical-compliance gatekeeper (score, pass/hold)
  - Visual QA    → looks at sampled frames for render/caption problems
  - Scheduler    → recommends a posting time

`review_and_optimize` orchestrates them and returns a decision + optimized metadata.

Failure policy: the team FAILS OPEN (approve with basic metadata) so an LLM hiccup
never stalls the channel — EXCEPT the reviewer/visual gates, which only HOLD when
they explicitly flag a problem (so transient errors don't silently block, but real
flags do).
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Optional

import httpx

from aeco.config import settings

logger = logging.getLogger(__name__)

_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = os.environ.get("SMM_MODEL", "openai/gpt-4o-mini")


def _key() -> Optional[str]:
    return os.environ.get("OPENROUTER_API_KEY") or settings.openrouter_api_key


async def _chat(messages: list, *, max_tokens: int = 700, temperature: float = 0.6) -> str:
    key = _key()
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY not set")
    async with httpx.AsyncClient(timeout=90) as c:
        r = await c.post(
            _URL,
            headers={"Authorization": f"Bearer {key}"},
            json={"model": DEFAULT_MODEL, "messages": messages,
                  "max_tokens": max_tokens, "temperature": temperature},
        )
    if r.status_code != 200:
        raise RuntimeError(f"OpenRouter {r.status_code}: {r.text[:200]}")
    return r.json()["choices"][0]["message"]["content"]


def _json(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        return json.loads(m.group(0)) if m else {}


async def copywriter(topic_id: str, script: str) -> dict:
    sys = (
        "You are a YouTube Shorts growth copywriter for a faceless science channel "
        "(@sciencedropdaily) covering supplements & medical discoveries. Write metadata "
        "that maximizes click-through and search, WITHOUT clickbait that breaks promises "
        "or medical hype. Return STRICT JSON only."
    )
    user = (
        f"Reel script (topic {topic_id}):\n{script}\n\n"
        "Return JSON with these keys:\n"
        '  "title": a hook + key term, max 90 chars, no ALL CAPS, ending with the literal text #Shorts\n'
        '  "description": 2-3 short lines, then a line reading "Educational, not medical advice."\n'
        '  "hashtags": array of 6-8 relevant hashtags including #shorts\n'
        '  "tags": array of 10-12 plain search keywords'
    )
    data = _json(await _chat(
        [{"role": "system", "content": sys}, {"role": "user", "content": user}]
    ))
    return {
        "title": (data.get("title") or "").strip().strip("<>").strip()[:100],
        "description": (data.get("description") or "").strip(),
        "hashtags": data.get("hashtags") or [],
        "tags": data.get("tags") or [],
    }


async def reviewer(topic_id: str, script: str) -> dict:
    sys = (
        "You are the compliance editor for an EDUCATIONAL science Short. The channel "
        "summarizes published research on supplements/health, framed as information, with an "
        "on-screen 'not medical advice' disclaimer. Be PERMISSIVE with properly-hedged content "
        "— your job is to catch only clear violations.\n"
        "PASS when the script frames claims as research ('studies suggest', 'may', 'linked to', "
        "'in animals'), includes a caveat/'the catch', or cites a source. Hedged correlational "
        "science (e.g. 'linked to fewer heart deaths — it's a link, not proof') is FINE and should PASS.\n"
        "HOLD only for explicit violations: specific dosage instructions, claims it CURES/TREATS/"
        "PREVENTS a disease, 'guaranteed' results, telling viewers to stop prescribed meds, or "
        "clearly fabricated specifics. When unsure, PASS. Return STRICT JSON only."
    )
    user = (
        f"Script (topic {topic_id}):\n{script}\n\n"
        "Return JSON: {\"score\": 0.0-1.0, \"decision\": \"pass\"|\"hold\", \"issues\": [short strings]}"
    )
    try:
        data = _json(await _chat(
            [{"role": "system", "content": sys}, {"role": "user", "content": user}],
            temperature=0.2,
        ))
    except Exception as e:  # noqa: BLE001 — transient error must not silently block
        logger.warning("reviewer failed (%s) — defaulting to pass", e)
        return {"score": 0.7, "decision": "pass", "issues": [f"reviewer-error:{e}"]}
    decision = "hold" if str(data.get("decision", "pass")).lower() == "hold" else "pass"
    return {"score": float(data.get("score", 0.7) or 0.7), "decision": decision,
            "issues": data.get("issues") or []}


async def visual_qa(frame_data_uris: list[str]) -> dict:
    if not frame_data_uris:
        return {"ok": True, "issues": []}
    content = [{"type": "text", "text": (
        "These are sampled frames from a vertical science Short whose captions animate in "
        "WORD-BY-WORD. Partial or still-appearing text is NORMAL mid-animation — do NOT flag it. "
        "Only set ok=false for SEVERE defects: a fully black/blank frame, scrambled or overlapping "
        "unreadable text, or an obviously broken render. When unsure, ok=true. Return STRICT JSON: "
        "{\"ok\": true|false, \"issues\": [short strings]}")}]
    for uri in frame_data_uris[:3]:
        content.append({"type": "image_url", "image_url": {"url": uri}})
    try:
        data = _json(await _chat([{"role": "user", "content": content}], temperature=0.2))
    except Exception as e:  # noqa: BLE001
        logger.warning("visual_qa failed (%s) — defaulting to ok", e)
        return {"ok": True, "issues": [f"vqa-error:{e}"]}
    return {"ok": bool(data.get("ok", True)), "issues": data.get("issues") or []}


async def art_director(topic_id: str, segments: list) -> list[str]:
    """Write one cinematic background-image prompt per beat (same order)."""
    beats = [s["text"].replace("**", "") for s in segments]
    sys = (
        "You are the art director for a faceless science Short. For EACH caption beat, write "
        "one short, concrete text-to-image prompt for a cinematic PHOTOGRAPHIC background that "
        "visually represents the beat's subject (e.g. a lab, a neuron, a molecule, a pill, a "
        "sauna). Keep it literal and evocative, no on-image text, no specific real people. "
        "Return STRICT JSON only."
    )
    user = (
        "Beats:\n" + "\n".join(f"{i + 1}. {b}" for i, b in enumerate(beats)) +
        '\n\nReturn JSON: {"prompts": [one prompt per beat, in order]}'
    )
    try:
        data = _json(await _chat(
            [{"role": "system", "content": sys}, {"role": "user", "content": user}],
            max_tokens=600, temperature=0.7,
        ))
        prompts = [str(p) for p in (data.get("prompts") or [])]
    except Exception as e:  # noqa: BLE001
        logger.warning("art_director failed (%s) — using beat text as prompts", e)
        prompts = []
    # Pad/truncate to exactly one per beat (fall back to the beat text itself).
    out = []
    for i, b in enumerate(beats):
        out.append(prompts[i] if i < len(prompts) and prompts[i].strip() else b)
    return out


async def hero_director(topic_id: str, segments: list) -> str:
    """Write ONE cinematic hero-image prompt that captures the whole reel.

    Premium look = one consistent hero scene per reel (not one image per beat),
    so the backdrop reads as a coherent film still under the captions.
    """
    script = " ".join(s["text"].replace("**", "") for s in segments)
    sys = (
        "You are the art director for a faceless science Short. Write ONE short, concrete "
        "text-to-image prompt for a single premium HERO background image that captures the "
        "whole story's subject in one cinematic scene. Favor a real-looking healthy person "
        "WITHIN a wider, atmospheric, on-topic environment (setting, hands, body mid-motion, "
        "silhouette) — keep any face mid-distance or turned, never an extreme close-up, since "
        "tight faces look uncanny. Never include product packaging, jars, bottles, supplement "
        "containers, labels, logos, signage, or any on-image text. No named or real people. "
        "Keep it literal and vivid in one sentence. Return STRICT JSON only."
    )
    user = f"Story:\n{script}\n\nReturn JSON: {{\"prompt\": \"one vivid scene prompt\"}}"
    try:
        data = _json(await _chat(
            [{"role": "system", "content": sys}, {"role": "user", "content": user}],
            max_tokens=200, temperature=0.7,
        ))
        prompt = str(data.get("prompt") or "").strip()
        if prompt:
            return prompt
    except Exception as e:  # noqa: BLE001 — fall back to the hook line
        logger.warning("hero_director failed (%s) — using hook text", e)
    return segments[0]["text"].replace("**", "")


# Higher-engagement Shorts windows (local); rotate so we don't dump all at once.
_SLOTS = ["07:30", "12:30", "17:30", "19:00", "20:30", "21:30"]


def scheduler(index: int = 0) -> str:
    return _SLOTS[index % len(_SLOTS)]


async def review_and_optimize(
    topic_id: str, script: str, frame_data_uris: Optional[list[str]] = None, *, slot_index: int = 0
) -> dict:
    """Run the team. Returns approved flag + optimized metadata + diagnostics."""
    # Copywriter fails open to basic metadata.
    try:
        copy = await copywriter(topic_id, script)
    except Exception as e:  # noqa: BLE001
        logger.warning("copywriter failed (%s) — using basic metadata", e)
        copy = {"title": "", "description": "", "hashtags": [], "tags": []}

    rev = await reviewer(topic_id, script)
    vqa = await visual_qa(frame_data_uris or [])

    approved = rev["decision"] == "pass" and vqa["ok"]
    issues = list(rev["issues"]) + list(vqa["issues"])
    return {
        "approved": approved,
        "title": copy["title"],
        "description": copy["description"],
        "hashtags": copy["hashtags"],
        "tags": copy["tags"],
        "quality_score": rev["score"],
        "posting_time": scheduler(slot_index),
        "issues": issues,
        "decision": rev["decision"],
        "visual_ok": vqa["ok"],
    }
