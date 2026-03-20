"""Workspace scanner: reads key files to build product context.

Before the portfolio can make decisions, agents need to know what the
product actually IS — what tech stack, what the codebase looks like,
what README says, what config files exist, etc.

This scanner reads the workspace and builds a compact product summary
that gets injected into every agent context.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Files to look for (in priority order) to understand the product
_KEY_FILES = [
    "README.md",
    "readme.md",
    "README.rst",
    "package.json",
    "pyproject.toml",
    "setup.py",
    "requirements.txt",
    "Pipfile",
    "Cargo.toml",
    "go.mod",
    "pom.xml",
    "build.gradle",
    "docker-compose.yml",
    "docker-compose.yaml",
    "Dockerfile",
    ".env.example",
    ".env.sample",
    "next.config.js",
    "next.config.ts",
    "vite.config.ts",
    "tsconfig.json",
    "webpack.config.js",
    "app.json",
    "vercel.json",
    "netlify.toml",
]

# Directories that indicate tech stack / structure
_KEY_DIRS = [
    "src",
    "app",
    "pages",
    "components",
    "api",
    "lib",
    "utils",
    "models",
    "services",
    "routes",
    "controllers",
    "middleware",
    "tests",
    "test",
    "__tests__",
    "public",
    "static",
    "templates",
    "migrations",
]

# Max chars to read from any single file
_MAX_FILE_CHARS = 3000


def _safe_read(path: Path, max_chars: int = _MAX_FILE_CHARS) -> str:
    """Read a file safely, returning empty string on failure."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        return text[:max_chars]
    except Exception:
        return ""


def _detect_tech_stack(workspace: Path) -> list[str]:
    """Detect technologies used based on config files."""
    stack = []
    checks = {
        "Next.js": ["next.config.js", "next.config.ts", "next.config.mjs"],
        "React": ["package.json"],  # refined below
        "Vue.js": ["vue.config.js", "nuxt.config.ts"],
        "Python/Django": ["manage.py", "django"],
        "Python/FastAPI": ["main.py"],  # refined below
        "Python/Flask": ["app.py"],
        "Node.js": ["package.json"],
        "TypeScript": ["tsconfig.json"],
        "Docker": ["Dockerfile", "docker-compose.yml", "docker-compose.yaml"],
        "PostgreSQL": [],  # detected from config content
        "Redis": [],
        "Stripe": [],
        "Tailwind CSS": ["tailwind.config.js", "tailwind.config.ts"],
    }

    for tech, files in checks.items():
        for f in files:
            if (workspace / f).exists():
                # Refine React detection
                if tech == "React" and f == "package.json":
                    content = _safe_read(workspace / f, 2000)
                    if '"react"' in content:
                        stack.append("React")
                    continue
                stack.append(tech)
                break

    # Check package.json for more deps
    pkg_path = workspace / "package.json"
    if pkg_path.exists():
        content = _safe_read(pkg_path, 5000)
        if "stripe" in content.lower():
            stack.append("Stripe")
        if "prisma" in content.lower():
            stack.append("Prisma")
        if "tailwind" in content.lower() and "Tailwind CSS" not in stack:
            stack.append("Tailwind CSS")
        if "supabase" in content.lower():
            stack.append("Supabase")

    # Check .env.example for services
    for env_file in [".env.example", ".env.sample", ".env.local.example"]:
        env_path = workspace / env_file
        if env_path.exists():
            content = _safe_read(env_path, 3000).upper()
            if "POSTGRES" in content or "DATABASE_URL" in content:
                if "PostgreSQL" not in stack:
                    stack.append("PostgreSQL")
            if "REDIS" in content:
                if "Redis" not in stack:
                    stack.append("Redis")
            if "STRIPE" in content:
                if "Stripe" not in stack:
                    stack.append("Stripe")
            if "FACEBOOK" in content or "META" in content:
                stack.append("Facebook/Meta Ads")
            if "OPENAI" in content:
                stack.append("OpenAI")
            if "S3" in content or "AWS" in content:
                stack.append("AWS")

    return list(set(stack))


