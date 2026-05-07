"""Weather tool — fetches current conditions + short forecast via wttr.in (no API key required).

Format is the standard wttr.in 'format' output, optimized for short Telegram messages.
"""
from __future__ import annotations

import logging
import urllib.parse

import httpx

from core.tools import tool

log = logging.getLogger("charles.weather")


@tool(
    name="get_weather",
    summary="Get current weather + short forecast for a location via wttr.in. No API key required. Returns a compact human-readable string.",
    triggers=("weather", "forecast", "temperature", "rain", "snow", "what's it like outside"),
    schema={
        "type": "object",
        "properties": {
            "location": {
                "type": "string",
                "description": "City + state/country, airport code, or zip. e.g. 'Dundalk, MD', 'BWI', '21222'.",
            },
            "format": {
                "type": "string",
                "description": "wttr.in format spec. Default is a 1-line summary; 'full' = multi-day forecast.",
                "default": "%l: %C, %t (feels %f), wind %w, humidity %h, %p precip — sunrise %S, sunset %s",
            },
        },
        "required": ["location"],
    },
)
def get_weather(
    location: str,
    format: str = "%l: %C, %t (feels %f), wind %w, humidity %h, %p precip — sunrise %S, sunset %s",
) -> str:
    loc_q = urllib.parse.quote(location.strip())
    if format == "full":
        url = f"https://wttr.in/{loc_q}?2nFQ"
    else:
        fmt_q = urllib.parse.quote(format)
        url = f"https://wttr.in/{loc_q}?format={fmt_q}"
    try:
        r = httpx.get(url, timeout=10, headers={"User-Agent": "curl/8"})
        r.raise_for_status()
        text = r.text.strip()
    except Exception as e:  # noqa: BLE001
        log.exception("weather fetch failed")
        return f"[error] {type(e).__name__}: {e}"
    if not text:
        return "[error] empty response from wttr.in"
    return text
