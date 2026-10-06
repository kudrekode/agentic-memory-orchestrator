# Agent Memory — Memory Orchestration Design

## Purpose

This document defines how Agent Memory should orchestrate memory capture, enrichment, consolidation, and session handoff when the developer uses frontier models through Cursor but does **not** have direct frontier-model API access.

The core design principle is:

```text
Cursor frontier model
        ↕
Agent Memory MCP tools
        ↕
local memory system
```

Cursor provides high-context reasoning while an engineering conversation is active.

Agent Memory provides durable memory, deterministic validation, local enrichment, provenance, and persistence.

Agent Memory must not require direct access to OpenAI, Anthropic, or other frontier-model APIs.

---

# Core Architecture

```text
                     Cursor
              frontier coding model
                       │
                       │ MCP
                       ▼
                Agent Memory Server
                       │
        ┌──────────────┼──────────────┐
        │              │              │
    validation      retrieval      orchestration
        │              │              │
        └──────────────┼──────────────┘
                       │
              ┌────────┴────────┐
              │                 │
           SQLite             Ollama
              │                 │
              │          embeddings / local
              │          enrichment tasks
              │
              ▼
          Obsidian
      human-readable view
```

The frontier model sits **above** Agent Memory.

Agent Memory should not assume it can internally invoke the Cursor model.

Instead, Cursor reasons, calls Agent Memory tools, receives structured results, reasons again if necessary, and then calls another Agent Memory tool.

---

# Local MCP Deployment

Agent Memory should initially run entirely on the developer's local machine.

A possible local layout:

```text
~/code/agentic-memory-orchestrator/
├── src/
├── data/
│   ├── dev/
│   │   └── memory.db
│   └── live/
│       └── memory.db
├── prompts/
├── docs/
└── mcp_server.py
```

Other local components may include:

```text
the application repository you are working on
Agent Memory repository
a local model runtime such as Ollama (optional, future)
Obsidian vault (optional)
Cursor or another MCP client
```

No cloud hosting is required for v1.

Cursor connects to the local Agent Memory MCP server using a local MCP configuration.

The Agent Memory codebase can remain completely separate from the application repository whose work it remembers.

---

# Why Cursor Is Part of the Orchestration

The strongest model already has access to the active coding conversation.

That conversation may contain:

- debugging attempts;
- failed hypotheses;
- repository changes;
- architectural reasoning;
- tool results;
- explicit developer corrections;
- confirmation that a fix worked.

Re-sending all of this to a smaller local model after the fact would often discard useful context and duplicate work.

Therefore:

> High-context memory extraction should happen while the frontier model still has the live engineering context.

Agent Memory then receives structured candidates rather than requiring a local model to reconstruct the session.

---

# Model Responsibility Split

## Frontier model

Use the active Cursor frontier model for high-judgment tasks.

Examples:

- determine what from the current session is worth remembering;
- identify meaningful Episodes;
- distinguish Episode vs Semantic vs Lesson;
- understand whether a fix was actually confirmed;
- identify durable engineering decisions;
- propose semantic corrections or expansions;
- resolve ambiguous memory conflicts;
- perform important consolidation reasoning;
- generate useful Lessons from experience.

The frontier model proposes changes.

It does not directly control SQLite.

## Local Ollama models

Use local models for low-risk and repeatable enrichment tasks.

Examples:

- embeddings;
- entity extraction;
- tag suggestions;
- topic grouping;
- related-memory candidate matching;
- low-risk duplicate detection;
- summary assistance;
- search-query generation;
- clustering Episodes before consolidation.

Local models may eventually perform more memory reasoning after they have been benchmarked against a known evaluation set.

## Deterministic application code

Normal application logic should own all operations that do not require semantic reasoning.

Examples:

- ULID generation;
- Pydantic validation;
- importance calculation;
- confidence mapping;
- project isolation;
- revision numbering;
- database transactions;
- existence checks;
- duplicate exact-match checks;
- valid status transitions;
- memory-link validation;
- persistence;
- Obsidian sync.

