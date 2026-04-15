"""Video ad generation harness for AECO.

Pipeline:
    script_writer  — LLM → script variants (hook/body/CTA) from a product brief
    composer       — Python wrapper around Remotion (renders MP4 from a composition + props)
    publisher      — Uploads MP4 to FB/IG as a PAUSED video ad

Phase 1 (current): local Ken Burns + captions reel. No paid video gen APIs.
Phase 2: image-to-video (Runway/Luma/Veo) + voiceover (ElevenLabs).
"""
from aeco.tools.video.composer import render_reel, RenderedReel
from aeco.tools.video.script_writer import write_scripts, ReelScript
from aeco.tools.video.publisher import upload_video_to_facebook, create_video_ad
from aeco.tools.video.runway import (
    image_to_video,
    image_to_videos_batch,
    motion_prompt_for,
    RunwayError,
    STYLE_MOTION_PROMPTS,
)

__all__ = [
    "render_reel",
    "RenderedReel",
    "write_scripts",
    "ReelScript",
    "upload_video_to_facebook",
    "create_video_ad",
    "image_to_video",
    "image_to_videos_batch",
    "motion_prompt_for",
    "RunwayError",
    "STYLE_MOTION_PROMPTS",
]
