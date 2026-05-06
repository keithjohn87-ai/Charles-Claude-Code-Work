"""Text → speech → Telegram-compatible voice note.

Local pipeline: macOS `say` (built-in neural voices) → ffmpeg → .ogg/Opus.
Zero cloud calls, zero extra deps beyond what's already on the box.

Default voice: Daniel (British male). Override via `CHARLES_VOICE` env var.
List installed voices with `say -v ?`.
"""
from __future__ import annotations

import logging
import os
import subprocess
import tempfile
import uuid
from pathlib import Path

log = logging.getLogger("charles.speak")

DEFAULT_VOICE = os.environ.get("CHARLES_VOICE", "Daniel")
SPEAK_RATE = int(os.environ.get("CHARLES_SPEAK_RATE", "180"))  # words/min; macOS default is ~175


def speak_to_ogg(text: str, out_dir: str | Path = "/tmp", voice: str | None = None) -> Path:
    """Synthesize speech and return path to a .ogg file Telegram will accept as a voice note.

    Caller is responsible for deleting the file when done.
    """
    if not text or not text.strip():
        raise ValueError("empty text")
    voice = voice or DEFAULT_VOICE

    stem = f"charles_speak_{uuid.uuid4().hex[:8]}"
    out_dir = Path(out_dir)
    aiff_path = out_dir / f"{stem}.aiff"
    ogg_path = out_dir / f"{stem}.ogg"

    log.info("synth voice=%s rate=%d chars=%d", voice, SPEAK_RATE, len(text))
    try:
        subprocess.run(
            ["say", "-v", voice, "-r", str(SPEAK_RATE), "-o", str(aiff_path), text],
            check=True, capture_output=True, text=True,
        )
        subprocess.run(
            [
                "ffmpeg", "-y", "-loglevel", "error",
                "-i", str(aiff_path),
                "-c:a", "libopus", "-b:a", "32k", "-application", "voip",
                str(ogg_path),
            ],
            check=True, capture_output=True, text=True,
        )
    finally:
        if aiff_path.exists():
            aiff_path.unlink()
    return ogg_path