---

# Core Workflow Commands

Agent Memory should initially expose three developer-facing workflows:

```text
/memory-save
/memory-status
/memory-close
```

These may be implemented as Cursor Skills that invoke underlying MCP tools.

The slash command is the user-facing workflow.

The MCP tools are the application primitives beneath it.

---

# `/memory-save`

## Purpose

`/memory-save` captures useful knowledge from the **current active coding context**.

It answers:

> What have we just learned that would be expensive or annoying to lose?

`memory-save` should be used at meaningful checkpoints during a long coding session.

Examples:

- a difficult root cause has been discovered;
- a bug has been fixed;
- the developer has confirmed a proposed fix worked;
- an important architecture decision was made;
- a hypothesis was disproved;
- an infrastructure dependency was discovered;
- a significant implementation milestone was reached.

## Why `memory-save` belongs in the current chat

The current Cursor conversation contains context that may disappear or become expensive to reconstruct later.

For example:

```text
Initial hypothesis:
ORM connection pool exhaustion

Investigation:
queries fail on first DB operation
credential lookup succeeds
database connection count near zero

New hypothesis:
network connectivity

Fix:
missing firewall ingress rule added

Developer:
"That fixed it."
```

The final confirmation materially changes the memory:

```text
Before confirmation:
"Missing firewall ingress may be the cause."
confidence = medium

After confirmation:
"Missing firewall ingress caused the connectivity failure."
confidence = high / confirmed
```

Therefore Agent Memory should capture important outcomes while the context is still available.

---

# Incremental Saving

`memory-save` should not mean:

> Save the entire conversation.

Instead it should create one or more **memory checkpoints**.

A long engineering session may use `memory-save` multiple times.

Example:

```text
09:45
/memory-save

Saved:
- database incident findings

11:30
/memory-save

Saved:
- background job concurrency decision

14:20
/memory-save

Saved:
- third-party API integration fix
```

This reduces reliance on one final huge summarisation pass.

It also protects useful context if:

- Cursor crashes;
- the conversation becomes too large;
- the model is changed;
- the developer opens a new conversation;
- work continues the next day.

---

# `memory-save` Flow

```text
Current Cursor conversation
          ↓
Frontier model identifies useful knowledge
          ↓
MemoryCandidateBundle
          ↓
submit_memory_candidates()
          ↓
Pydantic validation
          ↓
importance dimension validation
          ↓
deterministic importance calculation
          ↓
ULID creation
          ↓
local embedding generation
          ↓
related-memory retrieval
          ↓
duplicate / conflict checks
          ↓
safe storage or review routing
          ↓
checkpoint result returned to Cursor
```

---

# Memory Candidate Bundle

The frontier model should submit a coherent group of candidates rather than one unrelated database write at a time.

Conceptual schema:

```python
class MemoryCandidateBundle(BaseModel):
    project_id: str
    session_id: str | None

    session_summary: str | None

    candidates: list[MemoryCandidate]

    working_state_update: WorkingStateCandidate | None

    submitted_by: str  # MCP client name; "manual" marks developer-explicit memory

    submitted_at: datetime
```

A candidate bundle may contain:

- zero or more Episodes;
- Semantic candidates;
- Lesson candidates;
- a Working State update;
- ignored items where appropriate.

---

# `memory-save` Processing Result

Agent Memory should return a structured result.

Example:

```text
Agent Memory checkpoint saved

Created:
- Episode: Production DB connectivity failure

Supported:
- Semantic: architecture.database / postgres.application_ingress

Queued for review:
- Semantic correction: database endpoint behaviour

Updated:
- Working State

Ignored:
- 2 low-value duplicate candidates
```

Conceptually:

```python
class MemoryProcessingResult(BaseModel):
    accepted: list[str]
    revised: list[str]
    linked: list[str]
    ignored: list[str]
    conflicts: list[str]
    rejected: list[str]
```

