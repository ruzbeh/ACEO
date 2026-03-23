"""Browser tools — give agents eyes via Playwright headless Chromium.

Agents can screenshot pages, click elements, fill forms, read console errors,
and navigate — enabling visual QA and dev preview loops.

Uses a shared browser context per workspace to avoid cold-start overhead.
"""
from __future__ import annotations

import asyncio
import base64
import logging
from pathlib import Path
from typing import Any

from aeco.config import settings

logger = logging.getLogger(__name__)

# Shared browser instance (lazy-init)
_browser = None
_playwright = None
_contexts: dict[str, Any] = {}  # workspace_path → BrowserContext


async def _ensure_browser():
    """Lazy-init Playwright browser (shared across all tool calls)."""
    global _browser, _playwright
    if _browser is not None:
        return _browser

    from playwright.async_api import async_playwright
    _playwright = await async_playwright().start()
    _browser = await _playwright.chromium.launch(headless=True)
    logger.info("Playwright browser launched (headless Chromium)")
    return _browser


async def _get_context(workspace_key: str = "default"):
    """Get or create a browser context for isolation."""
    if workspace_key in _contexts:
        return _contexts[workspace_key]
    browser = await _ensure_browser()
    ctx = await browser.new_context(
        viewport={"width": 1280, "height": 720},
        ignore_https_errors=True,
    )
    _contexts[workspace_key] = ctx
    return ctx


async def browser_screenshot(
    url: str,
    save_path: str | None = None,
    full_page: bool = False,
    wait_for: str | None = None,
    workspace_path: str | None = None,
) -> dict[str, Any]:
    """Take a screenshot of a web page.

    Args:
        url: Full URL to screenshot (e.g. http://localhost:3000)
        save_path: Optional path to save PNG (relative to workspace). If None, returns base64.
        full_page: Capture full scrollable page, not just viewport
        wait_for: CSS selector to wait for before screenshot (e.g. 'h1', '.loaded')
        workspace_path: Workspace for file saving
    """
    try:
        ctx = await _get_context(workspace_path or "default")
        page = await ctx.new_page()

        # Capture console errors
        console_errors: list[str] = []
        page.on("console", lambda msg: console_errors.append(f"[{msg.type}] {msg.text}") if msg.type in ("error", "warning") else None)

        try:
            await page.goto(url, wait_until="networkidle", timeout=30000)
        except Exception:
            # Fallback: try with just load event
            await page.goto(url, wait_until="load", timeout=30000)

        if wait_for:
            try:
                await page.wait_for_selector(wait_for, timeout=10000)
            except Exception:
                logger.debug(f"wait_for selector '{wait_for}' not found, continuing")

        # Small delay for rendering
        await asyncio.sleep(0.5)

        screenshot_bytes = await page.screenshot(full_page=full_page)
        title = await page.title()
        page_url = page.url

        await page.close()

        result: dict[str, Any] = {
            "status": "ok",
            "url": page_url,
            "title": title,
            "console_errors": console_errors[:20],
            "viewport": "1280x720",
        }

        if save_path:
            ws = Path(workspace_path or settings.workspace_path).expanduser().resolve()
            out = ws / save_path
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(screenshot_bytes)
            result["saved_to"] = str(out)
            result["size_bytes"] = len(screenshot_bytes)
        else:
            result["screenshot_base64"] = base64.b64encode(screenshot_bytes).decode()
            result["size_bytes"] = len(screenshot_bytes)

        if console_errors:
            result["has_errors"] = True
            result["error_count"] = len(console_errors)

        return result

    except Exception as e:
        return {"status": "error", "error": str(e), "url": url}


async def browser_click(
    url: str,
    selector: str,
    wait_after: float = 1.0,
    workspace_path: str | None = None,
) -> dict[str, Any]:
    """Navigate to a URL and click an element.

    Args:
        url: Page URL
        selector: CSS selector of element to click (e.g. 'button.submit', '#login-btn')
        wait_after: Seconds to wait after click for navigation/rendering
    """
    try:
        ctx = await _get_context(workspace_path or "default")
        page = await ctx.new_page()

        await page.goto(url, wait_until="networkidle", timeout=30000)
        await page.click(selector, timeout=10000)
        await asyncio.sleep(wait_after)

        new_url = page.url
        title = await page.title()
        screenshot_bytes = await page.screenshot()
        await page.close()

        return {
            "status": "ok",
            "clicked": selector,
            "url_before": url,
            "url_after": new_url,
            "navigated": url != new_url,
            "title": title,
            "screenshot_base64": base64.b64encode(screenshot_bytes).decode(),
        }
    except Exception as e:
        return {"status": "error", "error": str(e), "url": url, "selector": selector}


