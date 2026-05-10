"""Playwright browser tool — Charles's eyes on the web.

Spawns a Chromium instance (headless by default), navigates, scrapes content,
and tears down. Each call is self-contained — no persistent session yet (that
comes later with cookies/storage_state and a long-running browser).

Two tools today:
  - browse_url(url, wait_for=None) → page text
  - browser_screenshot(url, path=None) → screenshot saved to disk

Why now: M5 spec includes Playwright. The Master Operating Manual references
research, email checks, Gumroad listings, ContractorPro deployment monitoring
— all web-driven work that needs eyes-on-page beyond what curl can do.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from pathlib import Path

from core.tools import tool

log = logging.getLogger("charles.browser")

_DEFAULT_TIMEOUT = 30_000  # ms
_TEXT_CAP = 16_000  # chars; truncate huge pages

# Patterns that mean "this page is dead — there's no real content here." When
# detected, browse_url returns a single-line `[BLOCKED reason=... url=...]`
# header followed by a short snippet, instead of the full HTML dump. The
# dispatcher's post-call hook (core.tool_guards.post_call) reads the header
# and adds the URL to the per-conv block-list so future calls short-circuit.
#
# Order matters — first match wins. Specific phrases before generic ones.
_BLOCKED_PAGE_PATTERNS = (
    ("ResearchGate - Temporarily Unavailable", "site_unavailable"),
    ("Access denied", "access_denied"),
    ("Access Denied", "access_denied"),
    ("403 ERROR", "forbidden"),
    ("403 Forbidden", "forbidden"),
    ("HTTP 401", "unauthorized"),
    ("Just a moment...", "cloudflare_block"),
    ("Checking your browser before accessing", "cloudflare_block"),
    ("Please verify you are a human", "captcha_wall"),
    ("Page Not Found", "404"),
    ("Page not found", "404"),
    ("404 Error", "404"),
    ("404 Not Found", "404"),
    ("Sorry, the page you requested was not found", "404"),
    ("File Not Found", "404"),
    ("Temporarily Unavailable", "site_unavailable"),
    ("rate limit", "rate_limited"),
    ("Rate limit", "rate_limited"),
    ("Too many requests", "rate_limited"),
)


def _classify_blocked(title: str, body: str) -> tuple[str, str] | None:
    """Return (reason, evidence_snippet) if the page is blocked/dead, else None.

    Looks at the title + first 1.5KB of body — that's where every real-world
    block page surfaces its message. Avoids false positives from articles
    that legitimately discuss e.g. "404 errors" by anchoring on the first
    matched chunk.
    """
    head = (title + "\n" + body)[:1500]
    for phrase, reason in _BLOCKED_PAGE_PATTERNS:
        if phrase in head:
            # Pull a short evidence snippet around the matched phrase
            idx = head.find(phrase)
            start = max(0, idx - 30)
            end = min(len(head), idx + len(phrase) + 80)
            snippet = head[start:end].strip().replace("\n", " ")
            return reason, snippet
    return None


def _async(coro):
    """Run an async coroutine to completion from a sync caller."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Caller is async (e.g. inside the Telegram channel) — run in nested loop
            return asyncio.run_coroutine_threadsafe(coro, loop).result()
    except RuntimeError:
        pass
    return asyncio.run(coro)


@tool(
    name="browse_url",
    summary="Open a URL in headless Chromium and return the visible page text. Handles JavaScript-rendered pages that curl can't read. Use when you need to actually see what's on a website.",
    triggers=("browse", "open url", "fetch web", "what's on the page"),
    schema={
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "Full URL including https://"},
            "wait_for": {
                "type": "string",
                "description": "Optional CSS selector to wait for before extracting text (e.g. 'article', '#main'). Default: just wait for load.",
            },
        },
        "required": ["url"],
    },
)
def browse_url(url: str, wait_for: str | None = None) -> str:
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    async def _run() -> tuple[str, str]:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                page = await browser.new_page()
                await page.goto(url, timeout=_DEFAULT_TIMEOUT, wait_until="domcontentloaded")
                if wait_for:
                    try:
                        await page.wait_for_selector(wait_for, timeout=_DEFAULT_TIMEOUT)
                    except Exception:  # noqa: BLE001 — selector miss is non-fatal
                        log.warning("wait_for selector %r not found within timeout", wait_for)
                text = await page.evaluate("() => document.body.innerText")
                title = await page.title()
            finally:
                await browser.close()
        return title or "", text or ""

    try:
        title, body = _async(_run())
    except Exception as e:  # noqa: BLE001
        return f"[error] {type(e).__name__}: {e}"

    # Detect blocked / dead pages BEFORE returning the body. The structured
    # `[BLOCKED reason=... url=...]` header lets the dispatcher remember
    # this URL is poisoned for the current conv and short-circuit any
    # future calls. See core/tool_guards.py.
    blocked = _classify_blocked(title, body)
    if blocked:
        reason, evidence = blocked
        return (
            f"[BLOCKED reason={reason} url={url}]\n"
            f"This page is dead — no real content. Evidence: {evidence!r}\n"
            f"Don't retry it. Pick a different source or skip this item."
        )

    out = f"# {title}\n\n{body}".strip()
    if len(out) > _TEXT_CAP:
        out = out[:_TEXT_CAP] + f"\n\n... [truncated, full page was {len(out)} chars]"
    return out


@tool(
    name="browser_screenshot",
    summary="Open a URL in headless Chromium and save a full-page screenshot to disk. Returns the path on success.",
    triggers=("screenshot", "screencap", "snap", "capture page"),
    schema={
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "Full URL including https://"},
            "path": {
                "type": "string",
                "description": "Where to save the .png. Defaults to /tmp/charles_screenshot_<uuid>.png.",
            },
        },
        "required": ["url"],
    },
)
def browser_screenshot(url: str, path: str | None = None) -> str:
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    out_path = Path(path) if path else Path(f"/tmp/charles_screenshot_{uuid.uuid4().hex[:8]}.png")

    async def _run() -> str:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                page = await browser.new_page()
                await page.goto(url, timeout=_DEFAULT_TIMEOUT, wait_until="domcontentloaded")
                await page.screenshot(path=str(out_path), full_page=True)
            finally:
                await browser.close()
        return f"saved screenshot to {out_path}"

    try:
        return _async(_run())
    except Exception as e:  # noqa: BLE001
        return f"[error] {type(e).__name__}: {e}"
