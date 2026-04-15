"""ElevenLabs voiceover TTS client.

Uses POST https://api.elevenlabs.io/v1/text-to-speech/{voice_id}
and writes the returned MP3 to workspace/reels/voiceover/.

Usage:
    from aeco.tools.video.voiceover import text_to_speech
    path = await text_to_speech(
        "Your LinkedIn photo is the first thing recruiters see.",
        voice="narrator",
    )
"""
from __future__ import annotations

import logging
import os
import shutil
import uuid
from pathlib import Path
from typing import Optional

import httpx

from aeco.config import settings

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.elevenlabs.io/v1"

# Output dir
_AECO_ROOT = Path(__file__).resolve().parents[3]
_VO_DIR = _AECO_ROOT / "workspace" / "reels" / "voiceover"
_VO_DIR.mkdir(parents=True, exist_ok=True)


class ElevenLabsError(RuntimeError):
    pass


# Curated voice IDs — these are ElevenLabs' default preset voices, safe to use.
# See: https://api.elevenlabs.io/v1/voices (with an API key)
VOICES: dict[str, str] = {
    "narrator": "EXAVITQu4vr4xnSDxMaL",   # Sarah — warm, friendly female (recommended for B2C)
    "male_pro": "ErXwobaYiN019PkySvjV",   # Antoni — professional male
    "male_deep": "29vD33N1CtxCmqQRPOHJ",  # Drew — deep confident male
    "female_clear": "21m00Tcm4TlvDq8ikWAM",  # Rachel — clear, natural female
    "male_calm": "VR6AewLTigWG4xSOukaG",   # Arnold — calm authoritative male
}


def _api_key() -> str:
    key = os.environ.get("ELEVENLABS_API_KEY") or getattr(settings, "elevenlabs_api_key", None)
    if not key:
        raise ElevenLabsError(
            "ELEVENLABS_API_KEY not set. Add it to .env or export it."
        )
    return key


def _resolve_voice_id(voice: str) -> str:
    """Accept a preset name (e.g. 'narrator') or a raw ElevenLabs voice_id."""
    if voice in VOICES:
        return VOICES[voice]
    # Raw voice IDs are ~20 chars, alphanumeric
    if len(voice) >= 15 and voice.isalnum():
        return voice
    raise ElevenLabsError(
        f"Unknown voice {voice!r}. Presets: {', '.join(VOICES)} or pass a raw voice_id."
    )


async def text_to_speech(
    text: str,
    *,
    voice: str = "narrator",
    model_id: str = "eleven_multilingual_v2",
    stability: float = 0.50,
    similarity_boost: float = 0.75,
    style: float = 0.0,
    use_speaker_boost: bool = True,
    output_dir: Path | None = None,
    timeout_sec: float = 120.0,
) -> str:
    """Synthesize speech and save as MP3. Returns absolute path.

    Args:
        text: The script to speak (keep under ~500 chars for fast generation).
        voice: preset name (see VOICES) or a raw ElevenLabs voice_id.
        model_id: "eleven_multilingual_v2" (high quality, ~1-2s) or
                  "eleven_turbo_v2_5" (faster, slightly lower quality).
        stability / similarity_boost / style: ElevenLabs voice settings.
        use_speaker_boost: enhances the voice's natural characteristics.
    """
    voice_id = _resolve_voice_id(voice)
    output_dir = output_dir or _VO_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    headers = {
        "Accept": "audio/mpeg",
        "xi-api-key": _api_key(),
        "Content-Type": "application/json",
    }
    body = {
        "text": text,
        "model_id": model_id,
        "voice_settings": {
            "stability": stability,
            "similarity_boost": similarity_boost,
            "style": style,
            "use_speaker_boost": use_speaker_boost,
        },
    }

    logger.info(
        "ElevenLabs: TTS (voice=%s model=%s chars=%d)", voice, model_id, len(text)
    )

    async with httpx.AsyncClient(timeout=timeout_sec) as client:
        resp = await client.post(
            f"{_BASE_URL}/text-to-speech/{voice_id}",
            json=body,
            headers=headers,
        )
        if resp.status_code >= 400:
            raise ElevenLabsError(
                f"TTS failed ({resp.status_code}): {resp.text[:500]}"
            )
        if not resp.content:
            raise ElevenLabsError("TTS returned empty audio")

        out_path = output_dir / f"vo-{uuid.uuid4()}.mp3"
        out_path.write_bytes(resp.content)
        logger.info(
            "ElevenLabs: wrote %.1f KB → %s", len(resp.content) / 1024, out_path
        )
        return str(out_path)


async def measure_mp3_duration(path: str | Path) -> Optional[float]:
    """Return MP3 duration in seconds via ffprobe, or None if ffprobe missing."""
    import asyncio

    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return None
    proc = await asyncio.create_subprocess_exec(
        ffprobe,
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    stdout, _ = await proc.communicate()
    try:
        return float(stdout.decode().strip())
    except (ValueError, TypeError):
        return None


# Default VO script — 18-22s at normal pace. Tuned to flow with the 25s reel
# sections (hook/problem/reveal/proof/cta) so the audio tracks the visuals.
DEFAULT_SCRIPT_TEMPLATE = (
    "Your LinkedIn photo is the first thing recruiters see. "
    "Upload a selfie to Headshot AI and get {n} studio-quality headshots in {time}. "
    "All for just {price}. "
    "Try it free — money-back guarantee."
)


def default_script(n_headshots: int = 8, price: str = "nineteen dollars", time: str = "two minutes") -> str:
    return DEFAULT_SCRIPT_TEMPLATE.format(n=n_headshots, price=price, time=time)