This gives the Cursor agent feedback and makes memory operations inspectable.

---

# `/memory-status`

## Purpose

`/memory-status` answers:

> What does Agent Memory currently think is going on?

It should retrieve a compact summary of:

- current Working State;
- recent saved Episodes;
- unresolved issues;
- pending memory review;
- current project handoff;
- important relevant Semantic memory;
- active Lessons relevant to current work.

Example output:

```text
Current focus:
Production database connectivity

Known:
- connection timeout occurs before any successful DB query
- firewall ingress fix restored production access

Open:
- verify equivalent staging rule

Recent memory:
- epi_...
- sem_...

Pending review:
- 1 semantic consolidation candidate

Next actions:
1. verify staging
2. document SG dependency
```

`memory-status` should be safe and read-only.

---

# `/memory-close`

## Purpose

`/memory-close` closes an engineering work period using **already saved structured memory**.

It should not primarily summarise the old Cursor conversation.

It answers:

> Given what Agent Memory has saved from this work period, what durable memory should change, what remains open, and what should the next session know?

---

# Important Design Invariant

`memory-close` must **not depend on access to the original coding conversation**.

This is intentional.

A successful Agent Memory system should support:

```text
Old coding chat
     ↓
 /memory-save
     ↓
 structured memory
     ↓
 old chat ends

NEW CHAT
     ↓
 /memory-close
     ↓
 consolidation + handoff
```

If `memory-close` requires the old raw conversation, Agent Memory has failed to provide meaningful persistence.

---

# Fresh-Chat `memory-close`

The preferred workflow is:

```text
Large coding conversation
         ↓
one or more /memory-save checkpoints
         ↓
coding work finishes
         ↓
start a fresh Cursor chat
         ↓
/memory-close
         ↓
retrieve curated close context
         ↓
frontier model performs consolidation
         ↓
Agent Memory validates and persists
         ↓
handoff created
         ↓
Obsidian synced
```

This avoids using a high-context, heavily consumed coding conversation for another expensive reasoning pass.

It also allows the developer to choose a cheaper but still competent model specifically for session closing.

---

# `get_close_context()`

The fresh `memory-close` conversation should begin by retrieving a curated context package.

Conceptually:

```text
get_close_context(project_id)
```

may return:

- current Working State;
- Episodes saved since the previous close;
- pending Episodes;
- candidate related Semantic memories;
- recent Semantic revisions;
- relevant Lessons;
- unresolved conflicts;
- previous handoff.

The goal is to give the closing model **high-signal structured context**, not raw conversation history.

---

# `memory-close` Stages

## Stage 1 — Retrieve

Deterministic/local:

```text
Working State
recent Episodes
pending consolidation
related Semantic memory
relevant Lessons
previous handoff
```

## Stage 2 — Consolidate

Frontier reasoning:

For each relevant memory cluster, determine whether to:

- leave Semantic memory unchanged;
- add supporting evidence;
- expand Semantic memory;
- correct Semantic memory;
- split one memory into multiple memories;
- dispute an existing memory;
- supersede obsolete knowledge;
- create or revise a Lesson.

The model should return structured proposals rather than direct writes.

## Stage 3 — Validate and Persist

Agent Memory:

- validates proposal schemas;
- checks referenced memory IDs;
- verifies revision numbers;
- checks permitted transitions;
- calculates deterministic importance;
- creates Memory Links;
- writes the transaction;
- marks Episodes as processed where appropriate.

## Stage 4 — Update Working State

After consolidation:

- remove resolved work;
- preserve unresolved blockers;
- keep current hypotheses only where still relevant;
- set next actions;
- set current focus for the next work session.

## Stage 5 — Generate Handoff

Create a concise next-session handoff.

Suggested structure:

```markdown
# Current Handoff

## What changed

## Confirmed decisions

## Important knowledge

## Open issues

## Current blockers

## Next actions

## Relevant memories

## Relevant files / services
```

The handoff should be much smaller than the original coding conversation.

