# MLX-LM training split v7.1 — curated + length-clamped

Created: 2026-05-16

## Why v7.1 vs v7
v7 NaN'd at iter 50 across three hyperparam attempts because 24 pairs had
user prompts > 4000 chars (mostly subagent spawn-prompt task descriptions).
At max_seq_length=1024 those got truncated mid-prompt, leaving zero
assistant tokens to compute loss on with mask_prompt=true → NaN.

v7.1 adds a joint-length filter:
- user content ≤ 2500 chars
- user + assistant combined ≤ 3500 chars

## Sources (real session data only, no synthetic)
- mac_code v3: 402 → 396 (6 dropped for length) × 4x oversample = 1,584
- claude_ai v3: 1,723 → 1,701 (22 dropped) × 1x = 1,701
- telegram_charles (memory.db 8455750177): 25 → 25 × 8x oversample = 200
  (highest-fidelity training signal — literal John↔Charles dialog from prod)
- subagent: 36 → 8 (28 dropped for long spawn prompts) × 2x = 16

## Totals
- 3,501 pairs (3,151 train / 350 valid)
- Max user: 2,317 chars (well under 2,500 cap)
- Max joint: 3,485 chars (well under 3,500 cap)

## Training run history
- Phase 3 v4: 500 iters at LR 1e-5, rank 16, 8 layers, dropout 0.05, no weight_decay.
- Val loss trajectory: 2.606 → 2.318 → 2.223 → 2.234 → 2.304 → 2.274 → 2.130 → 2.129 → 2.101 → **2.041**
- 22% val loss reduction; best checkpoint = iter 500 (final)

## A/B sweep findings (ab_results_iter500.json)
- All 9 forget probes PASS — zero capability regression
- 6/15 prompts show base/LoRA divergence (was 2/15 in v6 attempt) — directional improvement
- Adapter is SAFE to ship but behaviorally mild — Charles persona not yet baked in

## Privacy
8455750177 contains real John↔Charles conversations; other sources include John's
private claude.ai history. All JSONL files local-only (.gitignored).
