# Charles Harness Audit — 2026-05-13

## Executive Summary

Charles's runtime harness is **architecturally sound** with strong patterns around deterministic guards, memory persistence, and behavioral safeguards. The core loop (`agent.respond()`, tool dispatch, memory replay) closely mirrors Claude Code's principles. However, **three specific friction points** systematically degrade execution quality:

1. **Prompt token cost spirals silently** — tool schema overhead doesn't scale gracefully
2. **Error visibility is buried in string responses** — tools return `[error] ...` text that gets parsed as agent reasoning instead of explicit signals
3. **Tool return shapes are unstandardized** — inconsistent result parsing kills mid-chain reliability

This audit identifies the top drag points ranked by **impact/effort ratio** and proposes concrete fixes for the next sprint.

---

## 1. What the Harness Looks Like Today

### Agent Loop: `core/agent.py` (450+ lines)

The turn flow lives in `_respond_impl()` (lines 210–600):

1. **History load** (lines 214–252): Load prior context from SQLite memory, with adaptive budgeting (`HISTORY_CHAR_BUDGET=4000`). Greeter messages get 1/8 budget to prevent over-fit.
2. **Context enrichment** (lines 254–286): Auto-recall long_term_facts via semantic search (JOHN_CHARLES only); inject recent CHARLES_LOG summary for relational awareness.
3. **Tool selection** (lines 301–316): CORE tools always loaded; ON_DEMAND tools selected via trigger match on latest user message.
4. **Multi-round loop** (lines 337–600): Up to 25 rounds (relational: 5 rounds). Each round:
   - Calls `inference.complete()` (MLX-LM, with optional thinking mode)
   - Parses tool_calls from response
   - Checks **dispatch-guard** (hallucinated tool actions) and **intra-call loop guard**
   - Dispatches tool_calls via `tools.dispatch()`
   - Appends results and continues if tool_calls exist; else breaks
5. **Persistence** (lines 291–298): Single "progress ticker" row gets updated in-place each round to show live state in WarRoom UI.

**Stop semantics** (lines 59–76, 339–344, 388–397): Threading.Event for user-initiated cancellation; checked between rounds + post-complete.

### Tool Registry: `core/tools.py` (300+ lines)

**78 tools across 32 files** in `/tools/`:

- **CORE tier** (~25): Sent every turn, stable across MLX cache (project_*, browse_url, exec_shell, recall, remember, etc.)
- **ON_DEMAND tier** (~50): Triggered by keyword match in message; loaded only round 0
- **SYSTEM_ONLY tier** (~3): Never sent (consolidate_memory, reflect_now, notify_john) — scheduler/heartbeat-only

**Tool shape** (lines 25–41):
```python
@dataclass
class Tool:
    name: str
    summary: str
    schema: dict            # JSON schema for params
    triggers: tuple[str, ...]
    handler: Callable[..., str]  # Returns string always
```

Schema is OpenAI-compatible JSON; handler always returns a string (no typed results).

**Dispatch** (`lines 172–290`): Parses tool_calls, validates args against schema, applies guards (section below), calls handler, returns string.

### Memory Pipe: `core/memory.py` (250+ lines)

SQLite at `workspace/memory.db` with six tables:

1. **conversations** — append-only logs of role/content, indexed by (conversation_id, id)
2. **long_term_facts** — facts with embedding (MiniLM-384), tags, topic, confidence, source
3. **daily_log** — timestamped events (kind, text)
4. **tasks** — open requests Charles created for John (title, urgency, status)
5. **projects** — structured item state (slug, title, status) + items table
6. **goals** — open-ended work with per-goal notes column

**Recall** (`recall()`, `recall_keyword()`): Semantic similarity search via embedding dot-product (fast, deterministic).

**Log turn** (`log_turn()`): Appends to conversations; caps tool-result text at 2000 chars for replay.

**Recent history** (`recent_history()`): Filters role='progress' only; returns last N turns up to char budget. Does NOT strip tool results — model sees full chain.

### Goal/Planning System: `core/goals.py` + `core/heartbeat.py`

**Goals table**: `(id, title, description, notes, status=active/done/paused, created_at, completed_at)`

- Per-goal `notes` column holds continuity (instead of separate conv_id per goal)
- Heartbeat picks one "ripe" goal per tick (15 sec default)
- Charles advances ONE step, appends a note, heartbeat picks up next tick

