#!/bin/bash
# update_session.sh - Append data to an existing session JSON file
# Usage: update_session.sh <session_file> [field] [value]
# Fields: response, tool_calls, file_diffs, tokens (prompt/completion/total),
#         status, outcome, notes, prompt

set -euo pipefail

SESSION_FILE="${1:?Usage: update_session.sh <session_file> [field] [value]}"

if [ ! -f "$SESSION_FILE" ]; then
  echo "Error: Session file not found: $SESSION_FILE"
  exit 1
fi

FIELD="${2:-notes}"
VALUE="${3:-$(date -u +%Y-%m-%dT%H:%M:%SZ)}"

# Simple JSON field update using python (more reliable than jq for edge cases)
python3 -c "
import json, sys

with open('$SESSION_FILE', 'r') as f:
    data = json.load(f)

field = '$FIELD'
value = '''$VALUE'''

if field == 'tokens':
    # value format: 'prompt:100,completion:50'
    parts = value.split(',')
    for part in parts:
        key, val = part.split(':')
        data['tokens'][key.strip()] = int(val.strip())
elif field == 'tool_calls' or field == 'file_diffs':
    # Append a JSON array element
    import ast
    item = ast.literal_eval(value)
    data[field].append(item)
elif field == 'status' or field == 'outcome' or field == 'notes' or field == 'prompt' or field == 'response':
    data[field] = value
else:
    data[field] = value

with open('$SESSION_FILE', 'w') as f:
    json.dump(data, f, indent=2)

print(f'Updated {field} in $SESSION_FILE')
"
