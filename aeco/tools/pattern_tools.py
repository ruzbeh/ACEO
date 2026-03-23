"""Reusable UI/API pattern library — copy and customize pre-built components.

Patterns live in aeco/templates/_patterns/{name}/ with manifest.json + source files.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from aeco.config import settings

logger = logging.getLogger(__name__)

_PATTERNS_ROOT = Path(__file__).resolve().parent.parent / "templates" / "_patterns"


def _substitute(content: str, variables: dict[str, str]) -> str:
    """Replace {{VAR}} placeholders in content."""
    result = content
    for key, value in variables.items():
        result = result.replace(f"{{{{{key}}}}}", value)
    return result


async def pattern_list() -> dict[str, Any]:
    """List available UI/API patterns with descriptions."""
    patterns = []
    if not _PATTERNS_ROOT.is_dir():
        return {"status": "ok", "patterns": []}

    for d in sorted(_PATTERNS_ROOT.iterdir()):
        if not d.is_dir():
            continue
        manifest_path = d / "manifest.json"
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text())
            patterns.append({
                "name": d.name,
                "description": manifest.get("description", ""),
                "files": [f["src"] for f in manifest.get("files", [])],
                "variables": manifest.get("variables", []),
            })
        else:
            files = [f.name for f in d.iterdir() if f.is_file()]
            patterns.append({
                "name": d.name,
                "description": "",
                "files": files,
                "variables": [],
            })

    return {"status": "ok", "patterns": patterns}


async def pattern_use(
    name: str,
    target_path: str,
    variables: dict[str, str] | None = None,
    workspace_path: str | None = None,
) -> dict[str, Any]:
    """Copy a pattern into the project with variable substitution.

    Args:
        name: Pattern name (directory under _patterns/)
        target_path: Destination path relative to workspace (e.g. "src/components/PricingTable.tsx")
        variables: Optional variable substitutions (e.g. {"PLAN_1_NAME": "Starter"})
        workspace_path: Project workspace path
    """
    ws = Path(workspace_path or settings.workspace_path).expanduser().resolve()
    pattern_dir = _PATTERNS_ROOT / name

    if not pattern_dir.is_dir():
        available = [d.name for d in _PATTERNS_ROOT.iterdir() if d.is_dir()]
        return {
            "status": "error",
            "error": f"Unknown pattern '{name}'. Available: {available}",
        }

    variables = variables or {}
    # Add TARGET_PATH as a variable
    variables["TARGET_PATH"] = target_path

    manifest_path = pattern_dir / "manifest.json"
    files_created: list[str] = []

    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        for file_entry in manifest.get("files", []):
            src = pattern_dir / file_entry["src"]
            # If only one file in pattern, use target_path directly
            dest_template = file_entry.get("dest", target_path)
            dest_rel = _substitute(dest_template, variables)
            dest = ws / dest_rel

            if not src.exists():
                logger.warning(f"Pattern file not found: {src}")
                continue

            dest.parent.mkdir(parents=True, exist_ok=True)
            content = src.read_text(encoding="utf-8")
            content = _substitute(content, variables)
            dest.write_text(content, encoding="utf-8")
            files_created.append(dest_rel)
    else:
        # No manifest — copy all files from pattern dir
        for src in pattern_dir.iterdir():
            if src.is_file():
                dest = ws / target_path / src.name
                dest.parent.mkdir(parents=True, exist_ok=True)
                content = src.read_text(encoding="utf-8")
                content = _substitute(content, variables)
                dest.write_text(content, encoding="utf-8")
                files_created.append(str(Path(target_path) / src.name))

    logger.info(f"Applied pattern '{name}' → {files_created}")
    return {
        "status": "ok",
        "pattern": name,
        "files_created": files_created,
        "variables_applied": list(variables.keys()),
    }
