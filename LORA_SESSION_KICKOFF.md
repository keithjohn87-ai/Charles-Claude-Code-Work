# Qwen LoRA Fine-Tune — Session Kickoff Doc

**Date drafted:** 2026-05-16
**Status:** PROJECT GREENLIT — pivot from harness work confirmed by John 2026-05-16 ~16:00 EST: "Probably going into Model tweaks. Charles seems to be working through things on his own with issues. So we will let him ride for a bit and get Qwen up to snuff."
**Read this FIRST when the next session opens.** It contains the decision context, hardware constraints, training-data assessment, tooling status, recommended phase plan, and risk register so we don't re-litigate scope each time.

---

## 1. Why we're doing this (decision context)

The harness work has plateaued in terms of reliability impact. Charles now has:
- 9 harness fixes shipped (round cap, Rule 7, cc_runner guard, set_goal nudge, stuck detector, Read-before-Edit, tool truncation, TodoWrite, Rule 9 parallel calls, sub-agent spawning)
- 81 registered tools, 32 in CORE
- All the dispatch-layer guards Claude Code has

The remaining capability gap is **model intelligence**. Qwen 3.6-A3B-4bit has 3B active params; Claude Sonnet/Opus has dramatically more. Some chains will always require more harness scaffolding on Qwen than Claude. The structural answer is to **bake the operator/consultant pattern, John's voice, the construction domain, and Charles's response style into the model weights** instead of carrying it all in the 33,700-char system prompt.

**Expected outcomes if successful:**
- Lower latency (less prompt to evaluate every turn — could cut system prompt to ~10-15K)
- More reliable persona adherence (operator over warmth, no narration, just-do-it)
- More reliable domain handling (construction trade vocabulary, lien/contract awareness)
- More reliable execution patterns (Plan → todo_set → tools → final reply discipline)

**Expected outcomes if it goes wrong:**
- Catastrophic — a bad fine-tune makes Charles WORSE. Could collapse persona, regress reasoning, increase hallucination. The eval gate (Phase 4 below) is non-negotiable.

---

## 2. Hardware + tooling status (audited 2026-05-16)

**Hardware:** Mac Studio M1 Ultra, 64GB unified memory.

**Model checkpoint:** `~/.cache/huggingface/hub/models--mlx-community--Qwen3.6-35B-A3B-4bit/` (4-bit quantized, ~19GB on disk).

**⚠️ Critical:** mlx-lm's LoRA training typically works best on **non-quantized** base models. We may need to fetch `mlx-community/Qwen3.6-35B-A3B` (full precision) for training, train the LoRA against that, then re-quantize the fused result back to 4-bit for inference. The full-precision model is ~70GB on disk and ~70GB in memory during training. Tight fit on 64GB; may need to use gradient checkpointing or train fewer layers.

**LoRA tooling:** mlx-lm 0.31.3 (at `/Users/home/charles/.venv/lib/python3.11/site-packages/mlx_lm/`). Confirmed `lora.py` and `fuse.py` both present. Standard CLI:
```bash
python -m mlx_lm.lora --model <path> --train --data <jsonl_dir> ...
python -m mlx_lm.fuse --model <base> --adapter-path <lora_out> --save-path <fused>
```

