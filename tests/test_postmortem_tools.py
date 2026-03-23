"""Tests for postmortem git snapshot and screenshot helpers."""
import pytest

from aeco.tools.postmortem_tools import git_workspace_snapshot


@pytest.mark.asyncio
async def test_git_workspace_snapshot_not_a_repo(tmp_path):
    import aeco.tools.postmortem_tools as pt

    out = await git_workspace_snapshot(str(tmp_path), max_diff_chars=1000)
    assert out["status"] == "not_a_git_repo"


@pytest.mark.asyncio
async def test_git_workspace_snapshot_with_repo(tmp_path):
    import subprocess

    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "t@test.local"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "test"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    (tmp_path / "a.txt").write_text("hello")
    subprocess.run(["git", "add", "a.txt"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    (tmp_path / "a.txt").write_text("hello world")

    out = await git_workspace_snapshot(str(tmp_path), max_diff_chars=5000)
    assert out["status"] == "ok"
    assert "hello world" in out.get("git_diff_excerpt", "") or "hello" in out.get("git_diff_excerpt", "")
