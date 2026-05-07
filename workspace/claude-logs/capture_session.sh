#!/bin/bash
# capture_session.sh — Wrapper script to capture a Claude Code session
# Usage: ./capture_session.sh <session_id> <category> "<prompt>"
#
# Captures: prompt, response text, tool calls, file diffs, token usage
# Output: JSON log file in workspace/claude-logs/sessions/

set -euo pipefail

SESSION_ID="${1:?Usage: capture_session.sh <session_id> <category> \"<prompt>\"}"
CATEGORY="${2:?Category (e.g., skill-creation, code-gen, refactoring, debugging, multi-file, integration, build-deploy, documentation, testing, architecture)}"
PROMPT="${3:?Prompt text}"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
LOG_DIR="/Users/home/charles/workspace/claude-logs/sessions"
mkdir -p "$LOG_DIR"

LOG_FILE="$LOG_DIR/session_${SESSION_ID}.json"

# Initialize the session log
cat > "$LOG_FILE" <<EOF
{
  "session_id": "${SESSION_ID}",
  "category": "${CATEGORY}",
  "timestamp": "${TIMESTAMP}",
  "prompt": $(python3 -c "import json,sys; print(json.dumps(sys.argv[1]))" "$PROMPT"),
  "status": "in_progress",
  "responses": [],
  "tool_calls": [],
  "file_diffs": [],
  "token_usage": {
    "input": 0,
    "output": 0,
    "total": 0
  },
  "notes": ""
}
EOF

echo "Session log created: $LOG_FILE"
echo "Session ID: $SESSION_ID"
echo "Category: $CATEGORY"
echo "Prompt: $PROMPT"
echo ""
echo "Next: Run Claude Code with this prompt, then append results using:"
echo "  ./update_session.sh $SESSION_ID '<response_json>' '<tool_calls_json>' '<diffs_json>' <input_tokens> <output_tokens>"
