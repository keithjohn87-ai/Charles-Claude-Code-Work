# MLX-LM training split v4 — COMBINED (Mac Code + claude.ai)

Created: 2026-05-16

## Composition
- **Mac Claude Code v3** (402 base pairs, oversampled 4x = 1608 effective)
- **claude.ai export v1** (2136 raw → 1638 after asst<=1200 char verbosity filter)

## Why this mix
- Mac Code is the canonical operator-pattern signal (median asst reply 87 chars, terse, action-oriented).
- claude.ai is volume + John-voice + construction domain, BUT default claude.ai responses run 650 char median (kickoff doc explicitly flagged this as dilution risk).
- 4x oversample of Mac Code + 1200-char cap on claude.ai biases the trained model toward the terse operator pattern while still getting volume + domain coverage from claude.ai.

## Numbers
- Total pairs: 3246
- Source mix: {'claude_ai': 1638, 'mac_claude_code': 1608}
- Train: 2922 pairs
- Valid: 324 pairs (10% holdout, seed 20260516)
- User len: median 79 chars, mean 133
- Asst len: median 388 chars, mean 566

## Schema
`{"messages": [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]}` — mlx-lm ChatDataset compatible

## Privacy
claude.ai export contained 15 detected secrets (Stripe keys, GitHub tokens, etc.) — all redacted to `[REDACTED_*]` placeholders before this corpus was written. Raw exports live in `training_corpus/manual_drops/` and are .gitignored.

## Pending
- Cowork (Windows) export — not yet dropped
- Mobile Claude export — not yet dropped
- Hand-curated synthetic examples — optional, gated on whether final pre-train evals show specific behavior gaps

## Files
- `train.jsonl` — 2922 pairs (schema-only, ready for mlx_lm.lora)
- `valid.jsonl` — 324 pairs (holdout)
- `_audit_with_meta.jsonl` — same pairs with source tags for inspection (do not feed to trainer)
