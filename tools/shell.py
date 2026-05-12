"""Shell exec. Full power, no allowlist, no confirmation gate (YOLO mode)."""
from __future__ import annotations

import os
import signal
import subprocess
import threading
import time

from core.tools import tool

_OUTPUT_CAP = 8_000  # chars; truncate huge outputs so replies stay legible
_CANCEL_POLL_SECONDS = 0.25  # how often the run loop checks cancel_event


@tool(
    name="exec_shell",
    summary="Run a shell command (zsh on macOS) and return stdout/stderr and exit code.",
    triggers=(
        "run", "execute", "exec", "command", "shell", "ls", "list", "find",
        "grep", "ps", "kill", "npm", "pip", "brew", "git", "mkdir", "rm",
        "mv", "cp", "curl", "what files", "what's in /",
    ),
    schema={
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "Shell command to run via /bin/zsh -c."},
            "timeout": {"type": "number", "description": "Max seconds before killing the command.", "default": 60},
        },
        "required": ["command"],
    },
)
def exec_shell(
    command: str,
    timeout: float = 60,
    cancel_event: threading.Event | None = None,
) -> str:
    """Run a command. If cancel_event fires while the child is alive, the
    whole process group is killed (SIGTERM then SIGKILL after 1s) and the
    partial stdout/stderr captured so far is returned.

    Uses Popen + a polling loop instead of subprocess.run(timeout=...) so
    cancel_event can take effect mid-command — agent.respond hooks Stop
    into this same event.
    """
    # start_new_session=True so we get our own process group; signals
    # propagate to children (find/grep/etc spawned by the user's command).
    proc = subprocess.Popen(
        command,
        shell=True,
        executable="/bin/zsh",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )

    started = time.monotonic()
    cancelled = False
    timed_out = False
    while True:
        if proc.poll() is not None:
            break
        if cancel_event is not None and cancel_event.is_set():
            cancelled = True
            break
        if (time.monotonic() - started) >= timeout:
            timed_out = True
            break
        time.sleep(_CANCEL_POLL_SECONDS)

    if cancelled or timed_out:
        # SIGTERM the whole group; give it 1s; then SIGKILL.
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            proc.wait(timeout=1.0)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            try:
                proc.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                pass

    # Drain pipes even on kill — what came out before signal is useful.
    try:
        stdout, stderr = proc.communicate(timeout=2.0)
    except subprocess.TimeoutExpired:
        proc.kill()
        stdout, stderr = proc.communicate()

    if cancelled:
        prefix = f"[cancelled by user after {time.monotonic() - started:.1f}s]"
    elif timed_out:
        prefix = f"[error] timed out after {timeout}s: {command!r}"
    else:
        prefix = None

    parts = []
    if prefix:
        parts.append(prefix)
    parts.append(f"exit={proc.returncode}")
    if stdout:
        parts.append("[stdout]\n" + stdout.rstrip())
    if stderr:
        parts.append("[stderr]\n" + stderr.rstrip())
    out = "\n".join(parts)
    if len(out) > _OUTPUT_CAP:
        out = out[:_OUTPUT_CAP] + f"\n... [truncated, full output was {len(out)} chars]"
    return out
