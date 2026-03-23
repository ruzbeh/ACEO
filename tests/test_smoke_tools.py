"""Tests for smoke_tools — post-deploy verification."""
import asyncio

import pytest

from aeco.tools.smoke_tools import smoke_test_api, smoke_test_url


@pytest.mark.asyncio
async def test_smoke_test_url_bad_host():
    """Test that a bad URL returns an error."""
    result = await smoke_test_url("http://this-domain-does-not-exist-aeco.invalid", timeout=5)
    assert result["status"] == "error"
    assert result["checks_passed"] == 0


@pytest.mark.asyncio
async def test_smoke_test_api_bad_host():
    """Test API smoke test with bad host."""
    result = await smoke_test_api(
        "http://this-domain-does-not-exist-aeco.invalid",
        endpoints=[{"path": "/", "method": "GET", "expected_status": 200}],
    )
    assert result["status"] == "partial"
    assert result["checks_failed"] >= 1
