"""Importing this package registers all tools via @tool decorators.

Every module here MUST be listed below or its @tool decorators never run and
the dispatcher reports "no such tool". 2026-05-09 audit caught 5 modules
silently absent (email_triage, documents, calendar, memory_consolidation,
open_requests), losing 8 tools Charles already had source for.
"""
from . import (  # noqa: F401
    browser,
    calendar,
    call_claude,
    cc_build,
    documents,
    email_triage,
    filesystem,
    gmail,
    goals,
    governance,
    imessage,
    john_prefs,
    learning,
    memory,
    memory_consolidation,
    notify,
    open_requests,
    projects,
    reflection,
    scheduler,
    search,
    self_modify,
    sentiment,
    shell,
    skills,
    sunday_test,
    tasks,
    topics,
    time,
    vibe,
    watchdog,
    weather,
)
