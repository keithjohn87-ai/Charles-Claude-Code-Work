# Claude Code Logging System

## Overview

This system captures and logs Claude Code sessions for analysis, optimization, and knowledge retention.

## Quick Start

```bash
# 1. Create a session
./capture_session.sh <session_name> [category]

# 2. During the session, log data:
./update_session.sh <session_id> prompt "the user prompt"
./update_session.sh <session_id> response "Claude's response"
./update_session.sh <session_id> tool_call "read_file: config.py"
./update_session.sh <session_id> file_diff "modified config.py: changed port 8080->8081"
./update_session.sh <session_id> tokens 1500
./update_session.sh <session_id> outcome "Success - config updated"
./update_session.sh <session_id> notes "Claude took 3 attempts"

# 3. Review all sessions
ls -la sessions/
cat sessions/<session_id>.json
```

## Session Categories

| Category | Description |
|----------|-------------|
| skill_creation | Creating new Claude Code skills/rules |
| code_generation | Writing new code from scratch |
| refactoring | Restructuring existing code |
| debugging | Finding and fixing bugs |
| multi_file | Operations across multiple files |
| integration | Connecting systems/APIs |
| build_deploy | Build, test, deployment tasks |
| documentation | Writing or updating docs |
| testing | Writing or running tests |
| architecture | Design and structural decisions |

## JSON Schema

Each session file contains:
- `session_id`: Unique identifier (lowercase, underscored)
- `name`: Human-readable name
- `category`: One of the categories above
- `created`: ISO 8601 UTC timestamp
- `status`: "active" or "complete"
- `prompt`: The full user prompt sent to Claude
- `response`: Claude's response text
- `tool_calls`: Array of tool call descriptions
- `file_diffs`: Array of file change descriptions
- `tokens`: Object with input, output, total counts
- `outcome`: Result summary
- `notes`: Additional observations

## Session Count

Target: 20 trial sessions across all categories.
Day 7 Gate: Review captures, identify gaps, refine logging.
