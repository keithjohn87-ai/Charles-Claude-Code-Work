# MLX-LM training split v2 — Mac Claude Code (synthetic-filtered)

Created: 2026-05-16

**Improvement over v1:** v1 had 1,126 pairs but ~727 were synthetic (task-notification events, slash-command expansions, system-reminder preambles). v2 filters these out.

- **Source:** `mac_claude_code_v2_clean.jsonl` (402 pairs)
- **Random seed:** 20260516
- **Split:** 362 train / 40 valid
- **Schema:** `{"messages": [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]}`

## What this is
Real John ↔ Claude Code conversation pairs from 9 Mac sessions across early-to-mid May 2026.

## What this is NOT (yet)
- claude.ai export (pending John drop into `training_corpus/manual_drops/`)
- Cowork export from Windows (pending)
- Mobile Claude export (pending)
- Multi-turn context windows — pairs are isolated user→assistant exchanges

## Caveats
- No manual QA pass yet (50-random spot-check still owed before training)
- Some pairs have very terse asst responses (e.g. "Standing by.") — these are still on-persona for Charles's operator pattern but might want a length floor in a later iteration

## Files
- `train.jsonl` — 362 pairs
- `valid.jsonl` — 40 pairs
