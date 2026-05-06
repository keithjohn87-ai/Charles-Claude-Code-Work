"""Self-modification: Charles edits his own source.

Two tools:
  self_modify   — replace a file's full contents
  self_patch    — find-and-replace a single unique snippet (cheaper for small edits)

Both auto-backup, validate Python syntax, and git-commit on success. Changes
take effect on the NEXT restart of charles.py — Python does not hot-reload.
"""
from __future__ import annotations

import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from config import ROOT, WORKSPACE
from core.tools import tool

_BACKUP_DIR = WORKSPACE / "self_modify_backups"


def _backup(p: Path) -> Path:
    _BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    bkp = _BACKUP_DIR / f"{p.name}.{ts}.bak"
    shutil.copy2(p, bkp)
    return bkp


def _git_commit(p: Path, reason: str) -> tuple[bool, str]:
    """Stage + commit a single file. Returns (ok, message_or_sha)."""
    try:
        rel = p.resolve().relative_to(ROOT)
    except ValueError:
        return False, f"path is outside repo root ({ROOT}); not committing"

    try:
        subprocess.run(
            ["git", "add", "--", str(rel)],
            cwd=ROOT, check=True, capture_output=True, text=True,
        )
        # If nothing changed, commit will fail with "nothing to commit" — surface that
        commit = subprocess.run(
            ["git", "-c", "user.name=Charles", "-c", "user.email=charles@local",
             "commit", "-q", "-m", f"self_modify: {reason}"],
            cwd=ROOT, capture_output=True, text=True,
        )
        if commit.returncode != 0:
            err = (commit.stderr or commit.stdout or "").strip()
            return False, f"git commit failed: {err}"
        sha = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT, check=True, capture_output=True, text=True,
        ).stdout.strip()
        return True, sha
    except subprocess.CalledProcessError as e:
        return False, f"git error: {(e.stderr or '').strip()}"


def _validate_python(content: str, label: str) -> str | None:
    """Return None if syntax-valid (or not .py), else an error message."""
    try:
        compile(content, label, "exec")
    except SyntaxError as e:
        return f"SyntaxError: {e.msg} at line {e.lineno}"
    return None


def _diff_stats(old: str, new: str) -> str:
    old_n, new_n = old.count("\n"), new.count("\n")
    return f"{old_n}→{new_n} lines ({new_n - old_n:+d})"


@tool(
    name="self_modify",
    summary="Replace one of your source files with new content. Auto-backs-up, syntax-checks .py, and git-commits.",
    triggers=("self modify", "rewrite your", "edit your", "modify your", "change your code", "update your code"),
    schema={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Absolute path to the file to overwrite. Typically inside /Users/home/charles/.",
            },
            "new_content": {
                "type": "string",
                "description": "Full new contents of the file.",
            },
            "reason": {
                "type": "string",
                "description": "Short explanation; used as the git commit message.",
            },
        },
        "required": ["path", "new_content", "reason"],
    },
)
def self_modify(path: str, new_content: str, reason: str) -> str:
    p = Path(path).expanduser().resolve()
    if not p.exists():
        return f"[error] no such file: {p}"
    if not p.is_file():
        return f"[error] not a file: {p}"

    if p.suffix == ".py":
        err = _validate_python(new_content, str(p))
        if err:
            return f"[error] refused — {err}"

    old = p.read_text()
    if old == new_content:
        return "[noop] new_content is identical to current file; nothing changed."

    bkp = _backup(p)
    p.write_text(new_content)
    ok, info = _git_commit(p, reason)
    note = f"committed {info}" if ok else f"NOT committed ({info})"
    return (
        f"self_modify: {p.name} {_diff_stats(old, new_content)} — {note}\n"
        f"  backup: {bkp}\n"
        f"  reason: {reason}\n"
        f"  effect: takes hold on next charles.py restart"
    )


@tool(
    name="self_patch",
    summary="Find a single unique snippet in your source and replace it. Auto-backs-up, syntax-checks .py, git-commits. Cheaper than self_modify for small edits.",
    triggers=("self patch", "patch your", "fix your code", "edit your code"),
    schema={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Absolute path to the file."},
            "find": {
                "type": "string",
                "description": "Exact snippet to find. Must appear EXACTLY ONCE in the file.",
            },
            "replace": {
                "type": "string",
                "description": "Replacement text. Use empty string to delete the snippet.",
            },
            "reason": {"type": "string", "description": "Used as git commit message."},
        },
        "required": ["path", "find", "replace", "reason"],
    },
)
def self_patch(path: str, find: str, replace: str, reason: str) -> str:
    p = Path(path).expanduser().resolve()
    if not p.exists():
        return f"[error] no such file: {p}"
    if not p.is_file():
        return f"[error] not a file: {p}"

    old = p.read_text()
    count = old.count(find)
    if count == 0:
        return f"[error] snippet not found in {p.name}"
    if count > 1:
        return f"[error] snippet matches {count} places in {p.name} — make it unique or use self_modify"

    new_content = old.replace(find, replace, 1)
    if p.suffix == ".py":
        err = _validate_python(new_content, str(p))
        if err:
            return f"[error] refused — {err}"

    bkp = _backup(p)
    p.write_text(new_content)
    ok, info = _git_commit(p, reason)
    note = f"committed {info}" if ok else f"NOT committed ({info})"
    return (
        f"self_patch: {p.name} {_diff_stats(old, new_content)} — {note}\n"
        f"  backup: {bkp}\n"
        f"  reason: {reason}\n"
        f"  effect: takes hold on next charles.py restart"
    )
