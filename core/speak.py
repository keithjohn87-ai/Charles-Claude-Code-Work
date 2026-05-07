"""Text → speech → Telegram-compatible voice note.

Three-tier engine, in priority order:
  1. **Voice clone (Chatterbox)** — if `workspace/voice_reference.wav` exists,
     mlx-audio Chatterbox clones the reference voice. Best quality, matches
     character (Keith David reference, etc.).
  2. **Kokoro neural** — Apple Silicon native, configurable voice via
     CHARLES_VOICE (default am_fenrir). Studio-clean American narrator.
  3. **macOS `say` fallback** — built-in, robotic, last-resort.

Output is always .ogg/Opus — Telegram voice-note format.

Toggle the clone tier off via `CHARLES_USE_CLONE=0` in `.env` (e.g. when
debugging, or when the reference clip needs to be replaced).
"""
from __future__ import annotations

import logging
import os
import subprocess
import uuid
from pathlib import Path

from config import WORKSPACE

log = logging.getLogger("charles.speak")

DEFAULT_VOICE = os.environ.get("CHARLES_VOICE", "am_fenrir")
KOKORO_MODEL = os.environ.get("CHARLES_KOKORO_MODEL", "prince-canuma/Kokoro-82M")
SPEAK_RATE = float(os.environ.get("CHARLES_SPEAK_RATE", "0.85"))

CLONE_MODEL = os.environ.get("CHARLES_CLONE_MODEL", "mlx-community/Chatterbox-TTS-fp16")
CLONE_REF = WORKSPACE / "voice_reference.wav"
USE_CLONE = os.environ.get("CHARLES_USE_CLONE", "1") != "0"

# macOS-say fallback only
_SAY_VOICE = os.environ.get("CHARLES_SAY_VOICE", "Daniel")
_SAY_RATE = int(os.environ.get("CHARLES_SAY_RATE", "180"))


def speak_to_ogg(text: str, out_dir: str | Path = "/tmp", voice: str | None = None) -> Path:
    """Synthesize speech and return a .ogg file Telegram accepts as a voice note.

    Tries clone → Kokoro → say in order; returns on first success.
    Caller is responsible for deleting the file when done.
    """
    if not text or not text.strip():
        raise ValueError("empty text")
    voice = voice or DEFAULT_VOICE
    out_dir = Path(out_dir)
    stem = f"charles_speak_{uuid.uuid4().hex[:8]}"

    if USE_CLONE and CLONE_REF.exists():
        try:
            return _clone_to_ogg(text, out_dir, stem)
        except Exception as e:  # noqa: BLE001
            log.warning("clone failed (%s: %s) — falling back to kokoro", type(e).__name__, e)

    try:
        return _kokoro_to_ogg(text, voice, out_dir, stem)
    except Exception as e:  # noqa: BLE001
        log.warning("kokoro failed (%s: %s) — falling back to macOS say", type(e).__name__, e)
        return _say_to_ogg(text, out_dir, stem)


def _clone_to_ogg(text: str, out_dir: Path, stem: str) -> Path:
    """Voice-clone path: Chatterbox with the reference clip → ffmpeg .ogg."""
    from mlx_audio.tts.generate import generate_audio  # late import — heavy

    log.info("clone model=%s ref=%s chars=%d", CLONE_MODEL, CLONE_REF.name, len(text))
    cwd_before = Path.cwd()
    try:
        os.chdir(out_dir)
        generate_audio(
            text=text,
            model=CLONE_MODEL,
            ref_audio=str(CLONE_REF),
            file_prefix=stem,
            save=True,
            verbose=False,
        )
    finally:
        os.chdir(cwd_before)
    return _wav_to_ogg(out_dir, stem)


def _kokoro_to_ogg(text: str, voice: str, out_dir: Path, stem: str) -> Path:
    """Kokoro path: neural .wav → ffmpeg .ogg."""
    from mlx_audio.tts.generate import generate_audio

    log.info("kokoro voice=%s rate=%.2f chars=%d", voice, SPEAK_RATE, len(text))
    cwd_before = Path.cwd()
    try:
        os.chdir(out_dir)
        generate_audio(
            text=text,
            model=KOKORO_MODEL,
            voice=voice,
            speed=SPEAK_RATE,
            file_prefix=stem,
            save=True,
            verbose=False,
        )
    finally:
        os.chdir(cwd_before)
    return _wav_to_ogg(out_dir, stem)


def _wav_to_ogg(out_dir: Path, stem: str) -> Path:
    """Find the wav mlx-audio just wrote, convert to .ogg, delete the wav."""
    wav_path = out_dir / f"{stem}_000.wav"
    if not wav_path.exists():
        raise FileNotFoundError(f"mlx-audio produced no wav: {wav_path}")
    ogg_path = out_dir / f"{stem}.ogg"
    try:
        subprocess.run(
            [
                "ffmpeg", "-y", "-loglevel", "error",
                "-i", str(wav_path),
                "-c:a", "libopus", "-b:a", "32k", "-application", "voip",
                str(ogg_path),
            ],
            check=True, capture_output=True, text=True,
        )
    finally:
        if wav_path.exists():
            wav_path.unlink()
    return ogg_path


def _say_to_ogg(text: str, out_dir: Path, stem: str) -> Path:
    """Fallback: macOS `say` → aiff → ffmpeg .ogg."""
    aiff_path = out_dir / f"{stem}.aiff"
    ogg_path = out_dir / f"{stem}.ogg"
    log.info("say fallback voice=%s rate=%d chars=%d", _SAY_VOICE, _SAY_RATE, len(text))
    try:
        subprocess.run(
            ["say", "-v", _SAY_VOICE, "-r", str(_SAY_RATE), "-o", str(aiff_path), text],
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