## Stage 6 — Obsidian Sync

Completely local/deterministic.

Possible outputs:

```text
Projects/<Project Name>/Current State.md
Projects/<Project Name>/Semantic.md
Projects/<Project Name>/Lessons.md
Sessions/2026-09-28.md
Handoffs/<Project Name>.md
```

Obsidian remains a human-readable projection.

SQLite remains canonical memory.

---

# Why `memory-close` Can Use a Cheaper Model

`memory-save` benefits heavily from the strongest model because it has access to messy live engineering context.

`memory-close` receives:

- already summarised Episodes;
- structured Working State;
- existing Semantic memories;
- explicit Memory Links;
- known conflicts.

Therefore its reasoning task is much more constrained.

This makes it reasonable to evaluate cheaper frontier models for closing.

However model choice should be benchmarked rather than assumed.

---

# Consolidation Evaluation

Create a fixed test set containing:

- Episodes;
- existing Semantic memories;
- Semantic revisions;
- conflicts;
- Lesson opportunities.

Evaluate candidate closing models on:

```text
fact preservation
correct conflict handling
appropriate revision choice
absence of invented facts
useful Lesson generation
scope correctness
provenance preservation
```

A cheaper model may become the default `memory-close` model if it performs reliably.

---

# Frontier Reasoning Boundaries

Even during `memory-close`, the model should not directly modify the database.

The interaction remains:

```text
Cursor frontier model
        ↓
prepare / reason
        ↓
MCP tool call
        ↓
Agent Memory validates
        ↓
persist or return conflict
        ↓
Cursor may reason again
        ↓
next MCP call
```

This allows multi-step orchestration without giving the model unrestricted persistence access.

---

# High-Risk Memory Changes

The following should initially require stronger reasoning and potentially explicit developer review:

- correcting confirmed Semantic memory;
- marking knowledge obsolete;
- resolving contradictory evidence;
- creating project-wide Lessons;
- creating critical Lessons;
- splitting long-standing Semantic memory;
- destructive deletion.

Low-risk operations may happen automatically:

- appending an Episode;
- adding supporting evidence;
- updating Working State;
- adding embeddings;
- adding tags/entities;
- syncing Obsidian.

---

# MCP Tool Design

The user-facing workflows should be composed from smaller MCP primitives.

Possible tools:

```text
submit_memory_candidates
get_memory_status
get_close_context
prepare_consolidation
apply_semantic_revision
create_lesson
update_working_state
get_pending_reviews
mark_episode_processed
sync_obsidian
inspect_memory
inspect_memory_history
```

Do not create one unrestricted tool such as:

```text
do_everything_and_modify_memory()
```

Smaller primitives:

- make behaviour auditable;
- reduce accidental writes;
- simplify testing;
- let Cursor reason between steps;
- make future permissions possible.

---

# Suggested Cursor Skill Layer

Possible project/global skills:

```text
/memory-save
/memory-status
/memory-close
```

These Skills should contain the workflow instructions required for Cursor to call the correct MCP tools.

The Skills should not duplicate the entire Agent Memory architecture.

Instead they should tell the agent:

- when to invoke Agent Memory;
- what information to extract;
- which MCP tools to call;
- how to handle returned conflicts;
- what to show the developer.

---

# AGENTS.md Contract

The normal repository `AGENTS.md` should contain only the permanent Agent Memory behaviour contract.

Suggested principles:

```text
When Agent Memory tools are available:

- retrieve relevant project memory before substantial work where useful;
- use current repository state as more authoritative than memory;
- save meaningful engineering outcomes at important milestones;
- do not store routine conversation or trivial edits;
- distinguish hypotheses from confirmed facts;
- treat developer confirmation that a fix worked as strong evidence;
- use Agent Memory's conflict/revision process rather than silently overwriting memory;
- preserve unresolved next actions in Working State.

If Agent Memory is unavailable, continue using normal repository instructions.
```

The detailed workflows belong in Skills.

