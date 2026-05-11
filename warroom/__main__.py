"""Entrypoint: `python -m warroom` runs the server on 127.0.0.1:8765.

Production deployment is via the launchd plist at launchd/com.charles.warroom.plist
(install via scripts/install_warroom.sh, NOT auto-enabled — operator runs that
manually after Tailscale + auth setup).
"""
from __future__ import annotations

import logging
import os

import uvicorn

def _sweep_stale_progress_rows() -> int:
    """On startup, delete any orphan `role='progress'` rows in the
    conversations table older than 60 seconds.

    These rows are written when a tool is in flight; they're supposed to be
    cleared when the tool returns. But if warroom is killed mid-tool (e.g.
    launchctl kickstart -k or crash), the cleanup never runs and the row
    persists in sqlite. The UI reads from sqlite and shows the stale
    "Runnin' shell …" forever. Clear them on every fresh start.
    """
    import sqlite3
    from pathlib import Path
    db = Path("/Users/home/charles/workspace/memory.db")
    if not db.exists():
        return 0
    try:
        with sqlite3.connect(str(db)) as c:
            cur = c.execute(
                "DELETE FROM conversations WHERE role='progress' "
                "AND created_at < datetime('now', '-60 seconds')"
            )
            return cur.rowcount or 0
    except Exception as e:  # noqa: BLE001
        logging.getLogger("warroom").warning("stale-progress sweep failed: %s", e)
        return 0


if __name__ == "__main__":
    logging.basicConfig(
        level=os.environ.get("WARROOM_LOG_LEVEL", "INFO"),
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    host = os.environ.get("WARROOM_HOST", "127.0.0.1")
    port = int(os.environ.get("WARROOM_PORT", "8765"))
    log = logging.getLogger("warroom")
    swept = _sweep_stale_progress_rows()
    if swept:
        log.info("startup: swept %d stale progress rows from prior crash", swept)
    log.info("starting War Room server at %s:%d (localhost-only by default)", host, port)
    uvicorn.run(
        "warroom.server:app",
        host=host,
        port=port,
        log_level=os.environ.get("WARROOM_LOG_LEVEL", "info").lower(),
        access_log=True,
    )
