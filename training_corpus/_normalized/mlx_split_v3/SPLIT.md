# MLX-LM training split v3 — Mac Claude Code (QA-passed)

Created: 2026-05-16

**Pipeline:** v3 supersedes v2. Same synthetic-prompt filter, plus assistant-side contamination filter (caught a rate-limit error message that had slipped through). 50-random-pair manual QA pass executed.

- **Pairs kept:** 402
- **Drops:** synthetic_user=727, contam_asst=1, length_outlier=8, empty=0
- **Split:** 362 train / 40 valid (seed 20260516, 10% holdout)
- **Schema:** `{"messages": [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]}` — mlx-lm ChatDataset compatible

## QA findings
- 50-pair spot check: 80% on-pattern, 18% long-form (legitimate multi-paragraph replies), 2% terse-but-acceptable
- 4 of 50 contained the "— Claude Code" signoff (good voice signal)
- 23 of 50 used markdown formatting (bold/lists/headers) — accepted style
- One rate-limit error response found and now filtered

## Files
- `train.jsonl` — 362 pairs
- `valid.jsonl` — 40 pairs

## Still owed
- John's claude.ai/Cowork/mobile exports (pending)
- Hand-curated synthetic examples (optional — only if final corpus stays under 500 floor)
