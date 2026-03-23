"""Project scaffolding tools — generate full project skeletons from templates.

Templates live in aeco/templates/{stack}/ with {{VAR}} placeholders.
Feature add-ons in aeco/templates/_features/{feature}/ with manifest.json.
"""
from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
from typing import Any

from aeco.config import settings

logger = logging.getLogger(__name__)

_TEMPLATES_ROOT = Path(__file__).resolve().parent.parent / "templates"

# Variable substitution markers
_VAR_PREFIX = "{{"
_VAR_SUFFIX = "}}"


def _substitute(content: str, variables: dict[str, str]) -> str:
    """Replace {{VAR}} placeholders in content."""
    result = content
    for key, value in variables.items():
        result = result.replace(f"{_VAR_PREFIX}{key}{_VAR_SUFFIX}", value)
    return result


def _slugify(name: str) -> str:
    """Convert project name to URL-safe slug."""
    return name.lower().replace(" ", "-").replace("_", "-")


def _copy_template_tree(
    src_dir: Path,
    dest_dir: Path,
    variables: dict[str, str],
    files_created: list[str],
) -> None:
    """Recursively copy template directory, substituting variables in text files."""
    text_extensions = {
        ".ts", ".tsx", ".js", ".jsx", ".json", ".css", ".html", ".md",
        ".yml", ".yaml", ".sql", ".env", ".txt", ".gitignore", ".mjs",
    }
    # Also treat dotfiles and extensionless files as text
    for src_path in src_dir.rglob("*"):
        if src_path.is_dir():
            continue
        rel = src_path.relative_to(src_dir)
        dest_path = dest_dir / rel
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        suffix = src_path.suffix.lower()
        name_lower = src_path.name.lower()
        is_text = (
            suffix in text_extensions
            or name_lower.startswith(".")
            or suffix == ""
        )

        if is_text:
            try:
                content = src_path.read_text(encoding="utf-8")
                content = _substitute(content, variables)
                dest_path.write_text(content, encoding="utf-8")
            except UnicodeDecodeError:
                shutil.copy2(src_path, dest_path)
        else:
            shutil.copy2(src_path, dest_path)

        files_created.append(str(rel))


async def scaffold_project(
    name: str,
    stack: str = "nextjs-supabase-stripe",
    features: list[str] | None = None,
    workspace_path: str | None = None,
) -> dict[str, Any]:
    """Generate a full project skeleton from a template.

    Args:
        name: Project name (e.g. "headshot-ai")
        stack: Template to use (directory name under aeco/templates/)
        features: Optional feature add-ons to merge (e.g. ["auth", "payments", "file-upload"])
        workspace_path: Base directory to create project in
    """
    ws = Path(workspace_path or settings.workspace_path).expanduser().resolve()
    template_dir = _TEMPLATES_ROOT / stack

    if not template_dir.is_dir():
        available = [
            d.name for d in _TEMPLATES_ROOT.iterdir()
            if d.is_dir() and not d.name.startswith("_")
        ]
        return {
            "status": "error",
            "error": f"Unknown stack '{stack}'. Available: {available}",
        }

    slug = _slugify(name)
    project_dir = ws / slug
    project_dir.mkdir(parents=True, exist_ok=True)

    variables = {
        "PROJECT_NAME": name,
        "PROJECT_SLUG": slug,
        "DESCRIPTION": f"{name} — built with AECO",
    }

    files_created: list[str] = []

    # Copy base template
    _copy_template_tree(template_dir, project_dir, variables, files_created)
    logger.info(f"Scaffolded base template '{stack}' → {project_dir} ({len(files_created)} files)")

    # Merge feature add-ons
    features_applied: list[str] = []
    for feature in (features or []):
        feature_dir = _TEMPLATES_ROOT / "_features" / feature
        if not feature_dir.is_dir():
            logger.warning(f"Feature '{feature}' not found at {feature_dir}")
            continue

        manifest_path = feature_dir / "manifest.json"
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text())
            for file_entry in manifest.get("files", []):
                src = feature_dir / file_entry["src"]
                dest = project_dir / file_entry["dest"]
                if src.exists():
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    content = src.read_text(encoding="utf-8")
                    content = _substitute(content, variables)
                    dest.write_text(content, encoding="utf-8")
                    files_created.append(file_entry["dest"])
        else:
            # No manifest — copy entire feature directory
            _copy_template_tree(feature_dir, project_dir, variables, files_created)

        features_applied.append(feature)
        logger.info(f"Applied feature '{feature}' to {project_dir}")

    return {
        "status": "ok",
        "path": str(project_dir),
        "project_name": name,
        "stack": stack,
        "features": features_applied,
        "files_created": files_created,
        "total_files": len(files_created),
    }


async def scaffold_list_templates() -> dict[str, Any]:
    """List available project templates and features."""
    templates = []
    for d in sorted(_TEMPLATES_ROOT.iterdir()):
        if d.is_dir() and not d.name.startswith("_"):
            file_count = sum(1 for _ in d.rglob("*") if _.is_file())
            templates.append({
                "name": d.name,
                "files": file_count,
            })

    features = []
    features_dir = _TEMPLATES_ROOT / "_features"
    if features_dir.is_dir():
        for d in sorted(features_dir.iterdir()):
            if d.is_dir():
                manifest_path = d / "manifest.json"
                desc = ""
                if manifest_path.exists():
                    m = json.loads(manifest_path.read_text())
                    desc = m.get("description", "")
                features.append({"name": d.name, "description": desc})

    patterns = []
    patterns_dir = _TEMPLATES_ROOT / "_patterns"
    if patterns_dir.is_dir():
        for d in sorted(patterns_dir.iterdir()):
            if d.is_dir():
                manifest_path = d / "manifest.json"
                desc = ""
                if manifest_path.exists():
                    m = json.loads(manifest_path.read_text())
                    desc = m.get("description", "")
                patterns.append({"name": d.name, "description": desc})

    return {
        "status": "ok",
        "templates": templates,
        "features": features,
        "patterns": patterns,
    }
