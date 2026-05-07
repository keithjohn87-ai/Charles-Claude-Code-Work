#!/bin/bash
# update_session.sh — Append results to a captured session log
# Usage: ./update_session.sh <session_id> "<response_json>" "<tool_calls_json>" "<diffs_json>" <input_tokens> <output_tokens>

set -euo pipefail

SESSION_ID="${1:?Missing session_id}"
LOG_FILE="/Users/home/charles/workspace/claude-logs/sessions/session_${SESSION_ID}.json"

if [ ! -f "$LOG_FILE" ]; then
  echo "ERROR: Session log not found: $LOG_FILE"
  echo "Run capture_session.sh first."
  exit 1
fi

RESPONSES="${2:-[]}"
TOOL_CALLS="${3:-[]}"
FILE_DIFFS="${4:-[]}"
INPUT_TOKENS="${5:-0}"
OUTPUT_TOKENS="${6:-0}"

# Use Python to properly merge JSON into the log file
python3 -c "
import json, sys

log_file = sys.argv[1]
responses = json.loads(sys.argv[2])
tool_calls = json.loads(sys.argv[3])
file_diffs = json.loads(sys.argv[4])
input_tokens = int(sys.argv[5])
output_tokens = int(sys.argv[6])

with open(log_file, 'r') as f:
    log = json.load(f)

# Append responses (as a list or single item)
if isinstance(responses, list):
    log['responses'].extend(responses)
else:
    log['responses'].append(responses)

# Append tool calls
if isinstance(tool_calls, list):
    log['tool_calls'].extend(tool_calls)
else:
    log['tool_calls'].append(tool_calls)

# Append file diffs
if isinstance(file_diffs, list):
    log['file_diffs'].extend(file_diffs)
else:
    log['file_diffs'].append(file_diffs)

# Update token usage
log['token_usage']['input'] += input_tokens
log['token_usage']['output'] += output_tokens
log['token_usage']['total'] += input_tokens + output_tokens

# Mark complete
log['status'] = 'complete'

with open(log_file, 'w') as f:
    json.dump(log, f, indent=2)

print(f'Updated: {log_file}')
print(f'  Responses: {len(log[\"responses\"])} total')
print(f'  Tool calls: {len(log[\"tool_calls\"])} total')
print(f'  File diffs: {len(log[\"file_diffs\"])} total')
print(f'  Tokens: {log[\"token_usage\"][\"total\"]} (in: {log[\"token_usage\"][\"input\"]}, out: {log[\"token_usage\"][\"output\"]})')
" "$LOG_FILE" "$RESPONSES" "$TOOL_CALLS" "$FILE_DIFFS" "$INPUT_TOKENS" "$OUTPUT_TOKENS"
