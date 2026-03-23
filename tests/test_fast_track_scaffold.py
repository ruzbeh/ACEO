"""Tests for the extended fast-track workflow with scaffold + verify."""
import pytest

from aeco.orchestrator.fast_track_state import FastTrackState
from aeco.orchestrator.fast_track_graph import _post_architect, _post_ship


def test_post_architect_routes_to_scaffold_for_new_project():
    state: FastTrackState = {
        "request_id": "test",
        "request": "Build an app",
        "workspace_path": "/tmp",
        "project_context": None,
        "scaffold_result": None,
        "is_new_project": True,
        "stack": "nextjs-supabase-stripe",
        "features": ["auth"],
        "project_name": "test-app",
        "plan": {"approach": "test"},
        "escalate_to_initiative": False,
        "build_result": None,
        "files_changed": [],
        "git_result": None,
        "deploy_result": None,
        "preview_url": None,
        "smoke_result": None,
        "current_phase": "scaffold",
        "budget_spent": 0.0,
        "budget_remaining": 20.0,
        "decisions": [],
        "messages": [],
        "errors": [],
    }
    assert _post_architect(state) == "scaffold"


def test_post_architect_routes_to_build_for_existing_project():
    state: FastTrackState = {
        "request_id": "test",
        "request": "Fix a bug",
        "workspace_path": "/tmp",
        "project_context": None,
        "scaffold_result": None,
        "is_new_project": False,
        "stack": None,
        "features": [],
        "project_name": None,
        "plan": {"approach": "test"},
        "escalate_to_initiative": False,
        "build_result": None,
        "files_changed": [],
        "git_result": None,
        "deploy_result": None,
        "preview_url": None,
        "smoke_result": None,
        "current_phase": "build",
        "budget_spent": 0.0,
        "budget_remaining": 20.0,
        "decisions": [],
        "messages": [],
        "errors": [],
    }
    assert _post_architect(state) == "build"


def test_post_ship_routes_to_verify_when_preview_url():
    state = {"preview_url": "https://example.vercel.app"}
    assert _post_ship(state) == "verify"


def test_post_ship_routes_to_end_when_no_preview():
    from langgraph.graph import END
    state = {"preview_url": None}
    assert _post_ship(state) == END
