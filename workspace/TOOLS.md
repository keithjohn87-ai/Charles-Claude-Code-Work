# TOOLS

## Currently available (M1)

- **`read_file(path)`** — read a UTF-8 text file. `~`-expansion supported. Cap: 64KB returned.
- **`write_file(path, content, append=False)`** — overwrite (default) or append; creates parent dirs automatically.
- **`exec_shell(command, timeout=60)`** — full zsh, no allowlist, no confirmation gate. stdout/stderr returned with exit code, output capped at 8KB.

## How tools are loaded

The classifier in `core/tools.py` picks 0–3 tools per turn by matching trigger keywords against the inbound message. Only matched tools' full JSON schemas go into the prompt that turn — everything else is just a one-line summary. Result: lean default prompt, fast turns, room to grow toward dozens of tools without bloat.

If I think I need a tool but its schema isn't loaded this turn, I can either:
- Re-phrase using a clearer keyword and the classifier will catch it next turn, or
- Use `exec_shell` (loaded for most action verbs) to do the equivalent.

## Coming

- **M2 — Memory:** SQLite-backed `remember(fact)` / `recall(query)`, daily markdown logs in `workspace/memory/`.
- **M3 — Self-modify:** edit my own `.py` source (backed by `git` rollback).
- **M4 — Event loop + scheduled tasks:** autonomous heartbeat, not just reactive.
- **M5+ — More channels & senses:** iMessage, Whisper voice, Playwright browser, sentiment.

To inspect my current tool registry at any time:
```
read_file('/Users/home/charles/tools/__init__.py')
read_file('/Users/home/charles/tools/filesystem.py')
read_file('/Users/home/charles/tools/shell.py')
```

🌊
