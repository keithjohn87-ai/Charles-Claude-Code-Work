#!/bin/bash
# update_session.sh - Update a Claude Code session log with data
# Usage: update_session.sh <session_id> <field> <value>
# Fields: prompt, response, tool_calls (append), file_diff (append), tokens (add), outcome, notes

SESSIONS_DIR="/Users/home/charles/workspace/sessions"
SESSION_FILE="$SESSIONS_DIR/${1}.json"

if [ ! -f "$SESSION_FILE" ]; then
  echo "Error: Session $1 not found. Run capture_session.sh first."
  exit 1
fi

FIELD="$2"
VALUE="$3"

case "$FIELD" in
  prompt)
    python3 -c "
import json
with open('$SESSION_FILE') as f: s = json.load(f)
s['prompt'] = '''$VALUE'''
with open('$SESSION_FILE','w') as f: json.dump(s, f, indent=2)
"
    ;;
  response)
    python3 -c "
import json
with open('$SESSION_FILE') as f: s = json.load(f)
s['response'] = '''$VALUE'''
with open('$SESSION_FILE','w') as f: json.dump(s, f, indent=2)
"
    ;;
  tool_call)
    python3 -c "
import json
with open('$SESSION_FILE') as f: s = json.load(f)
s['tool_calls'].append('$VALUE')
with open('$SESSION_FILE','w') as f: json.dump(s, f, indent=2)
"
    ;;
  file_diff)
    python3 -c "
import json
with open('$SESSION_FILE') as f: s = json.load(f)
s['file_diffs'].append('$VALUE')
with open('$SESSION_FILE','w') as f: json.dump(s, f, indent=2)
"
    ;;
  tokens)
    python3 -c "
import json
with open('$SESSION_FILE') as f: s = json.load(f)
s['tokens']['input'] += $VALUE
s['tokens']['total'] += $VALUE
with open('$SESSION_FILE','w') as f: json.dump(s, f, indent=2)
"
    ;;
  outcome)
    python3 -c "
import json
with open('$SESSION_FILE') as f: s = json.load(f)
s['outcome'] = '''$VALUE'''
s['status'] = 'complete'
with open('$SESSION_FILE','w') as f: json.dump(s, f, indent=2)
"
    ;;
  notes)
    python3 -c "
import json
with open('$SESSION_FILE') as f: s = json.load(f)
s['notes'] = '''$VALUE'''
with open('$SESSION_FILE','w') as f: json.dump(s, f, indent=2)
"
    ;;
  *)
    echo "Unknown field: $FIELD (prompt|response|tool_call|file_diff|tokens|outcome|notes)"
    exit 1
    ;;
esac

echo "Updated $SESSION_FILE [$FIELD]"
