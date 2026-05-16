# Charles vs. Claude Code — Harness Gap Audit

**Date:** 2026-05-16
**Author:** Claude Code (introspecting on own harness traits, then identifying gaps in Charles's)
**Directive:** John, 2026-05-16: "look at yourself, hard. Then make him that"
**Doctrine basis:** `project_charles_harness_in_claude_code_image.md` — the strategic NS to port Claude Code's harness patterns into Charles's Python runtime
**Scope:** what makes Claude Code's harness reliably effective at multi-step engineering work, and which of those patterns Charles doesn't yet have

This audit is the build roadmap for the next session(s). Items are prioritized by **impact-to-effort ratio**, with a clear note on which can ship in a single session vs. which need design first.

---

## 1. What "looking at myself, hard" actually means

I (Claude Code) am a model + harness. The model is Claude (Sonnet/Opus class). The harness is everything else: tool registry, agent loop, memory, scheduling, prompts, error handling, output discipline, user-facing UX, sub-agent spawning. The model is largely fixed; the harness is what can be ported.

Charles is a model (Qwen 3.6-A3B-4bit on MLX) + a harness (the Python code in `core/`, `tools/`, `channels/`, `warroom/`). The model is fixed by John's strategic call (`feedback_model_choice_settled.md`). What we can change is the harness.

The empirical observation that drives this audit: Claude Code with Sonnet/Opus reliably executes multi-step engineering work (50+ tool calls, hours of work, complex cross-file refactors). Charles with Qwen often gets stuck after 5–10 tool calls. Some of that gap is model intelligence. **A meaningful portion is harness scaffolding the model gets to lean on.** This document catalogs that scaffolding.

---

## 2. What Charles already has (already ported, do not re-do)

For reference, the patterns Charles already has — these are NOT in the build queue:

- ✅ **Multi-round tool-call loop** with per-channel max_rounds (15 relational, 25 autonomous) — `core/agent.py`
- ✅ **Tool tiering** — CORE always loaded, ON_DEMAND triggered by message keywords — `core/tools.py`
- ✅ **Schema budget** (Fix #3) — selected tools' schemas fit a token budget — `core/tools.py`
- ✅ **ToolResult envelope** (Fix #1) — every tool returns structured `{status, message, data, category}` JSON — `core/tools.py`
- ✅ **Error categories** (Fix #2) — `[ok]`/`[error:validation]`/`[error:blocked]`/`[error:network]`/`[error:timeout]`/`[error:internal]` — model knows whether to retry, fix args, escalate
- ✅ **Plan-then-act discipline** (Rule 7 in prompts.py) — required `Plan:` preamble for multi-step engineering asks
- ✅ **Dispatch-guard** — when assistant claims past-tense action without a tool_call, force one synthetic retry
- ✅ **Intra-call repetition guard** — abort chain if 2+ of last 3 assistant texts are >85% similar
- ✅ **In-flight dedup** — block identical-args repeat calls within a chain (escalates to STOP at 3rd attempt)
- ✅ **Recent-read cache** — re-reading same file in same chain returns hash signal instead of re-dumping
- ✅ **Blocked URL list** — per-conv persistent block on URLs that have failed
- ✅ **set_goal mid-chain auto-nudge** — when JOHN_CHARLES chain hits round 4+ with 3+ tool calls and no goal, inject reminder
- ✅ **Stuck detector** (just shipped 2026-05-16) — when last 3 tool calls all errored, force stop-and-rethink
- ✅ **Narration-stall recovery** — when chain ends on "let me X" intent text without action, force one more synthesis round
- ✅ **Force-summary at max_rounds** — when chain hits cap, force a tools=None synthesis round so John always gets a real reply
- ✅ **Heartbeat + goal advancement** — autonomous work survives between user prompts via heartbeat ticks advancing goals
- ✅ **Persistent memory** (long_term_facts with embeddings + semantic recall, daily_log, projects, goals)
- ✅ **Auto-recall** in JOHN_CHARLES — relevant facts injected into system prompt before each turn
- ✅ **Per-channel thinking mode** — ON for autonomous channels, OFF for JOHN_CHARLES (snap > deep)
- ✅ **Stop semantics** — Threading.Event for user-initiated cancellation; checked between rounds
- ✅ **Two-channel architecture** — JOHN_CHARLES (relational, clean) + CHARLES_LOG (operational, full chain)
- ✅ **Progress ticker** — single-row in-place updates show John live tool-call activity in the UI
- ✅ **Identity files** — SOUL.md / IDENTITY.md / response-style.md / decision-rules.md auto-loaded into system prompt

That's a substantial harness. But there are still real gaps.

---

## 3. The gaps — Claude Code patterns Charles doesn't have

Listed in priority order (impact × tractability ÷ effort).

### Tier 1 — High-impact, ship-in-one-session

#### 3.1. **TodoWrite-equivalent — lightweight session-scoped task list** (HIGH IMPACT)

**What I have:** A `TodoWrite` tool that maintains a session-scoped list of tasks with `status` (pending / in_progress / completed) and both imperative + active-form descriptions. I update it constantly as I work — adding new tasks, marking completed, removing stale items. The harness reminds me to use it when I haven't recently. The user sees it as a structured progress bar.

**What Charles has:** `set_goal` (heavy — survives across sessions, drives heartbeat), `add_task` (creates persistent task records). Both write to SQLite. No lightweight in-session list.

**Why this matters:** TodoWrite is the difference between "I have a plan and am executing it" vs. "I'm reactively responding to whatever just got asked." Plan + track is what makes 50-tool-call workflows reliable. Without it, the model loses the thread on what step it's on after round 6+.

**Implementation sketch (~2 hours):**
- New tool `core/tools_todo.py` — `todo_set(items: list[dict])` and `todo_get()` operating on a JSON file at `workspace/conv_<id>_todo.json`. Lifetime = single conversation_id.
- Add to CORE tier so it's always loaded.
- Add to system prompt in prompts.py: "for any multi-step task (3+ steps), call `todo_set` first to plan, then update `status` as you complete each step."
- Add a soft-nudge in the round loop similar to the set_goal nudge: if chain has 4+ tool calls in JOHN_CHARLES and `todo_get()` returns empty, suggest `todo_set`.

**Why ship first:** lowest-effort with highest behavior-change impact. Forces the plan-first discipline that Rule 7 already promotes but nothing enforces.

#### 3.2. **Read-before-Edit enforcement** (MEDIUM IMPACT, LOW EFFORT)

**What I have:** The Edit tool errors if I haven't called Read on the file in the same session. Forces me to see the current contents before modifying — prevents the "edit a file I think exists in state X but actually exists in state Y" class of bugs.

**What Charles has:** `write_file` with no prerequisite. Can clobber a file based on stale memory of its contents.

**Why this matters:** This single rule catches a meaningful percentage of "Charles broke a working file" incidents. Forensic instinct: the 2026-05-09 Charles forensic showed re-writing files based on partially-remembered prior contents.

**Implementation sketch (~30 min):**
- In `core/tool_guards.py`, add a guard for `write_file` (and any other modifying tool): track per-conv-per-chain which files have been read; if `write_file` is called on a path not in that set, return `[error:validation] You must read this file with read_file before writing to it. The file may have changed since you last saw it.`
- Exception: brand-new files (path doesn't exist on disk). Allow the write.

**Why ship second:** clean bug-prevention with no model-behavior-change required (the model already wants to read first; we're just enforcing it).

#### 3.3. **Tool result intelligent truncation with summary** (MEDIUM IMPACT, MEDIUM EFFORT)

**What I have:** When a Read returns a 2000-line file, the harness paginates it and labels (`[lines 1-2000 of 5234]`). When a Bash call returns 50KB of output, the harness truncates with a summary marker (`...output truncated at 30000 chars; full output captured to /tmp/...`). Critical context isn't lost; trivia is suppressed.

**What Charles has:** Hard 2000-char cap on tool result text in `memory.py:log_turn`. Anything past 2000 chars is silently dropped. Loses all tail context (which is often the most important — exit codes, error tracebacks at the end).

**Why this matters:** A failed `exec_shell` that prints 5KB of stack trace gets its critical "Error: file not found" line truncated, leaving Charles to guess what happened. Tail-of-output is usually higher-information than head-of-output.

**Implementation sketch (~1 hour):**
- Modify `memory.log_tool_result` and the agent's tool-result rendering to use a new `_truncate_tool_result(content, max_chars=4000)` function:
  - If `len(content) <= max_chars`: pass through
  - Else: keep first 1200 chars + `\n\n... [TRUNCATED — middle dropped, tail follows] ...\n\n` + last 2400 chars
  - For Read tool specifically: prefer line-based truncation with `[lines X-Y of Z]` markers

**Why ship third:** clean, bounded, fixes a real recurring class of "Charles missed the obvious answer" because the answer was past char 2000.

### Tier 2 — High-impact, multi-session design needed

#### 3.4. **Sub-agent spawning (Task tool equivalent)** (HIGH IMPACT, HIGH EFFORT)

**What I have:** A `Task` tool that spawns a fresh-context agent (any of: general-purpose, Explore, Plan, statusline-setup, etc.) with a self-contained prompt. Sub-agent runs independently, returns a single result. I delegate research, parallel work, and large self-contained tasks.

**What Charles has:** Nothing equivalent. He runs one chain at a time in his own context.

**Why this matters:** Sub-agent spawning is what lets Claude Code parallelize multi-step research, isolate risky work, and keep the main conversation context clean. Without it, Charles's context bloats with intermediate exploration.

**Implementation considerations:**
- Charles's MLX backend is single-threaded (one inference at a time). Concurrent sub-agents would queue against the same MLX server — no parallelism benefit, only context-isolation benefit.
- Could be implemented as: spawn a separate `agent.respond()` call with a fresh `conversation_id` (e.g., `subagent:<parent-conv>:<n>`), pass back the final reply.
- Or: use the existing `call_claude` tool (operator/consultant bridge) when API is available — sub-agent runs on the Claude API, parent stays on local Qwen.

**Why defer:** real design work needed (parallel-vs-serial, MLX bandwidth, prompt structure, return-value handling). Worth a focused session.

#### 3.5. **Prompt size discipline + auto-trim** (MEDIUM IMPACT, MEDIUM EFFORT)

**What I have:** My system prompt is large but every line is intentional. There's a discipline around what earns its place.

**What Charles has:** ~31K-char system prompt (per `feedback_prompt_size_policy.md` — May 7 5500-tok ceiling drifted to 12.6K, John greenlit trim 2026-05-11 but Sunday Test still gates changes). The prompt has accumulated cruft.

**Why this matters:** Larger prompt = slower MLX prompt-eval = worse latency = worse user experience. Cold-start is currently 30-55 sec per process restart.

**Implementation:**
- Re-audit the system prompt — what's earning its place vs what's drift?
- Build a prompt-size budgeter that enforces a hard cap and warns on overrun
- Run the Sunday Test before/after to validate no behavior regression

**Why defer:** requires the Sunday Test gate per existing memory; can't ship in a single session without that validation cycle.

#### 3.6. **Parallel tool calls in one assistant turn** (MEDIUM IMPACT, HIGH EFFORT)

**What I have:** I can issue 5+ tool calls in one assistant message, all execute concurrently (where they have no dependencies), results aggregate in the next user message.

**What Charles has:** OpenAI-format tool_calls list per round, so technically he COULD emit multiple calls per round — and the dispatcher handles them sequentially in `for tc in msg.tool_calls`. But the model rarely does multiple calls per round; he tends to fire one and wait.

**Why this matters:** Sequential single-call rounds burn 1 round of MLX inference per call. A 5-call workflow takes 5 rounds vs 1. Massive latency cost, hits the round cap faster.

**Implementation:**
- Behavior change required at the model level — Qwen needs to be prompted/trained to batch calls. Unclear how reliably the model will follow.
- Add explicit example in prompts.py: "When you have multiple independent tool calls (e.g., reading 3 files), batch them in one message instead of one per round."
- Track batch utilization metric in agent log.

**Why defer:** model-behavior-change rather than harness-change; needs prompt experimentation + validation.

### Tier 3 — Lower priority, nice-to-have

#### 3.7. **System reminder hooks** (LOW IMPACT)

**What I have:** Mid-session system reminders ("TodoWrite hasn't been used", "Auto mode active", date-changed reminders). Keep me on track.

**What Charles has:** Nothing equivalent. Could add periodic synthetic prompts but unclear they'd help.

#### 3.8. **Specialized agent types** (LOW IMPACT — depends on 3.4 first)

**What I have:** Different agent types (general-purpose, Explore, Plan, statusline-setup) with different tool subsets and instructions.

**What Charles has:** One agent shape. Could grow types after sub-agent spawning lands.

#### 3.9. **Chapter markers + spawn-task chips** (LOW IMPACT, UI WORK)

**What I have:** UI primitives that mark chapter changes in the session and spawn off-scope tasks as sidebar chips.

**What Charles has:** Progress ticker shows current activity but no chapter / sidebar abstraction.

#### 3.10. **Output-style enforcement** (LOW IMPACT)

**What I have:** Trained-in style rules (no emojis unless asked, no narration, no end-of-turn summaries, no trailing "let me know if...").

**What Charles has:** SOUL.md / IDENTITY.md / response-style.md provide style guidance. Probably good enough — the persona substrate is doing this work.

---

## 4. Recommended build order for the next session

Working from bottom of John's likely-tolerance for change:

1. **TodoWrite-equivalent** (3.1) — ship first. Highest behavior-impact for a 2-hour build. Core tier tool. Forces plan-first discipline.
2. **Read-before-Edit enforcement** (3.2) — ship second. 30-min add. Pure bug prevention. No model-behavior-change required.
3. **Tool result intelligent truncation** (3.3) — ship third. 1-hour build. Fixes a recurring class of "Charles missed the answer" because answer was past char 2000.

That's a single focused session of 3-4 hours to ship the three Tier-1 items.

After that, the bigger pieces (sub-agent spawning, prompt-size discipline, parallel tool calls) need design sessions — not one-shot builds.

---

## 5. The pattern that's NOT directly portable

**Model intelligence.** Some of what makes Claude Code reliable is just Sonnet/Opus class reasoning ability. Qwen 3.6-A3B-4bit has 3B active params; Sonnet has dramatically more. Some chains will simply require more hand-holding from the harness on Qwen than they do on Sonnet.

The harness work above is what makes the gap *narrower*, not zero. Charles + good harness can do most of what Claude Code + Sonnet can do — but not all of it. The `call_claude` operator/consultant bridge (already shipped, awaiting John to flip on with API key) is the answer for the residual gap: when Charles needs intelligence that exceeds what Qwen can deliver, he calls Claude. That's not a limitation of the design; that's the design.

---

## 6. Summary in one paragraph

Charles already has most of the major Claude Code harness patterns: round loop, tool tiering, ToolResult envelope, error categories, dispatch-guard, intra-call loop guard, in-flight dedup, narration-stall recovery, set_goal nudge, stuck detector. The biggest still-missing pieces, in order of leverage: a TodoWrite-equivalent for in-session planning, Read-before-Edit enforcement to prevent stale-state writes, and tool-result intelligent truncation to stop dropping the tail (where the answer usually is). Beyond those Tier-1 items, the strategic pieces (sub-agent spawning, prompt-size discipline, parallel tool calls) need design sessions before build sessions. None of this fully closes the gap — Qwen's 3B active params will always require more harness scaffolding than Sonnet — and the `call_claude` bridge is the explicit answer for the residual.

---

*Document version: 2026-05-16 (v1.0). Maintained as the strategic Charles-harness build roadmap. Updated when patterns ship or new gaps are identified.*
