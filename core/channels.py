"""Two-channel conversation routing.

Charles operates in TWO conversations, distinct from internal scheduling:

  JOHN_CHARLES  — relational thread: John's UI/Telegram/iMessage messages and
                  Charles's replies. Voice-rich. Every turn matters.

  CHARLES_LOG   — operational/autonomous stream: goal-tick advances,
                  heartbeat-driven work, watchdog (Boss Hog) interventions,
                  Sunday Test runs. Plain English so John can skim it like
                  a Slack channel.

Goals/heartbeats/etc. are scheduling INTERNALS — they shouldn't each be a
separate "conversation" from Charles's POV. The goals table's `notes` column
holds per-goal continuity; this module's job is to make sure the chronological
RECORD of all that work lands in one human-readable channel John can browse.
"""
from __future__ import annotations

JOHN_CHARLES = "8455750177"  # the established Telegram chat id for John's primary thread
CHARLES_LOG = "charles_log"

# Conv_id prefixes that represent autonomous (non-user) work. Anything matching
# these collapses into CHARLES_LOG. Anything else collapses into JOHN_CHARLES.
_OPERATIONAL_PREFIXES = (
    "goal:",        # goal-tick respond chains (heartbeat-driven)
    "heartbeat:",   # scheduled-task firings
    "sunday_test",  # the periodic Sunday Test harness
    "watchdog",     # behavior watchdog interventions / reports
    "boss_hog",     # explicit Boss Hog reports (future)
)


def normalize(conv_id: str | None) -> str:
    """Map any conv_id to one of the two real channels.

    - None / empty       → JOHN_CHARLES   (default to the user thread)
    - JOHN_CHARLES       → JOHN_CHARLES   (already there)
    - CHARLES_LOG        → CHARLES_LOG    (already there)
    - operational prefix → CHARLES_LOG    (goal:42, heartbeat:7, etc.)
    - anything else      → JOHN_CHARLES   (any UI/Telegram leftover)
    """
    if not conv_id:
        return JOHN_CHARLES
    if conv_id == JOHN_CHARLES or conv_id == CHARLES_LOG:
        return conv_id
    if conv_id.startswith(_OPERATIONAL_PREFIXES):
        return CHARLES_LOG
    return JOHN_CHARLES


def is_operational(conv_id: str | None) -> bool:
    """True if this conv_id belongs in the operational/Charles_Log stream."""
    return normalize(conv_id) == CHARLES_LOG
