"""Post-deploy smoke test tools — verify deployed apps are actually working."""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Default checks for smoke_test_url
DEFAULT_CHECKS = ["status_200", "has_content", "no_error_page"]


async def smoke_test_url(
    url: str,
    checks: list[str] | None = None,
    timeout: int = 30,
) -> dict[str, Any]:
    """Hit a URL and verify basic health.

    Args:
        url: Full URL to test (e.g. https://myapp.vercel.app)
        checks: List of checks to run. Options: status_200, has_content, no_error_page
        timeout: Request timeout in seconds
    """
    import httpx

    checks = checks or DEFAULT_CHECKS
    results: list[dict[str, Any]] = []
    passed = 0
    failed = 0

    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(url)

            if "status_200" in checks:
                ok = 200 <= response.status_code < 400
                results.append({
                    "check": "status_200",
                    "passed": ok,
                    "detail": f"Status {response.status_code}",
                })
                if ok:
                    passed += 1
                else:
                    failed += 1

            body = response.text

            if "has_content" in checks:
                ok = len(body.strip()) > 100
                results.append({
                    "check": "has_content",
                    "passed": ok,
                    "detail": f"Body length: {len(body)} chars",
                })
                if ok:
                    passed += 1
                else:
                    failed += 1

            if "no_error_page" in checks:
                error_signals = [
                    "Internal Server Error",
                    "500 Internal",
                    "Application Error",
                    "DEPLOYMENT_NOT_FOUND",
                    "MODULE_NOT_FOUND",
                    "Cannot find module",
                    "SyntaxError",
                    "ReferenceError",
                ]
                found_errors = [s for s in error_signals if s.lower() in body.lower()]
                ok = len(found_errors) == 0
                results.append({
                    "check": "no_error_page",
                    "passed": ok,
                    "detail": f"Error signals found: {found_errors}" if found_errors else "No error signals",
                })
                if ok:
                    passed += 1
                else:
                    failed += 1

    except httpx.TimeoutException:
        return {
            "status": "error",
            "error": f"Request timed out after {timeout}s",
            "url": url,
            "checks_passed": 0,
            "checks_failed": len(checks),
        }
    except httpx.RequestError as e:
        return {
            "status": "error",
            "error": f"Request failed: {e}",
            "url": url,
            "checks_passed": 0,
            "checks_failed": len(checks),
        }

    return {
        "status": "ok" if failed == 0 else "partial",
        "url": url,
        "checks_passed": passed,
        "checks_failed": failed,
        "details": results,
    }


async def smoke_test_api(
    base_url: str,
    endpoints: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Test multiple API endpoints for basic health.

    Args:
        base_url: Base URL (e.g. https://myapp.vercel.app)
        endpoints: List of endpoint configs: [{"path": "/api/health", "method": "GET", "expected_status": 200}]
    """
    import httpx

    if not endpoints:
        endpoints = [
            {"path": "/", "method": "GET", "expected_status": 200},
            {"path": "/api/health", "method": "GET", "expected_status": 200},
        ]

    results: list[dict[str, Any]] = []
    passed = 0
    failed = 0

    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        for ep in endpoints:
            path = ep.get("path", "/")
            method = ep.get("method", "GET").upper()
            expected = ep.get("expected_status", 200)
            url = f"{base_url.rstrip('/')}{path}"

            try:
                response = await client.request(method, url)
                ok = response.status_code == expected
                results.append({
                    "endpoint": f"{method} {path}",
                    "passed": ok,
                    "status": response.status_code,
                    "expected": expected,
                })
                if ok:
                    passed += 1
                else:
                    failed += 1
            except Exception as e:
                results.append({
                    "endpoint": f"{method} {path}",
                    "passed": False,
                    "error": str(e),
                })
                failed += 1

    return {
        "status": "ok" if failed == 0 else "partial",
        "base_url": base_url,
        "checks_passed": passed,
        "checks_failed": failed,
        "details": results,
    }
