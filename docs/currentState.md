# Current State

## Goal

Give coding agents persistent, trustworthy context across sessions on any project.

The system should eventually:

- remember architectural facts
- remember decisions
- remember debugging outcomes
- remember corrections / lessons
- track current work
- generate end-of-session handoffs
- restore context in new agent sessions
- expose useful memory through Obsidian

## Where we are

Phases 0–3 of the [roadmap](ROADMAP.md) are in place. `/memory-save` and `/memory-status` call the MCP tools. `/memory-close` is designed and not implemented.

## Built

### Memory database

SQLite is the canonical store. One local database file per developer and environment, for example `data/dev/memory.db` or `data/live/memory.db`. The path comes from `AGENT_MEMORY_DB`.

Stored records:

- projects
- working state
- episodes
- semantic memories and revisions
- lessons
- memory links

The write path is candidate-first. An agent proposes a `MemoryCandidate`. The service validates it, assigns ids and timestamps, calculates importance, checks for duplicates and conflicts, and persists the result. The agent does not write SQL or stored records directly.

### MCP server

A local stdio server, `agent-memory-mcp`, exposes four tools:

- `get_memory_context`
- `get_memory_status`
- `submit_memory_candidates`
- `sync_obsidian`

Every tool accepts an optional `project_id`. When it is omitted the server uses `AGENT_MEMORY_PROJECT_ID`.

Cursor project skills call those tools:

- `/memory-save` submits one candidate bundle through `submit_memory_candidates`.
- `/memory-status` reads `get_memory_status` and `get_memory_context`.

### Setup CLI

`agent-memory init --name <name>` creates the database and a project and prints the env values for the MCP config. `agent-memory projects` lists projects.

### Obsidian sync

`src/obsidian_sync.py` renders one project into markdown: one note per memory, index pages, and `[[wikilinks]]` by id. A manifest tracks generated files so a later sync can remove stale notes.

`sync_obsidian` exposes that render on the MCP server. A successful `submit_memory_candidates` refreshes the vault when the project has `obsidian_path` or `AGENT_MEMORY_VAULT` is set. With neither configured, the save still succeeds and the result reports that the vault was skipped. A vault error is reported on the save result and does not undo the SQLite write.

## Not built yet

- `/memory-close`
- embedding pipeline and semantic recall
- automatic memory extraction
- session handoffs
- memory consolidation and semantic revisions through the MCP tools

## Current decision

SQLite is the canonical memory store.

Obsidian is not the source of truth. Obsidian notes are generated from structured memory, and edits in the vault are replaced on the next sync.

## Immediate next step

Phase 4 is `/memory-close`: consolidate saved memory and write a handoff. It needs memories that `/memory-save` has already stored.