async def browser_fill(
    url: str,
    selector: str,
    value: str,
    submit_selector: str | None = None,
    workspace_path: str | None = None,
) -> dict[str, Any]:
    """Navigate to a URL, fill a form field, and optionally submit.

    Args:
        url: Page URL
        selector: CSS selector of input to fill (e.g. 'input[name=email]')
        value: Value to type
        submit_selector: Optional CSS selector of submit button to click after filling
    """
    try:
        ctx = await _get_context(workspace_path or "default")
        page = await ctx.new_page()

        await page.goto(url, wait_until="networkidle", timeout=30000)
        await page.fill(selector, value, timeout=10000)

        if submit_selector:
            await page.click(submit_selector, timeout=10000)
            await asyncio.sleep(1.5)

        new_url = page.url
        title = await page.title()
        screenshot_bytes = await page.screenshot()
        await page.close()

        return {
            "status": "ok",
            "filled": selector,
            "value": value[:50],
            "submitted": submit_selector is not None,
            "url_after": new_url,
            "title": title,
            "screenshot_base64": base64.b64encode(screenshot_bytes).decode(),
        }
    except Exception as e:
        return {"status": "error", "error": str(e), "url": url, "selector": selector}


async def browser_get_text(
    url: str,
    selector: str | None = None,
    workspace_path: str | None = None,
) -> dict[str, Any]:
    """Get text content from a page or specific element.

    Args:
        url: Page URL
        selector: Optional CSS selector. If None, returns full page text.
    """
    try:
        ctx = await _get_context(workspace_path or "default")
        page = await ctx.new_page()

        console_errors: list[str] = []
        page.on("console", lambda msg: console_errors.append(f"[{msg.type}] {msg.text}") if msg.type in ("error", "warning") else None)

        await page.goto(url, wait_until="networkidle", timeout=30000)

        if selector:
            element = await page.query_selector(selector)
            if element:
                text = await element.inner_text()
            else:
                text = f"Selector '{selector}' not found on page"
        else:
            text = await page.inner_text("body")

        title = await page.title()
        await page.close()

        return {
            "status": "ok",
            "url": url,
            "title": title,
            "text": text[:5000],
            "text_length": len(text),
            "console_errors": console_errors[:20],
        }
    except Exception as e:
        return {"status": "error", "error": str(e), "url": url}


async def browser_console_errors(
    url: str,
    wait_seconds: float = 3.0,
    workspace_path: str | None = None,
) -> dict[str, Any]:
    """Load a page and collect all console errors and warnings.

    Args:
        url: Page URL
        wait_seconds: How long to wait for errors to appear
    """
    try:
        ctx = await _get_context(workspace_path or "default")
        page = await ctx.new_page()

        messages: list[dict[str, str]] = []
        page.on("console", lambda msg: messages.append({
            "type": msg.type,
            "text": msg.text,
        }))

        page_errors: list[str] = []
        page.on("pageerror", lambda err: page_errors.append(str(err)))

        try:
            await page.goto(url, wait_until="networkidle", timeout=30000)
        except Exception:
            await page.goto(url, wait_until="load", timeout=30000)

        await asyncio.sleep(wait_seconds)

        title = await page.title()
        await page.close()

        errors = [m for m in messages if m["type"] in ("error", "warning")]
        return {
            "status": "ok",
            "url": url,
            "title": title,
            "total_messages": len(messages),
            "errors": errors[:30],
            "page_errors": page_errors[:10],
            "has_errors": len(errors) > 0 or len(page_errors) > 0,
        }
    except Exception as e:
        return {"status": "error", "error": str(e), "url": url}


async def browser_close(workspace_path: str | None = None) -> dict[str, Any]:
    """Close browser context for a workspace (cleanup)."""
    key = workspace_path or "default"
    if key in _contexts:
        await _contexts[key].close()
        del _contexts[key]
        return {"status": "ok", "message": f"Browser context closed for {key}"}
    return {"status": "ok", "message": "No browser context to close"}


async def browser_close_all() -> dict[str, Any]:
    """Close all browser contexts and the browser itself."""
    global _browser, _playwright
    for key in list(_contexts.keys()):
        await _contexts[key].close()
    _contexts.clear()
    if _browser:
        await _browser.close()
        _browser = None
    if _playwright:
        await _playwright.stop()
        _playwright = None
    return {"status": "ok", "message": "All browser resources closed"}
