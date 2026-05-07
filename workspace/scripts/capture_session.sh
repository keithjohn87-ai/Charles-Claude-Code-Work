#!/bin/bash
# capture_session.sh - Create a new session JSON file for Claude Code instrumentation
# Usage: capture_session.sh <session_name> [category]
# Creates a JSON file in workspace/sessions/ with a unique session ID

set -euo pipefail

SESSIONS_DIR="/Users/home/charles/workspace/sessions"
mkdir -p "$SESSIONS_DIR"

SESSION_NAME="${1:?Usage: capture_session.sh <session_name> [category]}"
CATEGORY="${2:-general}"
SESSION_ID="session_$(date +%Y%m%d_%H%M%S)_${SESSION_NAME//[^a-zA-Z0-9]/_}"
SESSION_FILE="$SESSIONS_DIR/${SESSION_ID}.json"

cat > "$SESSION_FILE" <<EOF
{
  "session_id": "$SESSION_ID",
  "session_name": "$SESSION_NAME",
  "category": "$CATEGORY",
  "created_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "status": "active",
  "prompt": "",
  "response": "",
  "tool_calls": [],
  "file_diffs": [],
  "tokens": {
    "prompt": 0,
    "completion": 0,
    "total": 0
  },
  "outcome": "",
  "notes": ""
}
EOF

echo "Created session: $SESSION_ID"
echo "File: $SESSION_FILE"
