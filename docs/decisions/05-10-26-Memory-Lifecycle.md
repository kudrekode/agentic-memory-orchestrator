# 05-10-26 — Memory lifecycle and ownership

## Decision

Agent Memory treats memories as **proposals first, durable records second**.

A frontier model may propose a `MemoryCandidate`, but it never writes to SQLite
or chooses server-owned fields. Agent Memory validates, transforms, looks up existing
knowledge, and persists the final result. The MCP server is the thin interface
to this pipeline.

LangGraph is not part of the initial write path. The initial pipeline is
deterministic application code and ordinary service functions. A graph
orchestrator may be introduced later for consolidation or human-review
workflows if their branching and retries justify it.

## Why

- A model has the context to identify potentially valuable memories.
- Code can reliably enforce contracts, IDs, timestamps, importance arithmetic,
  project isolation, and database transactions.
- SQLite must be a durable store, not a policy engine.
- The lifecycle must leave an inspectable reason for every write or rejection.

## Core ownership rule

```text
Frontier model: propose meaning
Agent Memory:         decide whether and how it may be stored
SQLite:         durably store the decided result
```

The frontier model supplies:

- proposed memory type;
- content and rationale;
- confidence category;
- importance dimensions;
- related-memory search hints.

Agent Memory supplies or decides:

- prefixed ULID;
- project ID;
- timezone-aware timestamps;
- source attribution;
- final importance category;
- semantic revision number;
- persistence status and links;
- duplicate, conflict, and review routing.

## A → B → C → D: candidate capture

```text
A. Frontier-capable agent
   │ produces a structured MemoryCandidate
   ▼
B. MCP / submit_memory_candidates
   │ validates the candidate envelope and project boundary
   ▼
C. Agent Memory pipeline
   │ 1. business validation
   │ 2. transform into a typed server-owned record
   │ 3. retrieve possible existing memories
   │ 4. decide create / support / revise / conflict / ignore
   ▼
D. SQLite transaction
   │ persists records, revisions, links, and statuses atomically
   ▼
Structured result returned to the agent
```

### B — MCP boundary

The MCP tool accepts a bundle of candidates, not raw SQL and not direct stored
records. It authenticates or identifies the caller if required, selects the
target project, and passes the bundle to the application service.

The MCP tool must not:

- expose a general SQL execution tool;
- accept model-generated IDs, timestamps, or importance values as authoritative;
- directly update semantic memory by namespace/key;
- bypass validation because the caller is a frontier model.

### C.1 — business validation

The correct validator is selected from `proposed_type`.

```text
episode              → meaningful, coherent event with a credible outcome
semantic             → reusable, scoped fact with namespace/key
lesson               → WHEN / DO / BECAUSE, not merely a fact
working_state_update → active work; hypotheses remain hypotheses
ignore               → no durable record
```

Validation may reject a candidate before any database lookup. A rejection is a
normal result, not a system error.

### C.2 — transformation

An accepted candidate is transformed into one of the typed stored models:

```text
Episode candidate  → Episode
Semantic candidate → SemanticMemory (revision 1 only when no existing key)
Lesson candidate   → Lesson
Working-state      → update applied to the current WorkingState
```

Transformation is where Agent Memory adds server-owned values. For Episodes and
Semantic memories, it calculates importance from the five dimensions rather
than trusting a model-provided category.

Working-state updates are intentionally different: they must be merged with
the current project's single mutable state, so they are not independently
materialized as a new durable record.

### C.3 — existing-memory decision

Only after an accepted candidate has a typed shape does Agent Memory search the
project's existing records.

```text
No relevant match                       → create new record
Exact same semantic knowledge           → add supporting evidence/link
Same namespace/key, compatible addition → create semantic revision
Same namespace/key, incompatible claim  → mark conflict or request review
Duplicate episode or lesson              → ignore or link as supporting evidence
```

This step is database-dependent. It must be project-scoped and must not allow
a candidate from one project to influence another.

### D — atomic persistence

Each accepted decision is persisted in one transaction:

```text
create record or semantic revision
    + create MemoryLink provenance records
    + update consolidation status where applicable
    + update WorkingState if included
    = commit
```

If any required write fails, none of the writes in that decision are committed.

## Recall path

Recall does not mutate memory:

```text
Agent asks MCP for context
   → Agent Memory scopes to a project
   → fetches current WorkingState
   → fetches relevant Semantic memories and Lessons
   → optionally includes recent/pending Episodes
   → returns structured context
```

Vector search and local embeddings can improve ranking later, but they do not
change the source of truth: SQLite's structured records remain canonical.

## Consolidation path

Consolidation turns episodic evidence into durable knowledge; it is not a
second way to bypass the write pipeline.

```text
1. Select pending Episodes for one project
2. Retrieve related Semantic memories, revisions, and Lessons
3. Frontier model proposes one of:
   unchanged | support | expand | correct | split | dispute | supersede | lesson
4. Agent Memory validates authority, references, revision number, and allowed state transition
5. Agent Memory writes the revision/link/lesson transactionally
6. Mark processed Episodes and refresh WorkingState when appropriate
7. Return a concise handoff-ready result
```

An inferred proposal that contradicts a confirmed developer correction is not
automatically applied. It is routed to a disputed or review state.

## Implementation status on 05-10-26

Implemented before persistence:

- Pydantic models and enums;
- candidate business validators;
- canonical prefixed ULID generation and validation;
- timezone-aware stored timestamps;
- deterministic importance calculation and consistency checks;
- transformation from Episode, Semantic, and Lesson candidates to typed,
  server-owned records;
- unit tests for the above.

Still required with SQLite:

- `MemoryCandidateBundle` and MCP tools;
- repository and transaction layer;
- project-scoped lookup, duplicate detection, and conflict routing;
- semantic revision monotonicity and status-transition rules;
- memory-link existence, relationship-pair, and self-link checks;
- working-state merge/update service;
- persistence integration tests using a temporary SQLite database.

## Consequence

The next implementation slice is SQLite schema plus a thin persistence service
that completes steps C.3 and D. It should be tested against temporary
databases before any `data/dev/memory.db` is created or used for real memory.
