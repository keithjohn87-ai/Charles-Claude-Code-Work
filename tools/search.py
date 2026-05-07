"""Web search tools.

Two-tier strategy per John's direction (2026-05-07 morning):
  PRIMARY:  DuckDuckGo HTML — no auth, no rate limits, no JS required.
  FALLBACK: Google with 2CAPTCHA-solved CAPTCHAs when DuckDuckGo is insufficient.

The 2CAPTCHA service costs ~$1 per 1000 solves. Use the fallback sparingly —
the migration's spec says "Charles must self-correct, self-repair, and move
forward" — burning budget on a CAPTCHA when DuckDuckGo would have answered is
not self-correction, it's laziness. Start with DDG; only escalate to Google
if the DDG result is genuinely empty or off-target.
"""
from __future__ import annotations

import logging
import os
import re
import urllib.parse

import httpx

from core.tools import tool

log = logging.getLogger("charles.search")


def _parse_ddg_html(html: str, max_results: int) -> list[dict]:
    """Pull title/url/snippet from DuckDuckGo HTML results page."""
    results = []
    # Each result is <div class="result"> ... <a class="result__a" href="...">title</a>
    # ... <a class="result__snippet">snippet</a> ...
    # Or for newer DDG pages: <a class="result__a">...</a> + result__snippet
    pattern = re.compile(
        r'<a[^>]+class="[^"]*result__a[^"]*"[^>]+href="([^"]+)"[^>]*>(.*?)</a>'
        r'(?:.*?<a[^>]+class="[^"]*result__snippet[^"]*"[^>]*>(.*?)</a>)?',
        re.DOTALL,
    )
    for m in pattern.finditer(html):
        url = urllib.parse.unquote(m.group(1))
        # DDG wraps organic results in /l/?uddg= — pull out the actual target
        if "duckduckgo.com/l/?uddg=" in url:
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
            real = qs.get("uddg", [url])[0]
            url = urllib.parse.unquote(real)
        # Skip ads: /y.js? redirector + Bing affiliate trackers
        if "duckduckgo.com/y.js" in url or "bing.com/aclick" in url:
            continue
        title = re.sub(r"<[^>]+>", "", m.group(2) or "").strip()
        snippet = re.sub(r"<[^>]+>", "", m.group(3) or "").strip()
        if title and url:
            results.append({"title": title, "url": url, "snippet": snippet})
        if len(results) >= max_results:
            break
    return results


@tool(
    name="search_web",
    summary="Search the web via DuckDuckGo (primary) and return top results with titles, URLs, snippets. Use this BEFORE browse_url when you need to discover relevant pages — saves a separate scrape step. Use 'google' source only when DDG returns nothing useful (will cost ~$0.001 per CAPTCHA solve via 2CAPTCHA).",
    triggers=("search web", "search for", "find pages about", "google", "look up", "search engine"),
    schema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "What you're searching for. Plain language; quotes for phrases."},
            "max_results": {"type": "integer", "description": "How many results to return (default 8, max 20).", "default": 8},
            "source": {"type": "string", "description": "'duckduckgo' (default, free) or 'google' (uses 2CAPTCHA budget).", "default": "duckduckgo"},
        },
        "required": ["query"],
    },
)
def search_web(query: str, max_results: int = 8, source: str = "duckduckgo") -> str:
    max_results = max(1, min(int(max_results), 20))
    source = source.lower()

    if source in ("duckduckgo", "ddg", "default"):
        return _search_ddg(query, max_results)
    if source == "google":
        return _search_google(query, max_results)
    return f"[error] unknown source: {source!r}"


def _search_ddg(query: str, max_results: int) -> str:
    url = "https://html.duckduckgo.com/html/"
    try:
        r = httpx.post(
            url,
            data={"q": query},
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
                ),
            },
            follow_redirects=True,
            timeout=15,
        )
        r.raise_for_status()
    except Exception as e:  # noqa: BLE001
        return f"[error] DDG fetch failed: {type(e).__name__}: {e}"
    results = _parse_ddg_html(r.text, max_results)
    if not results:
        return "[no results from DuckDuckGo — try a broader query, or source='google']"
    out = [f"# DuckDuckGo: {query}", ""]
    for i, h in enumerate(results, 1):
        out.append(f"{i}. {h['title']}")
        out.append(f"   {h['url']}")
        if h["snippet"]:
            out.append(f"   {h['snippet']}")
    return "\n".join(out)


