# Aider + MLX-LM Smoke Test — Day 1 (2026-05-12)

**Sub-Workstream 1, Day 1 of the 30-day Claude Code Absorption Sprint
(MOM §14).** First end-to-end proof that Aider can drive Charles's local
MLX model to edit Charles's own codebase.

## Result

**PASS.** Aider connected to MLX-LM on `127.0.0.1:8080`, sent a small
edit request, and Qwen3.6-35B-A3B applied the diff to
`workspace/aider_smoke/greet.py`. Output verified:

```
$ python3 workspace/aider_smoke/greet.py
Hello, world
Howdy, world
```

## Two snags + fixes (keep for future invocations)

### Snag 1 — Aider thinks the model has 0-token context

The MLX `/v1/models` endpoint advertises only `id`/`object`/`created`,
no `context_length`. LiteLLM (Aider's underlying client) doesn't have a
hardcoded mapping for `mlx-community/Qwen3.6-35B-A3B-4bit`, so Aider
defaults `max_tokens = 0` and refuses to send the assistant reply.

**Fix:** pass `--model-metadata-file` with explicit limits.
Stored at `workspace/aider_smoke/aider_model_metadata.json`
(name avoids Aider's auto-added `.aider*` gitignore line):

```json
{
  "openai/mlx-community/Qwen3.6-35B-A3B-4bit": {
    "max_tokens": 8192,
    "max_input_tokens": 32768,
    "max_output_tokens": 8192,
    "input_cost_per_token": 0,
    "output_cost_per_token": 0,
    "litellm_provider": "openai",
    "mode": "chat",
    "supports_function_calling": false,
    "supports_vision": false
  }
}
```

### Snag 2 — Qwen3 reasoning mode swallows the answer

Qwen3 defaults to "thinking" mode: the model dumps its scratch into a
separate `reasoning` field and leaves `content` empty. Aider only reads
`content`, so it saw zero output tokens and bailed with "hit a token
limit".

**Fix:** disable thinking via `chat_template_kwargs.enable_thinking =
false`, passed through Aider's `extra_params.extra_body`.

Stored at `workspace/aider_smoke/aider_model_settings.yml`:

```yaml
- name: openai/mlx-community/Qwen3.6-35B-A3B-4bit
  edit_format: whole
  use_repo_map: false
  send_undo_reply: false
  examples_as_sys_msg: true
  extra_params:
    extra_body:
      chat_template_kwargs:
        enable_thinking: false
```

Note for later: keeping thinking *on* may help on harder edits, but
the answer-extraction path has to read `reasoning` too. Worth revisiting
once we're past smoke-test scope.

## Working invocation (canonical)

```bash
cd /Users/home/charles/.claude/worktrees/ecstatic-mestorf-033e82
OPENAI_API_BASE=http://127.0.0.1:8080/v1 \
OPENAI_API_KEY=mlx-local \
/Users/home/charles/.venv/bin/aider \
  --model openai/mlx-community/Qwen3.6-35B-A3B-4bit \
  --model-metadata-file workspace/aider_smoke/aider_model_metadata.json \
  --model-settings-file  workspace/aider_smoke/aider_model_settings.yml \
  --no-show-model-warnings \
  --no-auto-commits \
  --no-pretty \
  --no-stream \
  --yes-always \
  --map-tokens 0 \
  --message "<your edit instruction>" \
  <target file path>
```

`--map-tokens 0` disables Aider's repo-map (saves ~4k input tokens on
small targets; turn back on for whole-codebase work).

## Numbers

- Round-trip: ~30s for a 6-line edit (cold MLX cache).
- Tokens: 790 sent / 179 received. Fits in our 32k input window with
  10× headroom.
- Diff was clean (no orphan whitespace, no dropped lines), test passes.

## What this unlocks

Charles can now *delegate small refactors to himself* by shelling out to
Aider. That means goals like "rename this function across the file" or
"add a type hint here" no longer have to chew up Charles's main respond
loop — they go to a sub-process that streams to a different MLX context
and reports back. Next step (Day 2-3 of the absorption sprint): wire
Aider as a tool that Charles can call (`run_aider_edit(file, instr)`).
