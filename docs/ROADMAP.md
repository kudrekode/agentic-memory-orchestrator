# Roadmap

```text
PHASE 0 — DOCUMENT THE DESIGN             done
PHASE 1 — BASIC MEMORY DATABASE           done
PHASE 2 — MCP INTERFACE                   first version done
PHASE 3 — OBSIDIAN SYNC                   done
PHASE 4 — SESSION CLOSE AND HANDOFFS      not started
PHASE 5 — CONSOLIDATION AND REVISIONS     not started
PHASE 6 — LOCAL EMBEDDINGS AND RECALL     not started
PHASE 7 — MODEL EVALUATION                not started
```

## Phase 4 — Session close and handoffs

- `get_close_context` MCP tool returning working state, episodes since the last close, related semantic memory, lessons, and the previous handoff.
- `/memory-close` skill that runs in a fresh chat, using only stored memory.
- A stored handoff record rendered to the vault.

## Phase 5 — Consolidation and revisions

- MCP tools to apply semantic revisions (`expand`, `correct`, `split`, `dispute`, `supersede`) with monotonic revision numbers and allowed status transitions.
- Mark processed episodes; route contradictions of developer-confirmed memory to review.
- Checkpoint ids grouping everything one save created.

## Phase 6 — Local embeddings and recall

- Local embedding model (for example through Ollama) for related-memory lookup and ranked recall.
- SQLite stays canonical; vectors are a derived index.

## Phase 7 — Model evaluation

- A fixed evaluation set of episodes, semantic memories, revisions, and conflicts.
- Score candidate models on fact preservation, conflict handling, revision choice, invented facts, lesson usefulness, scope, and provenance.
- Allow cheaper or local models more authority only where the scores justify it.