**Heartbeat** (lines 47–64 in heartbeat.py): Async tick loop that:
1. Fires due scheduled_tasks (one-shot + recurring)
2. Advances one goal
3. Polls CLAUDE_CODE channel (every 60s)

All three produce synthetic prompts routed through `agent.respond()` with a prefixed conversation_id (`goal:42`, `heartbeat:123`, etc.). Narration-loop guard checks recent goal notes for >50% "I will / let me" phrases (lines 66–93 in heartbeat.py).

### Heartbeat / Proactive Loop: `core/heartbeat.py` + `core/scheduler.py`

**Heartbeat** runs continuously in a background thread (started by channels/telegram.py):
- 15-second tick default
- Async loop: `_fire_due_tasks()` → `_run_blocking()` → `agent.respond()`
- Watches for **narration loops** (>50% of recent goal notes are "I will" narration without action)
- Surfaces issues to John via `notify_john()` on stall detection

**Scheduler**: Simple SQLite-backed cron equivalent (one-shot or recurring cadence_seconds).

### State Persistence: `workspace/` tree

- **memory.db** — primary state (conversations, facts, tasks, goals, projects)
- **cc_state.json** — Common Crawl build state (for resume across restarts)
- **SOUL.md, IDENTITY.md** — editable persona files (auto-loaded into system prompt)
- **response-style.md, decision-rules.md** — doctrine files
- **workspace/projects/** — project items (TSV format, per-project)
- **logs/** — daily logs per conversation + process logs

---

## 2. Patterns that Match Claude Code

Charles already implements several patterns that make Claude Code "feel like it executes":

### ✓ Behavioral Guards Against Hallucination
**`core/tool_guards.py`** (lines 1–200): Deterministic guards that prevent tool-call spam:
- **Blocked URL list** per conversation (persists across turns)
- **In-flight dedup**: Same (tool_name, args_signature) tuple twice in one chain? Blocked.
- **Recent-read cache**: Re-reading same file in same chain returns hash signal instead of re-dumping.
- **SQLite-as-query anti-pattern**: `exec_shell("sqlite3 memory.db SELECT ...")` redirected to `recall()` instead.

**Guard application** happens in `dispatch()` (tools.py line 249) *before* handler is called. Returns explicit `[error] ...` string the model reads next round.

**Evidence**: Forensic 2026-05-09 showed Charles re-reading same file 55 times, retrying ResearchGate 48 times, emitting same blocked_url 13× across ticks. Guards eliminate this.

### ✓ Multi-Round Tool Chains with Prefix Cache Optimization
**Tool tiering** (agent.py lines 301–359): CORE tools always sent; ON_DEMAND selected per-message; mid-chain rounds drop ON_DEMAND schemas to keep MLX cache warm. This matches Claude Code's pattern of stable system-prompt prefix → cache reuse across turns.

**Per-channel thinking mode** (inference.py lines 38–85): ON by default for CHARLES_LOG (autonomous), OFF for JOHN_CHARLES (snappy). Adds 5–15× latency but catches multi-step coherence failures that Qwen's 3B active params drop.

### ✓ Memory Replay with Semantic Recall
**Recent history** (memory.py): Filters to last N turns, caps at char budget. Auto-recall (agent.py lines 267–274) runs keyword search on long_term_facts and merges findings into system prompt *before* user message — prevents "I already told you" frustration.

**Semantic lookup** via embedding similarity (MiniLM-384). Cheap, deterministic, survives across sessions.

### ✓ State Persistence and Resumability
**CC build** (cc_runner.py): State persisted to JSON every batch → resumable across process restarts. Goals table `notes` column provides per-goal continuity. Memory writes happen on every `log_turn()`.

### ✓ Stop Semantics (User-Initiated Cancellation)
**Threading.Event** (agent.py lines 55–76): `request_stop()` sets the event; `_respond_impl()` checks between rounds and post-complete. No in-flight kill of MLX generation (can't do mid-token), but next round exits cleanly.

### ✓ Incident Auditing
**Dispatch guard** (agent.py lines 120–184, 405–463): When Charles claims a past-tense action without emitting a tool_call, force a synthetic retry + audit fact. Caught 2026-05-12 "kicked off run_cc_build without doing it" incidents.

**Intra-call loop guard** (agent.py lines 89–117, 467–488): When 2+ of last 3 assistant texts are near-identical, abort and log incident fact.

---

## 3. The Top Friction Points (Ranked by Impact/Effort)

### FRICTION POINT 1: Prompt Token Cost Spirals Silently

**Impact: 5 / Effort: 2 → Ratio: 2.5**

#### What's Wrong

Every `respond()` call sends full tool schemas to MLX. With 78 tools × ~200 tokens per schema, that's ~15.6k tokens overhead *per message* even if only 5 tools actually fire. The tool selection mechanism (trigger-based) is naive substring matching (tools.py line 152: `if trig in text.lower()`), so:

- A message mentioning "project" triggers project_* tools even if the user only wants to browse
- All 25 CORE tools plus selected ON_DEMAND tools every round means schemas accumulate
- **No adaptive schema loading**: Even short "are you awake?" messages pay the full schema cost

**Evidence**: agent.py lines 319–326 logs tool counts but never logs schema bytes. MLX cache hits the prefix but a cold process restart pays ~30–55 sec upfront (prompts.py lines 20–22 admits target was <600 tokens, actually ~5500).

**Specific file:line**: 
- `core/tools.py` lines 142–164 (naive classifier)
- `core/agent.py` lines 313–316 (on_demand selection + core_tools() always)
- `core/inference.py` lines 38–65 (no schema pruning)

#### What Claude Code Does

Claude Code uses **dynamic schema pruning** — it builds a "schema budget" per turn type (relational vs. autonomous) and cuts off tail tools when over budget. Schemas for rare tools are fetched lazily or gated behind higher trigger thresholds.

#### Fix Sketch

```python
# In core/tools.py

def select_tools_with_budget(
    message: str,
    max_tools: int = 5,
    schema_token_budget: int = 3000,  # conservative; was ~15k
) -> list[Tool]:
    """Pick tools whose schemas fit the budget AND whose triggers fire.
    
    If selected tools' schemas exceed budget, drop lowest-score ones until
    we're under. Triggers=() tools are never selected unless max_tools not met.
    """
    # [existing trigger logic]
    scored = [...]  # (score, idx, tool)
    
    # NEW: Estimate schema size, filter to budget
    candidates = []
    schema_bytes = 0
    for score, idx, tool in scored:
        tool_schema_size = _estimate_schema_tokens(tool.schema)
        if schema_bytes + tool_schema_size <= schema_token_budget:
            candidates.append(tool)
            schema_bytes += tool_schema_size
        else:
            break  # over budget, skip this and rest
    
    return candidates[:max_tools]

def _estimate_schema_tokens(schema: dict) -> int:
    """Rough token count for a JSON schema (assume 1 token per 4 chars)."""
    import json
    return len(json.dumps(schema)) // 4
```

**In agent.py**, replace line 313–316:
```python
selected_on_demand = select_tools_with_budget(
    last_user_msg,
    max_tools=5,
    schema_token_budget=(2000 if _is_short_msg else 3000)
)
```

#### Validation

- Log `schema_bytes` alongside tool list (agent.py line 319)
- Measure inference latency on relational channel (should drop 5–15%)
- Verify cold-start prompt eval on first turn of new session (should <40 sec)

#### Implementation Effort
**2 hours**: _estimate_schema_tokens() is trivial; select_tools_with_budget() is a copy-modify; testing is log-review.

---

### FRICTION POINT 2: Tool Return Shapes Are Unstandardized

**Impact: 5 / Effort: 3 → Ratio: 1.67**

#### What's Wrong

Every tool returns a `str`, but there's **no standard error/success envelope**. Some tools return:
- `"[error] ..."` (dispatch guards, missing args)
- `"[blocked] ..."` (tool_guards)
- `"✓ ..."` (some custom tools)
- Plain success text (most tools)
- Partial results with no status flag (browse_url on timeout)

The model has to infer whether a tool call succeeded by reading the text. This causes:

1. **Ambiguous retry logic**: "Did the file read fail because the file doesn't exist, or because the path was typo'd? Should I retry or ask John?"
2. **Mid-chain cascades**: Tool A fails with `[error] not found`, model tries tool B, tool B's result contains the word "error" in a sentence, model misinterprets and halts.
3. **Silent failures**: Some tools (cc_build, run_shell with timeout) return partial results that look like success but aren't. Model doesn't know whether to move on.

**Specific file:line**:
- `core/tools.py` lines 172–290 (dispatch returns raw handler result as str)
- `tools/shell.py`, `tools/filesystem.py`, `tools/cc_build.py` (all return bare strings with no envelope)
- No schema enforcement of error response format

#### What Claude Code Does

Claude Code returns structured objects: `{ status: "ok"|"error", data: {...}, message: "..." }`. The model receives JSON, not prose, so it never misreads a tool result.

#### Fix Sketch

```python
# In core/tools.py (new module level)

from dataclasses import dataclass
from typing import Any, Literal

@dataclass
class ToolResult:
    """Standard envelope for all tool results."""
    status: Literal["ok", "error", "cancelled", "blocked"]
    data: Any = None  # whatever the tool produces
    message: str = ""  # human-readable context
    
    def to_json(self) -> str:
        """Return JSON string for the model to parse."""
        import json
        return json.dumps({
            "status": self.status,
            "data": self.data,
            "message": self.message,
        })

# Update dispatch() to wrap handler returns:

def dispatch(name: str, arguments_json: str, cancel_event: ... | None = None) -> str:
    # [existing validation]
    
    try:
        result = t.handler(**kwargs)
        
        # If handler returned a ToolResult, convert to JSON
        if isinstance(result, ToolResult):
            return result.to_json()
        
        # If handler returned string, wrap as success
        if isinstance(result, str):
            if result.startswith("[error]"):
                return ToolResult(
                    status="error",
                    message=result[8:].strip()
                ).to_json()
            elif result.startswith("[blocked]"):
                return ToolResult(
                    status="blocked",
                    message=result[9:].strip()
                ).to_json()
            else:
                return ToolResult(
                    status="ok",
                    data=result,
                    message=""
                ).to_json()
    except Exception as e:
        return ToolResult(
            status="error",
            message=f"{type(e).__name__}: {e}"
        ).to_json()
```

**In agent.py**, update history parsing to deserialize ToolResult:

```python
# Round loop: append tool results to history
for result_str in results:
    try:
        parsed = json.loads(result_str)  # ToolResult.to_json()
        content = f"[{parsed['status']}] {parsed['message']}"
        if parsed['data']:
            content += f"\n{parsed['data']}"
        history.append({"role": "tool", "content": content})
    except json.JSONDecodeError:
        # Fallback for old-style string results
        history.append({"role": "tool", "content": result_str})
```

#### Validation

- Update 3–5 high-volume tools (exec_shell, read_file, browse_url) to return ToolResult
- Regression test: agent.respond() with mixed old-string and new-JSON returns
- Measure: mid-chain retry rate (should drop once model sees explicit `"status": "error"`)

#### Implementation Effort
**4–6 hours**: ToolResult class is quick; updating 20+ tool handlers is mechanical; most effort is testing cascading failures (tool A returns error → does tool B still work?).

---

### FRICTION POINT 3: Error Visibility Is Buried in String Responses

**Impact: 4 / Effort: 2 → Ratio: 2.0**

#### What's Wrong

Tool errors come back as prose strings mixed with agent reasoning. The model has no way to distinguish:
- A file read that failed (error) vs. succeeded with empty content
- A network timeout (retriable) vs. a 403 Forbidden (permanent)
- An argument validation error (model should fix it now) vs. a guard block (model should skip and move on)

**Specific patterns**:

1. **Guard blocks return `[error]` but model can't tell WHY** (tools.py line 251):
   ```
   [error] read_file: cache hit, same as last round. Content hash: abc123
   ```
   Is this a real error or just "we already read this, here's the digest"? Model doesn't know.

2. **Guard blocks for blocked URLs mix multiple concerns** (tool_guards.py lines 150–200):
   ```
   [error] browse_url: blocked (ResearchGate access denied; 1 prior attempt)
   ```
   Is it "blocked by our guard" or "the site returned 403"? Model might retry differently for each.

3. **Tool timeouts are silent** (shell.py, cc_build.py):
   ```
   (partial output, then silence)
   ```
   Did the command finish? Is it hung? Should I kill it?

#### What Claude Code Does

Claude Code tags errors by category in the message itself:
- `[error:validation] ...` — model should fix arguments and retry
- `[error:blocked] ...` — model should skip and try different tool
- `[error:network] ...` — model should retry with backoff
- `[error:timeout] ...` — model should wait or escalate

#### Fix Sketch

In `core/tool_guards.py`, add error categorization:

```python
class ErrorCategory:
    VALIDATION = "validation"      # args are wrong
    BLOCKED = "blocked"            # guard prevents retry
    NETWORK = "network"            # retriable
    TIMEOUT = "timeout"            # kill and move on
    INTERNAL = "internal"          # bug in handler

def check_pre_call(name: str, kwargs: dict) -> tuple[str, ErrorCategory] | None:
    """Return (message, category) if guard blocks; else None.
    
    Categories let the model decide: retry-able? skip? escalate?
    """
    # [existing guard logic]
    if url in _BLOCKED_URLS[conv]:
        reason = _BLOCKED_URLS[conv][url]
        return (
            f"browse_url: URL blocked by safety guard. "
            f"Prior attempt: {reason}. "
            f"Reason for block: site returned {reason.split()[-1]}",
            ErrorCategory.BLOCKED
        )
```

In `dispatch()`, apply category to error returns:

```python
guard_msg, category = tool_guards.check_pre_call(name, kwargs) or (None, None)
if guard_msg is not None:
    return ToolResult(
        status="error",
        message=guard_msg,
        category=category or ErrorCategory.INTERNAL
    ).to_json()
```

In system prompt (prompts.py), add an error-handling docstring:

```python
_ERROR_HANDLING_RULES = """\
## How to Handle Tool Errors

When a tool returns `{"status": "error"}`, read the "category" field:

- category: "validation" — your arguments are wrong. Fix and retry.
- category: "blocked" — our safety guard blocked it. Try a different tool.
- category: "network" — transient failure. Retry once with backoff.
- category: "timeout" — command took too long. Move on; don't retry.
- category: "internal" — bug in the tool. Report to John via notify_john.

Do NOT retry blocked errors or assume timeout is retriable.
"""
```

#### Validation

- Tag all guard returns in tool_guards.py (5 guard points)
- Tag all handler exceptions in dispatch() (1 place)
- Measure: model retry rate on blocked URLs (should drop to <2% from ~20%)

#### Implementation Effort
**2 hours**: Enum + string tags; update 5–6 guard check points; add docstring to system prompt.

---

## 4. The Top 3 Fixes to Ship First

### Fix #1: Standardize Tool Return Shapes (ToolResult Envelope)

**Why first**: Fixes the root cause of mid-chain cascades. Once the model receives JSON instead of prose, it stops misreading tool results and mid-chain retry patterns collapse.

**The fix**: Implement `ToolResult` dataclass (tools.py), update `dispatch()` to wrap all returns (success/error/blocked), teach agent.py to deserialize. Update 5 high-volume tools to return ToolResult explicitly. Model still receives human-readable text in history, but now structured and unambiguous.

**Diff sketch**:
```
core/tools.py:
  + ToolResult class (~20 lines)
  ~ dispatch() wrapping logic (~40 lines)

core/agent.py:
  ~ history parsing in tool-round loop (~15 lines, add json.loads)

tools/{shell,filesystem,cc_build,memory,goals}.py:
  ~ return ToolResult(...) instead of bare string (~10 per file)
```

**Validation**: Run full test suite + spot-check 3 autonomous goal ticks. Verify:
- Tool results appear as JSON in memory.conversations
- Model doesn't panic on `"status": "error"`
- Mid-chain retries drop

**Effort**: 4–5 hours (mechanical updates to handlers, testing deserialize fallback).

---

### Fix #2: Add Error Categories for Smart Retry Logic

**Why second**: Builds on Fix #1. Once tool results are structured, attach metadata so the model knows whether to retry, escalate, or move on.

**The fix**: Add `category` field to ToolResult. Enum: validation / blocked / network / timeout / internal. Tag all guard checks and exception handlers. Update system prompt with error-handling docstring.

**Diff sketch**:
```
core/tools.py:
  + ErrorCategory enum (~10 lines)
  ~ dispatch() to attach category (~20 lines)

core/tool_guards.py:
  ~ all guard returns to include category (~30 lines, 5 sites)

core/prompts.py:
  + _ERROR_HANDLING_RULES section (~15 lines)
  ~ build_system_prompt() to include it
```

**Validation**: Measure retry rate on previously-stuck scenarios:
- Blocked URL retries (should drop 90%+)
- Timeout retries (should drop to <10%)
- Validation errors that got re-tried (should drop 80%+)

**Effort**: 2–3 hours (tagging existing guards, enum def, docstring).

---

### Fix #3: Implement Schema Budget + Adaptive Tool Selection

**Why third**: Reduces token overhead long-term. Once tools are structured (Fixes 1–2), invest in efficiency. This fix is slightly riskier (affects classifier behavior) but highest ROI once validated.

**The fix**: Add `_estimate_schema_tokens()`. Modify `select_tools()` to respect a budget (3k tokens for normal, 1.5k for short messages). Drop lowest-score tools if over budget. Keeps high-value tools, cuts cruft.

**Diff sketch**:
```
core/tools.py:
  + _estimate_schema_tokens() (~10 lines)
  ~ select_tools() → select_tools_with_budget() (~25 lines)

core/agent.py:
  ~ tool selection call, pass budget param (~5 lines)
  ~ logging: add schema_bytes to log line (~2 lines)
```

**Validation**: Compare inference latency (relational channel) before/after:
- Cold start (first turn of session): should drop from ~40s to <35s
- Warm turns: should stay same (cache hit)
- Tool coverage: verify on_demand tools still fire for their intended messages

**Effort**: 2 hours (token estimator is trivial, classifier change is copy-modify, test is latency log review).

---

## 5. What NOT to Touch

### Behavioral Guards (tool_guards.py)
The guards work *because they're deterministic*. Don't try to LLM-ify them (i.e., don't ask the model "should I retry this?"). The in-flight dedup, blocked URL list, and recent-read cache all survive Qwen's failure modes because they're regex + state, not learned heuristics. Leave them alone.

### Loop-Detection Heuristics (agent.py lines 89–117, heartbeat.py lines 66–93)
The intra-call loop guard and narration-loop guard are tuned to Charles's specific failure modes (108× repetitions, >50% narration in notes). Don't adjust thresholds without Friday sundown tests — these guards prevent runaway chains that burn $$ on MLX inference.

### Multi-Round Tool Chains and Prefix Caching
The tiering system (CORE stable, ON_DEMAND dynamic) is working. The MLX cache warm-up pattern is sound. Don't consolidate all tools to CORE or flatten to a single tier — that burns 2–3× inference latency.

### Thinking Mode Toggle (inference.py)
The per-channel thinking policy (ON for CHARLES_LOG, OFF for JOHN_CHARLES) is a live experiment (2026-05-12). Early results show 5–15× latency cost but improved reliability on multi-step chains. Let it run through next Sunday Test before tweaking.

### Memory Replay and Semantic Recall
Recent redesign (2026-05-12): filter role='progress' but NOT tool results. Model sees full chain on every call. This fixed the "Charles gaslights himself" bug where he'd claim a prior successful tool_call but find no evidence in replayed history. DO NOT strip tool results at write time.

---

## 6. Open Questions for John

1. **Thinking mode experiment**: How many CHARLES_LOG ticks should run with thinking=True before we declare it "working" or "too slow"? Are there specific goal types (research vs. build) where thinking is more/less valuable?

2. **On-demand classifier**: The current substring-match is naive. Are there goals/domains where false-positive tool selection causes issues? (E.g., "project" in a message triggers 5 project_* tools even if user only wants status.) Should we add a second-stage ranker (embed message + tool summary, cosine similarity)?

3. **Schema budget**: Is 3k tokens per-turn aggressive enough, or should it vary by conversation type? JOHN_CHARLES (relational) has tighter budget; CHARLES_LOG (autonomous) might benefit from more tools available. Current fix assumes uniform budget.

4. **Tool timeouts**: Several tools (cc_build, run_shell, exec_shell) have vague timeout behavior. Should we standardize on a single timeout library + explicit "kill after X sec" semantics? The current partial-result behavior is silent.

5. **ToolResult rollout**: Do you want to update all 78 tools at once, or start with a subset (top-10 by invocation count, per audit 2026-05-11) and backfill? All-at-once is cleaner but riskier (one broken tool breaks history parsing).

6. **Error categories**: Is the 5-category enum (validation / blocked / network / timeout / internal) sufficient, or are there other categories Charles hits? (E.g., "rate_limited", "auth_required"?)

---

## Summary Table: Friction Points Ranked by Impact/Effort

| Rank | Point | Impact | Effort | Ratio | Est. Hours | Ship Order |
|------|-------|--------|--------|-------|-----------|------------|
| 1 | Standardized tool returns (ToolResult) | 5 | 3 | 1.67 | 4–5 | 1st |
| 2 | Error categories + smart retry | 4 | 2 | 2.0 | 2–3 | 2nd |
| 3 | Schema budget + adaptive selection | 5 | 2 | 2.5 | 2 | 3rd |
| 4 | Prompt instruction coverage (goal-setting) | 3 | 2 | 1.5 | 1–2 | Later |
| 5 | Tool timeout standardization | 2 | 3 | 0.67 | 3–4 | Later |

---

**Report completed 2026-05-13, 21:45 EST.**
