"""Remotion wrapper — renders a composition to MP4.

Calls `npx remotion render` as a subprocess. Expects the Remotion project at
./video_renderer/ relative to the repo root (configurable via env var
AECO_VIDEO_RENDERER_DIR).

Inputs: composition id + props dict. Outputs: absolute path to the MP4.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_RENDERER_DIR = Path(__file__).resolve().parents[3] / "video_renderer"


def _renderer_dir() -> Path:
    override = os.environ.get("AECO_VIDEO_RENDERER_DIR")
    return Path(override) if override else _DEFAULT_RENDERER_DIR


@dataclass
class RenderedReel:
    path: str          # Absolute path to the MP4 file
    composition: str   # Composition id that was rendered
    props: dict        # Props that were passed in
    duration_sec: float | None = None  # Best-effort from ffprobe


async def _ffprobe_duration(path: Path) -> float | None:
    """Return duration in seconds, or None if ffprobe isn't available."""
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


async def render_reel(
    composition: str = "BeforeAfterReel",
    props: dict[str, Any] | None = None,
    output_path: str | None = None,
    *,
    concurrency: int = 4,
    log_level: str = "info",
) -> RenderedReel:
    """Render a Remotion composition to MP4.

    Args:
        composition: Remotion composition id (e.g. "BeforeAfterReel")
        props: dict matching the composition's schema; serialized as --props
        output_path: absolute path for the MP4; defaults to a temp file
        concurrency: number of parallel browser workers
        log_level: "verbose" | "info" | "warn" | "error"

    Returns:
        RenderedReel with the output path + duration.
    """
    props = props or {}
    renderer = _renderer_dir()
    if not (renderer / "package.json").exists():
        raise FileNotFoundError(
            f"Remotion project not found at {renderer}. "
            "Set AECO_VIDEO_RENDERER_DIR or run from the AECO repo root."
        )

    if output_path is None:
        tmp = tempfile.NamedTemporaryFile(prefix="aeco-reel-", suffix=".mp4", delete=False)
        output_path = tmp.name
        tmp.close()

    # Remotion reads --props as a JSON string. macOS/Linux shells need careful escaping,
    # so we write to a temp file and pass --props=/tmp/xxx.json which Remotion supports.
    props_file = tempfile.NamedTemporaryFile(mode="w", prefix="aeco-props-", suffix=".json", delete=False)
    json.dump(props, props_file)
    props_file.close()

    cmd = [
        "npx",
        "remotion",
        "render",
        composition,
        output_path,
        f"--props={props_file.name}",
        f"--concurrency={concurrency}",
        f"--log={log_level}",
        # Force a fresh bundle so files just staged into public/ are picked up.
        # Without this, Remotion can cache an old bundle that doesn't know
        # about runtime-added public/reel_assets/* files.
        "--public-dir=public",
    ]

    logger.info("Rendering %s to %s", composition, output_path)
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=str(renderer),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(
            f"Remotion render failed ({proc.returncode})\n"
            f"STDOUT:\n{stdout.decode()[-2000:]}\n"
            f"STDERR:\n{stderr.decode()[-2000:]}"
        )

    try:
        os.unlink(props_file.name)
    except OSError:
        pass

    path = Path(output_path)
    if not path.exists() or path.stat().st_size == 0:
        raise RuntimeError(f"Remotion reported success but {output_path} is missing/empty")

    duration = await _ffprobe_duration(path)
    return RenderedReel(path=str(path), composition=composition, props=props, duration_sec=duration)
