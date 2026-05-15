"""Three-channel conversation routing.

Charles operates in THREE conversations, distinct from internal scheduling:

  JOHN_CHARLES  — relational thread: John's UI/Telegram/iMessage messages and
                  Charles's replies. Voice-rich. Every turn matters.

  CHARLES_LOG   — operational/autonomous stream: goal-tick advances,
                  heartbeat-driven work, watchdog (Boss Hog) interventions,
                  Sunday Test runs. Plain English so John can skim it like
                  a Slack channel.

  CLAUDE_CODE   — builder dev-notes from Claude Code (the harness AI that
                  helps John build Charles). NOT John talking. These are
                  technical hand-offs: "I changed core/X.py, here's why";
                  "your last reflection had bug Y, fix is Z"; "smoke test
                  for the new async tool primitive passed". Charles reads
                  them on the next heartbeat poll and integrates the info
                  (memory facts, behavior tweaks, retries) without needing
                  to reply with full voice. Polled every 60s by the
                  heartbeat (see core/heartbeat._poll_claude_code).

Goals/heartbeats/etc. are scheduling INTERNALS — they shouldn't each be a
separate "conversation" from Charles's POV. The goals table's `notes` column
holds per-goal continuity; this module's job is to make sure the chronological
RECORD of all that work lands in one of the three human-readable channels.
"""
from __future__ import annotations

JOHN_CHARLES = "8455750177"  # the established Telegram chat id for John's primary thread
CHARLES_LOG = "charles_log"
CLAUDE_CODE = "claude_code"

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
    """Map any conv_id to one of the three real channels.

    - None / empty       → JOHN_CHARLES   (default to the user thread)
    - JOHN_CHARLES       → JOHN_CHARLES   (already there)
    - CHARLES_LOG        → CHARLES_LOG    (already there)
    - CLAUDE_CODE        → CLAUDE_CODE    (already there)
    - operational prefix → CHARLES_LOG    (goal:42, heartbeat:7, etc.)
    - anything else      → JOHN_CHARLES   (any UI/Telegram leftover)
    """
    if not conv_id:
        return JOHN_CHARLES
    if conv_id in (JOHN_CHARLES, CHARLES_LOG, CLAUDE_CODE):
        return conv_id
    if conv_id.startswith(_OPERATIONAL_PREFIXES):
        return CHARLES_LOG
    return JOHN_CHARLES


def is_operational(conv_id: str | None) -> bool:
    """True if this conv_id belongs in the operational/Charles_Log stream."""
    return normalize(conv_id) == CHARLES_LOG


def is_builder_notes(conv_id: str | None) -> bool:
    """True if this conv_id is the Claude Code builder channel.

    Builder messages don't need voice replies and shouldn't trigger John-facing
    notifications. Charles reads them, integrates, then logs a short
    acknowledgment turn so the channel has a record of receipt.
    """
    return normalize(conv_id) == CLAUDE_CODE
