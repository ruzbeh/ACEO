"""Project scanner — detects language, framework, structure, and conventions."""
from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, Field

# Directories to always skip when scanning
SKIP_DIRS = {
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    ".git",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    "dist",
    "build",
    ".next",
    ".nuxt",
    "egg-info",
}

# Files considered "key" when found at or near the project root
KEY_FILE_NAMES = {
    "README.md",
    "README.rst",
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "package.json",
    "tsconfig.json",
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    "Makefile",
    "Cargo.toml",
    "go.mod",
    "requirements.txt",
    "Pipfile",
    "pom.xml",
    "build.gradle",
    ".env.example",
    "alembic.ini",
    "manage.py",
    "next.config.js",
    "next.config.mjs",
    "vite.config.ts",
    "vite.config.js",
    "tailwind.config.js",
    "tailwind.config.ts",
}

# Language detection by extension
EXTENSION_TO_LANGUAGE = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".jsx": "javascript",
    ".tsx": "typescript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".rb": "ruby",
    ".php": "php",
    ".cs": "csharp",
    ".swift": "swift",
    ".kt": "kotlin",
}


class ProjectContext(BaseModel):
    """Scanned context for a project / codebase."""

    workspace_path: str = Field(description="Absolute path to the project root")
    project_name: str = Field(description="Project name (usually directory name)")
    language: Optional[str] = Field(default=None, description="Primary detected language")
    framework: Optional[str] = Field(default=None, description="Detected framework")
    structure: dict = Field(default_factory=dict, description="Directory tree (top 3 levels)")
    key_files: List[str] = Field(default_factory=list, description="Important files found")
    existing_patterns: str = Field(default="", description="Summary of code conventions detected")


def _should_skip(name: str) -> bool:
    return name in SKIP_DIRS or name.startswith(".")


def _build_tree(root: Path, max_depth: int = 3, _depth: int = 0) -> dict:
    """Build a directory tree dict, top `max_depth` levels."""
    tree: dict = {}
    if _depth >= max_depth:
        return tree
    try:
        entries = sorted(root.iterdir(), key=lambda p: (p.is_file(), p.name))
    except PermissionError:
        return tree
    for entry in entries:
        if _should_skip(entry.name):
            continue
        if entry.is_dir():
            tree[entry.name + "/"] = _build_tree(entry, max_depth, _depth + 1)
        else:
            tree[entry.name] = None
    return tree


def _detect_language(root: Path) -> Optional[str]:
    """Detect the primary language by counting source file extensions."""
    counts: dict[str, int] = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not _should_skip(d)]
        for fname in filenames:
            ext = Path(fname).suffix.lower()
            lang = EXTENSION_TO_LANGUAGE.get(ext)
            if lang:
                counts[lang] = counts.get(lang, 0) + 1
    if not counts:
        return None
    return max(counts, key=counts.get)  # type: ignore[arg-type]


def _detect_framework(root: Path, language: Optional[str]) -> Optional[str]:
    """Detect framework from config files and their contents."""
    # Python frameworks
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        try:
            text = pyproject.read_text(errors="replace")
            lower = text.lower()
            if "fastapi" in lower:
                return "fastapi"
            if "django" in lower:
                return "django"
            if "flask" in lower:
                return "flask"
        except Exception:
            pass

    requirements = root / "requirements.txt"
    if requirements.exists():
        try:
            text = requirements.read_text(errors="replace").lower()
            if "fastapi" in text:
                return "fastapi"
            if "django" in text:
                return "django"
            if "flask" in text:
                return "flask"
        except Exception:
            pass

    if (root / "manage.py").exists():
        return "django"

    # JavaScript / TypeScript frameworks
    pkg_json = root / "package.json"
    if pkg_json.exists():
        try:
            text = pkg_json.read_text(errors="replace").lower()
            if '"next"' in text or '"next":' in text:
                return "nextjs"
            if '"nuxt"' in text or '"nuxt":' in text:
                return "nuxt"
            if '"react"' in text or '"react":' in text:
                return "react"
            if '"vue"' in text or '"vue":' in text:
                return "vue"
            if '"angular' in text:
                return "angular"
            if '"express"' in text:
                return "express"
            if '"nestjs"' in text or '"@nestjs/' in text:
                return "nestjs"
        except Exception:
            pass

    # Go
    if (root / "go.mod").exists():
        try:
            text = (root / "go.mod").read_text(errors="replace").lower()
            if "gin-gonic" in text:
                return "gin"
            if "echo" in text:
                return "echo"
        except Exception:
            pass

    # Rust
    if (root / "Cargo.toml").exists():
        try:
            text = (root / "Cargo.toml").read_text(errors="replace").lower()
            if "actix" in text:
                return "actix"
            if "axum" in text:
                return "axum"
            if "rocket" in text:
                return "rocket"
        except Exception:
            pass

    return None


def _find_key_files(root: Path) -> list[str]:
    """List key files present at the root."""
    found: list[str] = []
    for name in sorted(KEY_FILE_NAMES):
        if (root / name).exists():
            found.append(name)
    return found


def _summarize_patterns(root: Path, key_files: list[str], language: str | None) -> str:
    """Read a few key files and summarize conventions."""
    parts: list[str] = []

    # README excerpt
    for readme in ("README.md", "README.rst"):
        readme_path = root / readme
        if readme_path.exists():
            try:
                text = readme_path.read_text(errors="replace")
                excerpt = text[:500]
                parts.append(f"README excerpt:\n{excerpt}")
            except Exception:
                pass
            break

    # pyproject.toml summary
    if "pyproject.toml" in key_files:
        try:
            text = (root / "pyproject.toml").read_text(errors="replace")
            parts.append(f"pyproject.toml excerpt:\n{text[:800]}")
        except Exception:
            pass

    # package.json summary
    if "package.json" in key_files:
        try:
            text = (root / "package.json").read_text(errors="replace")
            parts.append(f"package.json excerpt:\n{text[:800]}")
        except Exception:
            pass

    # Detect src layout vs flat
    if (root / "src").is_dir():
        parts.append("Layout: src/ layout detected")
    else:
        parts.append("Layout: flat layout (no src/ directory)")

    # Check for linting / formatting config
    for cfg in (".flake8", ".eslintrc.json", ".eslintrc.js", ".prettierrc", "ruff.toml", ".ruff.toml"):
        if (root / cfg).exists():
            parts.append(f"Linting/formatting: {cfg} found")

    return "\n\n".join(parts) if parts else "No patterns detected."


async def scan_project(workspace_path: str) -> ProjectContext:
    """Scan a workspace directory and return a ProjectContext."""
    root = Path(workspace_path).resolve()
    if not root.exists():
        raise FileNotFoundError(f"Workspace path does not exist: {workspace_path}")
    if not root.is_dir():
        raise NotADirectoryError(f"Workspace path is not a directory: {workspace_path}")

    project_name = root.name
    language = _detect_language(root)
    framework = _detect_framework(root, language)
    structure = _build_tree(root, max_depth=3)
    key_files = _find_key_files(root)
    existing_patterns = _summarize_patterns(root, key_files, language)

    return ProjectContext(
        workspace_path=str(root),
        project_name=project_name,
        language=language,
        framework=framework,
        structure=structure,
        key_files=key_files,
        existing_patterns=existing_patterns,
    )
