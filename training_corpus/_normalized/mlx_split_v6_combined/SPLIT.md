# MLX-LM training split v6 — combined + flattened tool arcs

Created: 2026-05-16

## Improvement over v5
v5 dropped tool_use/tool_result blocks entirely (treated them as noise).
v6 keeps them, but flattens them into NATURAL-LANGUAGE descriptions
("[calls exec_shell: cd /home/claude && find ...]" + "[result: file
listing ...]") rather than literal JSON tool calls. This bakes in the
CONVERSATIONAL ARC (when to use tools, when to respond) without
corrupting the JSON tool-call format Charles relies on at runtime.

Tool name translation: bash_tool→exec_shell, create_file→write_file,
view→read_file, str_replace→self_patch, web_search→search_web,
web_fetch→browse_url, ask_user_input_v0→ask_john. Cowork-only tools
(memory_user_edits, present_files, visualize:*, places_*, image_search)
dropped entirely.

## Composition
- Mac Code v3 (402 base × 4x oversample = 1,608 effective)
- claude.ai v3 (1723 after filters)
- Total: 3331 pairs (train 2998 / valid 333)

## What changed in the claude.ai pipeline
- 206 claude.ai pairs now contain tool-arc signal (~22% of total claude.ai)
- Length cap raised for tool arcs (asst <=4000 chars instead of <=1200)
- Text-only claude.ai pairs still capped at asst <=1200 chars (operator-pattern bias)

## Pending evals
- Phase 4 tool-call format adherence test — if LoRA regresses Charles's JSON tool-call
  format because of the flattened "[calls X]" pattern in training, rollback to v5