def _search_google(query: str, max_results: int) -> str:
    """Google search with 2CAPTCHA fallback for bot-detection challenges.

    Naive direct fetch first; if Google returns the 'unusual traffic' or sorry
    page, queue a CAPTCHA solve via 2CAPTCHA and retry. v0 simplification:
    when CAPTCHA is encountered, return the failure message + CAPTCHA URL so
    Charles can decide whether to escalate. Real automated CAPTCHA solving
    requires the recaptcha sitekey from the page — left as v1 work.
    """
    api_key = os.environ.get("TWOCAPTCHA_API_KEY")
    encoded = urllib.parse.quote(query)
    url = f"https://www.google.com/search?q={encoded}&num={max_results}"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }
    try:
        r = httpx.get(url, headers=headers, follow_redirects=True, timeout=15)
        r.raise_for_status()
    except Exception as e:  # noqa: BLE001
        return f"[error] Google fetch failed: {type(e).__name__}: {e}"

    body = r.text.lower()
    if "/sorry" in r.url.path or "unusual traffic" in body or "captcha" in body[:5000]:
        if not api_key:
            return (
                "[google rate-limited; no TWOCAPTCHA_API_KEY in env — falling back] "
                f"Try DDG with the same query: search_web({query!r}, source='duckduckgo')"
            )
        return (
            "[google rate-limited; CAPTCHA solving requires sitekey from page render. "
            "v0 fallback: switch to DDG, OR open the URL via browse_url, extract the "
            "sitekey from the <div class='g-recaptcha' data-sitekey='...'> attribute, "
            "then call solve_recaptcha(sitekey=..., page_url=...) and retry. CAPTCHA "
            "page is at: " + str(r.url) + "]"
        )

    # Parse a basic Google results format. The HTML is JS-heavy; this is a
    # best-effort regex that catches the "h3 + cite" pattern.
    results = []
    for m in re.finditer(
        r'<a[^>]+href="(/url\?q=)?(https?://[^"&]+)"[^>]*>.*?<h3[^>]*>(.*?)</h3>',
        r.text, re.DOTALL,
    ):
        u = m.group(2)
        title = re.sub(r"<[^>]+>", "", m.group(3)).strip()
        if title and u:
            results.append({"title": title, "url": u, "snippet": ""})
        if len(results) >= max_results:
            break
    if not results:
        return "[google: parse failed — page format may have changed; falling back to DDG recommended]"
    out = [f"# Google: {query}", ""]
    for i, h in enumerate(results, 1):
        out.append(f"{i}. {h['title']}")
        out.append(f"   {h['url']}")
    return "\n".join(out)


@tool(
    name="solve_recaptcha",
    summary="Solve a Google reCAPTCHA v2 via the 2CAPTCHA service (~$0.001 per solve). Use ONLY when search_web/browse_url hits a CAPTCHA wall and you've extracted the sitekey from the page. Returns a token string you submit back to the page.",
    triggers=("solve captcha", "2captcha", "recaptcha"),
    schema={
        "type": "object",
        "properties": {
            "sitekey": {"type": "string", "description": "Google reCAPTCHA sitekey from the page (data-sitekey attribute on <div class='g-recaptcha'>)."},
            "page_url": {"type": "string", "description": "Full URL of the page where the CAPTCHA appears."},
        },
        "required": ["sitekey", "page_url"],
    },
)
def solve_recaptcha(sitekey: str, page_url: str) -> str:
    api_key = os.environ.get("TWOCAPTCHA_API_KEY")
    if not api_key:
        return "[error] TWOCAPTCHA_API_KEY missing from environment"
    try:
        from twocaptcha import TwoCaptcha
        solver = TwoCaptcha(api_key)
        result = solver.recaptcha(sitekey=sitekey, url=page_url)
        return f"solved: token={result.get('code')[:60]}…"
    except Exception as e:  # noqa: BLE001
        return f"[error] {type(e).__name__}: {e}"
