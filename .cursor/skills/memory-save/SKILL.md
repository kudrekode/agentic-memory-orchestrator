---
name: memory-save
description: >-
  Save a project memory checkpoint from the current coding chat by submitting
  MemoryCandidate objects through the submit_memory_candidates MCP tool.
  Use when the user runs /memory-save or asks to save engineering memory, a
  checkpoint, or what was just learned.
disable-model-invocation: true
---

# /memory-save

Capture meaningful knowledge from this chat. Do not close the session, consolidate memory, or write a handoff.

## Authority

Read `docs/memory-agent-contract.md` and follow it. Propose candidates only. Do not write SQLite, invent ids, timestamps, revision numbers, or an importance category.

## Project

Omit `project_id` so the server uses its configured default (`AGENT_MEMORY_PROJECT_ID`). Pass a `prj_` id only when the user names one. Do not invent a project id. If the server says no project is configured, tell the user to run `agent-memory init` and stop.

## Steps

1. Call `get_memory_context`.
2. From this chat, keep only memories that would be expensive to lose. Skip chatter, transcripts, and trivial edits. If nothing qualifies, say so and stop without calling `submit_memory_candidates`.
3. Call `submit_memory_candidates` with one bundle. Omit `submitted_by` and `submitted_at`; the server sets them.

```json
{
  "session_summary": "Short checkpoint summary.",
  "candidates": [],
  "working_state_update": null
}
```

`working_state_update` is a sibling of `candidates`, never an item inside `candidates`. It is a candidate whose `proposed_type` is `working_state_update`. Episodes, semantic memories, lessons, and `ignore` items go in `candidates`.

4. Read every outcome and the `obsidian` status. Report created, linked, duplicate, conflict, rejected, and ignored items with id and reason. Say whether the vault refreshed, was skipped, or failed. A vault failure does not undo the SQLite write.

Episodes and semantic memories require `importance_dimensions`, each an integer from 0 through 3. Lessons do not. A lesson `instruction`, and each working-state `next_actions` item, must start with one of: add, check, confirm, create, disable, enable, inspect, run, test, use, verify, update, review, avoid, prefer, ensure, set, remove, restart, deploy, investigate, compare, open, read, write, fix. Other field rules are in the contract.
