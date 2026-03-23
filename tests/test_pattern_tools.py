"""Tests for pattern_tools — reusable UI/API snippet library."""
import asyncio
from pathlib import Path

import pytest

from aeco.tools.pattern_tools import pattern_list, pattern_use


def test_pattern_list():
    result = asyncio.get_event_loop().run_until_complete(pattern_list())
    assert result["status"] == "ok"
    assert isinstance(result["patterns"], list)


def test_pattern_use_unknown(tmp_path):
    result = asyncio.get_event_loop().run_until_complete(
        pattern_use("nonexistent-pattern", "components/Foo.tsx", workspace_path=str(tmp_path))
    )
    assert result["status"] == "error"
    assert "nonexistent-pattern" in result["error"]
