"""Tests for scaffold_tools — project template generation."""
import asyncio
import os
import tempfile
from pathlib import Path

import pytest

from aeco.tools.scaffold_tools import scaffold_list_templates, scaffold_project


@pytest.fixture
def tmp_workspace(tmp_path):
    return str(tmp_path)


def test_scaffold_list_templates():
    result = asyncio.get_event_loop().run_until_complete(scaffold_list_templates())
    assert result["status"] == "ok"
    assert isinstance(result["templates"], list)
    # Should have at least the nextjs-supabase-stripe template
    names = [t["name"] for t in result["templates"]]
    assert "nextjs-supabase-stripe" in names


def test_scaffold_project_creates_files(tmp_workspace):
    result = asyncio.get_event_loop().run_until_complete(
        scaffold_project("test-app", "nextjs-supabase-stripe", workspace_path=tmp_workspace)
    )
    assert result["status"] == "ok"
    assert result["project_name"] == "test-app"
    assert result["stack"] == "nextjs-supabase-stripe"
    assert len(result["files_created"]) > 5

    # Check key files exist
    project_dir = Path(tmp_workspace) / "test-app"
    assert project_dir.exists()
    assert (project_dir / "package.json").exists()


def test_scaffold_project_variable_substitution(tmp_workspace):
    result = asyncio.get_event_loop().run_until_complete(
        scaffold_project("My Cool App", "nextjs-supabase-stripe", workspace_path=tmp_workspace)
    )
    assert result["status"] == "ok"

    project_dir = Path(tmp_workspace) / "my-cool-app"
    pkg = (project_dir / "package.json").read_text()
    assert "my-cool-app" in pkg  # slug substituted


def test_scaffold_unknown_stack(tmp_workspace):
    result = asyncio.get_event_loop().run_until_complete(
        scaffold_project("test", "nonexistent-stack", workspace_path=tmp_workspace)
    )
    assert result["status"] == "error"
    assert "nonexistent-stack" in result["error"]


def test_scaffold_with_features(tmp_workspace):
    result = asyncio.get_event_loop().run_until_complete(
        scaffold_project("test-app", "nextjs-supabase-stripe", features=["auth", "payments"], workspace_path=tmp_workspace)
    )
    assert result["status"] == "ok"
    assert "auth" in result["features"]
    assert "payments" in result["features"]
    # Feature files should be in files_created
    assert len(result["files_created"]) > 5