def _get_directory_tree(workspace: Path, max_depth: int = 3) -> str:
    """Get a compact directory tree showing structure."""
    lines = []
    ignore_dirs = {
        "node_modules", ".git", "__pycache__", ".next", ".nuxt",
        "dist", "build", ".cache", "coverage", ".venv", "venv",
        "env", ".tox", ".pytest_cache", ".mypy_cache",
    }

    def _walk(path: Path, prefix: str, depth: int):
        if depth > max_depth:
            return
        try:
            entries = sorted(path.iterdir(), key=lambda e: (not e.is_dir(), e.name))
        except PermissionError:
            return

        dirs = [e for e in entries if e.is_dir() and e.name not in ignore_dirs and not e.name.startswith(".")]
        files = [e for e in entries if e.is_file() and not e.name.startswith(".")]

        # Limit to most important files at each level
        for d in dirs[:15]:
            lines.append(f"{prefix}{d.name}/")
            _walk(d, prefix + "  ", depth + 1)
        for f in files[:10]:
            lines.append(f"{prefix}{f.name}")

    _walk(workspace, "", 0)
    return "\n".join(lines[:100])  # cap at 100 lines


def scan_workspace(workspace_path: str) -> dict[str, Any]:
    """Scan a workspace directory and return a product context summary.

    Returns a dict with:
    - product_name: str
    - product_description: str (from README)
    - tech_stack: list[str]
    - directory_structure: str
    - key_files: dict[str, str] (filename → content preview)
    - file_count: int
    - has_tests: bool
    - has_docker: bool
    - has_ci: bool
    """
    workspace = Path(workspace_path).resolve()
    if not workspace.exists():
        logger.warning(f"Workspace not found: {workspace}")
        return {
            "product_name": "Unknown",
            "product_description": "Workspace directory not found",
            "tech_stack": [],
            "directory_structure": "",
            "key_files": {},
            "error": f"Directory not found: {workspace}",
        }

    logger.info(f"Scanning workspace: {workspace}")

    # 1. Read key files
    key_files = {}
    for fname in _KEY_FILES:
        fpath = workspace / fname
        if fpath.exists():
            content = _safe_read(fpath)
            if content.strip():
                key_files[fname] = content

    # 2. Extract product name and description from README
    product_name = workspace.name
    product_description = ""
    for readme_name in ["README.md", "readme.md", "README.rst"]:
        if readme_name in key_files:
            readme_content = key_files[readme_name]
            # Extract first heading and paragraph
            lines = readme_content.split("\n")
            for line in lines:
                if line.startswith("# ") and not product_name:
                    product_name = line[2:].strip()
                elif line.strip() and not line.startswith("#") and not line.startswith("!") and not line.startswith("["):
                    if not product_description:
                        product_description = line.strip()
            break

    # Also try package.json for name/description
    if "package.json" in key_files:
        try:
            import json
            pkg = json.loads(key_files["package.json"])
            if not product_description and pkg.get("description"):
                product_description = pkg["description"]
            if pkg.get("name") and product_name == workspace.name:
                product_name = pkg["name"]
        except Exception:
            pass

    # 3. Detect tech stack
    tech_stack = _detect_tech_stack(workspace)

    # 4. Directory tree
    dir_tree = _get_directory_tree(workspace)

    # 5. Stats
    file_count = sum(1 for _ in workspace.rglob("*") if _.is_file() and ".git" not in str(_) and "node_modules" not in str(_))
    has_tests = any((workspace / d).exists() for d in ["tests", "test", "__tests__", "spec"])
    has_docker = (workspace / "Dockerfile").exists() or (workspace / "docker-compose.yml").exists()
    has_ci = any((workspace / d).exists() for d in [".github/workflows", ".gitlab-ci.yml", ".circleci"])

    result = {
        "product_name": product_name,
        "product_description": product_description,
        "tech_stack": tech_stack,
        "directory_structure": dir_tree,
        "key_files": {k: v[:1500] for k, v in key_files.items()},  # trim for context
        "file_count": file_count,
        "has_tests": has_tests,
        "has_docker": has_docker,
        "has_ci": has_ci,
    }

    logger.info(
        f"Workspace scan complete: {product_name}, "
        f"{len(tech_stack)} tech stack items, {file_count} files"
    )

    return result
