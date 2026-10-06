---
name: memory-status
description: >-
  Read the current project memory without writing. Use when the user runs
  /memory-status or asks what the memory server currently has saved.
disable-model-invocation: true
---

# /memory-status

Read-only. Do not call `submit_memory_candidates` or `sync_obsidian`. Do not invent a handoff or pending-review count; those are not stored yet.

## Project

Omit `project_id` so the server uses its configured default (`AGENT_MEMORY_PROJECT_ID`). Pass a `prj_` id only when the user names one. Do not invent a project id.

## Steps

1. Call `get_memory_status` and `get_memory_context`.
2. Report only what those tools returned, in this shape:

```text
Current focus:
<working state focus, or none>

Status:
<working state status, or none>

Known:
- ...

Open:
- unknowns, blockers, and hypotheses that are still open

Recent episodes:
- <id> — <title> — <outcome>

Active semantic memories:
- <namespace>/<key> — <statement>

Active lessons:
- <title> — <instruction>

Next actions:
1. ...

Counts:
- working state: yes/no
- active semantic: N
- active lessons: N
- recent episodes: N
```

Leave a section empty when the tool returned nothing for it.
