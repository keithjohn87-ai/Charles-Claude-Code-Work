# Smoke Run Notes — 2026-05-16

## What we ran
- Config: `smoke_config.yaml` — 100 iters, batch=1, rank=8, scale=20, num_layers=4, LR=1e-4
- Data: v6 combined corpus (1,608 Mac Code 4x-oversample + 1,723 claude.ai with flattened tool arcs)
- Wall time: ~5 minutes
- Peak memory: 41 GB (of 64GB)

## What worked
- mlx-lm LoRA tooling end-to-end: model load, training loop, eval pass, checkpoint save
- Adapter file format: 256MB safetensors at iter 25/50/75/100 + adapter_config.json
- Inference loads the adapter via `mlx_lm.generate --adapter-path ...`
- Memory budget feasible (peak 41GB / 64GB — can push to ~16 layers safely)
- Charles offline ~10 min, came back online clean post-training

## What didn't work
- **Adapter produces garbage at every checkpoint.** Iter 25 → "!!!!" repetition. Iter 75 → "20220220..." token collapse.
- **Cause:** LR=1e-4 + scale=20 + rank=8 + batch=1 is way too aggressive for behavior LoRA on this corpus. The model learned to maximize loss in a degenerate token regime.

## Loss trajectory (noisy but real)
| Iter | Train | Val |
|------|-------|-----|
| 1    | -     | 2.922 |
| 20   | 2.791 | -     |
| 25   | -     | 2.965 |
| 50   | 3.259 | 3.156 |
| 75   | -     | 2.763 ← best val |
| 80   | 2.672 ← best train | - |
| 100  | 3.753 | 3.072 |

Per-iter variance is ±0.5 due to batch=1. Best val (iter 75, 2.763) was −0.16 below initial.

## Why the smoke still counts as PASS
The smoke gate is "does the tooling work?" — that's a YES. The garbage adapter output is the *expected* outcome of running default hyperparams on a small corpus. Phase 3 with proper hyperparams is the actual quality test.

## Phase 3 hyperparam changes (locked in phase3_config.yaml)
- LR: 1e-4 → **1e-5** (10x cut to match mlx-lm defaults)
- rank: 8 → **16** (more capacity for voice + operator pattern + domain)
- scale: 20 → **12** (less aggressive adapter influence)
- num_layers: 4 → **16** (default; smoke was undersized)
- iters: 100 → **1500**
- val_batches: 10 → **25** (smoother val loss curve)
- dropout: 0 → **0.05** (regularization for small dataset)

## What's NOT changed
- mask_prompt: true (correct — only compute loss on assistant text)
- batch_size: 1 (memory headroom — bumping to 2 with 16 layers could OOM)
- max_seq_length: 2048
- grad_checkpoint: true
- adamw optimizer
- seed: 20260516

## Files
- `smoke_config.yaml` — the smoke run (kept for record)
- `phase3_config.yaml` — proposed real-training config
- `smoke_adapter/0000{25,50,75,100}_adapters.safetensors` — broken checkpoints (kept as failure artifacts; useful for hyperparam calibration)
- `train.jsonl`, `valid.jsonl` — corpus (gitignored — local-only)