---

# Developer Confirmation as Evidence

Developer confirmation should be explicitly recognised as an important evidence signal.

Example:

```text
Agent:
"I changed the database firewall ingress rule."

Developer:
"Yep, production works now."
```

This can justify changing:

```text
hypothesis
↓
confirmed outcome
```

The system should record the provenance as:

```text
source = developer_explicit
```

or link the confirmation to the Episode.

Developer confirmation should not automatically prove every causal interpretation, but it should strongly increase confidence in the observed outcome.

---

# Checkpoint Concept

Each `memory-save` operation should create a checkpoint identifier.

Example:

```text
chk_01K...
```

A checkpoint groups memories created from the same save event.

Possible fields:

```text
checkpoint_id
project_id
session_id
created_at
created_memory_ids[]
working_state_updated
```

Benefits:

- easier debugging;
- easier rollback/review;
- easy session grouping;
- useful Obsidian history;
- ability to see exactly what a `/memory-save` created.

This may become a formal schema later.

---

# Recommended Daily Workflow

A typical work period should look like:

```text
Start coding chat
      ↓
Agent Memory recalls relevant context
      ↓
work
      ↓
important finding
      ↓
/memory-save
      ↓
continue work
      ↓
another meaningful milestone
      ↓
/memory-save
      ↓
work finished
      ↓
end old chat
      ↓
start fresh chat
      ↓
/memory-close
      ↓
consolidate
      ↓
update Working State
      ↓
create handoff
      ↓
sync Obsidian
```

The next work session then begins from:

```text
handoff
+
Working State
+
relevant Semantic memory
+
applicable Lessons
```

rather than the entire previous conversation.

---

# Failure Modes to Avoid

## 1. Saving everything

Bad:

```text
every few messages
→ memory write
```

This creates noise.

Prefer memory-worthy boundaries.

## 2. Waiting until the very end of a huge session

Important findings may already have disappeared from context or become harder to distinguish.

Use incremental checkpoints.

## 3. Letting `memory-close` depend on raw chat history

This defeats persistent memory.

`memory-close` should operate from Agent Memory's structured state.

## 4. Letting the local model rewrite long-term knowledge autonomously too early

Start local models with low-risk enrichment.

Benchmark before increasing authority.

## 5. Giving the frontier model direct SQLite access

All writes should pass through Agent Memory validation and business rules.

## 6. Treating every fix as a Lesson

Many fixes are Episodes or Semantic facts only.

A Lesson should change useful future behaviour.

---

# Initial Implementation Strategy

## Phase 1

Implement:

```text
submit_memory_candidates
get_memory_status
```

Support manual `/memory-save`.

## Phase 2

Implement:

```text
get_close_context
apply_semantic_revision
create_lesson
update_working_state
```

Support fresh-chat `/memory-close`.

## Phase 3

Add:

```text
/memory-status
```

and structured handoff generation.

## Phase 4

Add:

- automatic suggestions to run `memory-save`;
- smarter local enrichment;
- candidate conflict detection;
- checkpoint history;
- Obsidian sync.

## Phase 5

Benchmark local models and cheaper frontier models for consolidation.

Allow increasingly automatic low-risk memory processing only when evaluation demonstrates acceptable reliability.

---

# V1 Success Criterion

The orchestration design is successful when the following scenario works reliably:

```text
1. A developer performs substantial work in Cursor.
2. The developer runs /memory-save after an important finding.
3. Cursor's active frontier model extracts meaningful memory candidates.
4. Agent Memory validates, enriches, and stores those memories locally.
5. The original Cursor conversation can be closed.
6. A new conversation runs /memory-close.
7. The new model receives only structured Agent Memory context.
8. It correctly consolidates long-term memory.
9. Agent Memory validates and stores revisions and Lessons.
10. A concise next-session handoff is generated.
11. The next coding session can continue without the developer re-explaining the previous work.
```

The system should achieve this without requiring direct frontier-model API keys.
