"""CI/CD pipeline generation tools — write GitHub Actions / Vercel config files."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from aeco.config import settings

logger = logging.getLogger(__name__)

_CICD_TEMPLATES_ROOT = Path(__file__).resolve().parent.parent / "templates" / "_cicd"


_GITHUB_ACTIONS_VERCEL = """\
name: CI/CD

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

env:
  VERCEL_ORG_ID: ${{ secrets.VERCEL_ORG_ID }}
  VERCEL_PROJECT_ID: ${{ secrets.VERCEL_PROJECT_ID }}

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: npm
      - run: npm ci
      - run: npm run lint --if-present
      - run: npm test --if-present

  deploy-preview:
    needs: test
    if: github.event_name == 'pull_request'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: npm
      - run: npm ci
      - run: npx vercel pull --yes --environment=preview --token=${{ secrets.VERCEL_TOKEN }}
      - run: npx vercel build --token=${{ secrets.VERCEL_TOKEN }}
      - run: npx vercel deploy --prebuilt --token=${{ secrets.VERCEL_TOKEN }}

  deploy-production:
    needs: test
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: npm
      - run: npm ci
      - run: npx vercel pull --yes --environment=production --token=${{ secrets.VERCEL_TOKEN }}
      - run: npx vercel build --prod --token=${{ secrets.VERCEL_TOKEN }}
      - run: npx vercel deploy --prebuilt --prod --token=${{ secrets.VERCEL_TOKEN }}
"""

_GITHUB_ACTIONS_BASIC = """\
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: npm
      - run: npm ci
      - run: npm run build
      - run: npm run lint --if-present
      - run: npm test --if-present
"""


_TEMPLATES = {
    "github-actions-vercel": _GITHUB_ACTIONS_VERCEL,
    "github-actions-basic": _GITHUB_ACTIONS_BASIC,
}


async def cicd_generate(
    provider: str = "github-actions",
    deploy_target: str = "vercel",
    workspace_path: str | None = None,
) -> dict[str, Any]:
    """Generate CI/CD pipeline configuration files.

    Args:
        provider: CI provider (github-actions)
        deploy_target: Deploy target (vercel, none)
        workspace_path: Project workspace path
    """
    ws = Path(workspace_path or settings.workspace_path).expanduser().resolve()

    if provider == "github-actions":
        if deploy_target == "vercel":
            template_key = "github-actions-vercel"
        else:
            template_key = "github-actions-basic"
    else:
        return {
            "status": "error",
            "error": f"Unknown CI provider '{provider}'. Supported: github-actions",
        }

    content = _TEMPLATES.get(template_key)
    if not content:
        # Try loading from file
        file_path = _CICD_TEMPLATES_ROOT / f"{template_key}.yml"
        if file_path.exists():
            content = file_path.read_text(encoding="utf-8")
        else:
            return {
                "status": "error",
                "error": f"Template '{template_key}' not found",
            }

    dest = ws / ".github" / "workflows" / "ci.yml"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(content, encoding="utf-8")

    logger.info(f"Generated CI/CD config: {dest}")
    return {
        "status": "ok",
        "files_written": [".github/workflows/ci.yml"],
        "provider": provider,
        "deploy_target": deploy_target,
        "note": "Set VERCEL_TOKEN, VERCEL_ORG_ID, VERCEL_PROJECT_ID in GitHub repo secrets"
        if deploy_target == "vercel" else "",
    }
