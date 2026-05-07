#!/bin/bash
# capture_session.sh - Create a new Claude Code session log file
# Usage: capture_session.sh <session_name> [category]
# Creates a JSON log file in workspace/sessions/

SESSIONS_DIR="/Users/home/charles/workspace/sessions"
mkdir -p "$SESSIONS_DIR"

NAME="${1:?Usage: capture_session.sh <session_name> [category]}"
CATEGORY="${2:-general}"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
SESSION_ID=$(echo "$NAME" | tr '[:upper:]' '[:lower:]' | tr ' ' '_' | tr -cd '[:alnum:]_-')
SESSION_FILE="$SESSIONS_DIR/${SESSION_ID}.json"

cat > "$SESSION_FILE" <<EOF
{
  "session_id": "$SESSION_ID",
  "name": "$NAME",
  "category": "$CATEGORY",
  "created": "$TIMESTAMP",
  "status": "active",
  "prompt": "",
  "response": "",
  "tool_calls": [],
  "file_diffs": [],
  "tokens": {
    "input": 0,
    "output": 0,
    "total": 0
  },
  "outcome": "",
  "notes": ""
}
EOF

echo "Created session: $SESSION_FILE"