**Reference:** [mlx-examples/lora](https://github.com/ml-explore/mlx-examples/tree/main/lora) for the canonical workflow.

---

## 3. Training data assessment — REALITY CHECK

**Original assumption:** 18,000+ conversation turns in memory.db → plenty for LoRA.

**Actual state (audited 2026-05-16):** 1,461 total conversation rows. Why: the behavior_watchdog prunes each conv to 200 turns max (`Watchdog prune: trimmed N old turn(s) across X conv_id(s) (cap 200/conv)`). So:

| Source | Rows | Useful for LoRA |
|---|---|---|
| `conversations` table (memory.db) | 1,461 | ~400-600 user/assistant pairs after filtering tool rows, progress markers, intermediate assistant turns |
| `daily_log` (auto-extracted facts) | thousands | Domain knowledge, not behavior |
| `long_term_facts` | thousands | Same as above |
| John's curated training files (per `USER.md` / `KNOWLEDGE_BASE.md`) | unknown | High quality if John blesses them |
| Older conversation exports / backups (`workspace/memory.db.pre-*`) | unknown | Worth auditing — likely thousands of pre-pruned turns |
| The current Claude Code session transcripts (e.g., this very session) | substantial | High-quality operator/consultant pattern examples — THIS IS THE GOLD |

**Implication:** the most fertile training data may not be memory.db — it may be:
1. The **pre-prune memory.db backups** at `workspace/memory.db.pre-cc-20260511-*` and similar
2. The **Claude Code session transcripts** themselves (this conversation; prior conversations) which demonstrate the operator/consultant pattern at high quality
3. **Hand-curated synthetic examples** authored to bake in specific behaviors (response-style adherence, John-voice fluency, refusal patterns, etc.)

**First action of next session:** audit ALL training-data sources, count clean pairs, decide whether augmentation is needed before training.

**Typical LoRA dataset size for behavior tuning:** 500-5000 examples. Below 500 risks underfitting; above 5000 has diminishing returns for behavior (vs domain knowledge, which scales).

---

## 4. Recommended phase plan (1-2 day project session)

### Phase 1 — Training data prep (4-6 hours)
1. Mine ALL `workspace/memory.db.pre-*` backups for pre-prune conversation turns. Combine.
2. Mine `~/.claude/projects/-Users-home-charles/` session transcripts (Claude Code sessions) for high-quality operator/consultant examples. THIS IS THE SECRET WEAPON — high-quality plan→tool-batch→synthesis chains demonstrating exactly the behavior we want Charles to internalize.
3. Filter for "good" turns: user message + assistant reply where the assistant reply was accepted without correction in the next user turn.
4. Format as JSONL conversations in the mlx-lm-expected schema (typically `{"messages": [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]}`).
5. Hold out 10-15% as eval set. Random sample, stratified by conv source.
6. Manual QA of 50 random training pairs — confirm they're actually examples of behavior we want Charles to learn.

### Phase 2 — Tooling validation (2-4 hours)
1. Decide: train on the 4-bit quantized model (faster, less memory, may not converge well) OR fetch the full-precision base (slower, more memory, better convergence).
2. Run a smoke LoRA training: 50 examples × 100 iterations on a small rank (rank=8). Confirm the loss curve goes down. Confirm fuse + reload + sanity inference works end-to-end.
3. If 4-bit training is brittle, fetch full-precision base and prepare the larger training environment.

### Phase 3 — Real training run (4-8 hours)
1. Full dataset, rank=16-32, ~1000-2000 iterations.
2. Monitor loss curve; checkpoint every 200 iters.
3. Pick best checkpoint by held-out eval loss.

### Phase 4 — Eval gate (non-negotiable, 2-4 hours)
**Eval framework:** designed BEFORE training, not after.

| Eval | What | Pass criteria |
|---|---|---|
| Sunday Test scenarios | 5-10 scripted prompts John has used historically to validate Charles's persona/behavior | Same or better than baseline on all |
| Held-out training-set perplexity | Loss on the 10-15% holdout | Drops below baseline by ≥10% |
| Latency benchmark | Time to first token on 5 representative prompts | ≤ baseline (LoRA shouldn't slow inference) |
| Response-quality regression | A/B sample 20 prompts; rank Charles-baseline vs Charles-LoRA replies | LoRA wins or ties on ≥70% |
| Tool-call format adherence | 10 prompts that require tool calls; check JSON validity + correctness | 100% (regression here = block deploy) |
| Refusal/safety behavior | 5 prompts that should trigger refusal or notify_john | Same as baseline |

**Deploy gate:** ALL evals pass. If any regress, do not deploy — diagnose and iterate.

### Phase 5 — Deploy + monitor (1-2 hours)
1. Fuse the chosen LoRA adapter into a new model checkpoint.
2. Re-quantize to 4-bit for inference (if trained at full precision).
3. Replace the MLX server's model path. Restart `com.mlx.server`.
4. Smoke-test with 5 real prompts from John (or run them programmatically).
5. Monitor for 24-48 hours. Watch `charles.launchd.err.log` for new error patterns.
6. Keep the previous model checkpoint as `_prev` for instant rollback if regression appears.

---

## 5. Risk register

| Risk | Severity | Mitigation |
|---|---|---|
| 4-bit LoRA training diverges or doesn't converge | HIGH | Phase 2 smoke test catches this early; fetch full-precision base if needed |
| Full-precision model + training state exceeds 64GB | HIGH | Gradient checkpointing, train fewer layers (last 4-8), reduce rank |
| Fine-tune collapses persona (Charles forgets the operator/consultant pattern) | HIGH | Eval Phase 4 catches it; rollback to baseline model |
| Fine-tune regresses tool-call JSON format | HIGH | Phase 4 tool-call eval; this is a deploy-blocker |
| Training data is too small (< 500 high-quality pairs) | MEDIUM | Phase 1 audit catches it; augment with hand-curated examples; reduce rank to avoid overfitting |
| Latency degrades after fuse | LOW | Phase 4 latency benchmark; can ship LoRA-only (skip fuse) and pay adapter-load cost |
| Sunday Test scenarios don't catch the regression that breaks production | MEDIUM | Build 24-48hr monitoring + instant rollback; expand Sunday Test based on observed gaps |

---

## 6. What's already done (don't re-do)

- ✅ Tooling installed (`mlx_lm 0.31.3` with `lora.py` + `fuse.py`)
- ✅ Hardware audited (M1 Ultra 64GB; tight for full-precision training of 35B but workable with checkpointing)
- ✅ Model checkpoint located (`~/.cache/huggingface/hub/models--mlx-community--Qwen3.6-35B-A3B-4bit/`)
- ✅ Training-data sources mapped (memory.db + backups + Claude Code session transcripts + hand-curation)
- ✅ Phase plan + eval framework drafted (this doc)
- ✅ Risk register populated (this doc)
- ✅ Doctrine memory exists (`project_qwen_lora_customization.md`) — read it for ongoing context

---

## 7. First actions when the next session opens

1. Read this doc (you're here)
2. Read `project_qwen_lora_customization.md` (the standing doctrine memory)
3. Read `feedback_model_choice_settled.md` (so you don't accidentally pitch a model swap)
4. Run the training-data audit (Phase 1 step 1): `find /Users/home/charles/workspace -name "memory.db.pre-*" -exec ls -la {} \;` to count backup-DB sizes; then a one-shot Python script to sum conversation rows across all of them
5. Decide based on data volume: proceed with what we have OR augment with Claude Code session transcripts + hand-curation first
6. Phase 2 smoke training run on quantized base — confirm tooling works end-to-end on a tiny dataset before committing to a full run

**Estimated total project time:** 1-2 focused days end-to-end. Phase 4 eval gate is the long pole — don't shortcut it.

---

*Document version: 2026-05-16 (v1.0). Maintained as the LoRA project kickoff. Update when project state changes.*
