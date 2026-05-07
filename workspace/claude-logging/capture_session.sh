#!/bin/bash
# capture_session.sh — Create a new Claude Code session log file
# Usage: ./capture_session.sh <session_name> [category]
# Creates a JSON session file with metadata and a sessions directory

set -euo pipefail

SESSIONS_DIR="/Users/home/charles/workspace/claude-logging/sessions"
mkdir -p "$SESSIONS_DIR"

NAME="${1:?Usage: capture_session.sh <session_name> [category]}"
CATEGORY="${2:-general}"
SESSION_ID=$(echo "$NAME" | tr '[:upper:]' '[:lower:]' | tr ' ' '_' | tr -cd '[:alnum:]_-')
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
SESSION_FILE="$SESSIONS_DIR/${SESSION_ID}.json"

cat > "$SESSION_FILE" <<EOF
{
  "session_id": "${SESSION_ID}",
  "name": "${NAME}",
  "category": "${CATEGORY}",
  "created": "${TIMESTAMP}",
  "status": "active",
  "prompt_log": [],
  "response_log": [],
  "tool_calls": [],
  "file_diffs": [],
  "token_usage": {
    "total_prompt_tokens": 0,
    "total_completion_tokens": 0,
    "total_tokens": 0
  },
  "notes": []
}
EOF

echo "Created session: $SESSION_FILE"
echo "ID: $SESSION_ID"
echo "Category: $CATEGORY"
