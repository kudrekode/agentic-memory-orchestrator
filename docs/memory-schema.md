# Agent Memory — Memory Schema Design

## Purpose

This document defines the **v1 memory contracts** for Agent Memory before any SQLite persistence layer is implemented.

The goal is to answer three questions:

1. What kinds of memory can exist?
2. What fields must each memory contain?
3. What validation rules determine whether a memory is safe and useful enough to store?

The intended implementation order is:

```text
Pydantic schemas
      ↓
Memory classification
      ↓
Business validation
      ↓
Persistence service
      ↓
SQLite
```

SQLite is the persistence layer. It should not decide what valid memory is.

Pydantic models define the structural contract.

Business-validation logic determines whether structurally valid memory is actually worth storing.

---

# Design Principles

## 1. Repository state is authoritative

Memory must never silently override current repository state.

If remembered implementation details conflict with current code, infrastructure-as-code, or explicit developer correction, the current authoritative source wins.

---

## 2. Memory must preserve provenance

Long-term knowledge should be explainable.

Agent Memory should be able to answer:

1. What do we currently believe?
2. Why do we believe it?
3. What did we believe previously?

Semantic changes therefore use revisions instead of destructive overwrites.

---

## 3. Memory must be selective

Agent Memory should not store:

- routine conversation;
- every terminal command;
- raw chain-of-thought;
- every code edit;
- transient wording;
- facts already trivially available from the current codebase unless they are important context.

The system should prefer memories that are likely to reduce future re-explanation, prevent repeated mistakes, or preserve important engineering context.

---

## 4. ULIDs are the canonical identifier format

All first-class entities should use ULIDs with readable prefixes.

Examples:

```text
prj_01K...
epi_01K...
sem_01K...
rev_01K...
les_01K...
lnk_01K...
```

Reasons:

- sortable by creation time;
- globally unique;
- safer for future multi-developer or merged stores;
- easier to recognise in logs and Obsidian;
- avoids dependence on SQLite auto-increment IDs.

---

# Memory Types

Agent Memory v1 contains four memory concepts:

```text
Working State  → What are we doing now?
Episode        → What happened?
Semantic       → What do we believe is true?
Lesson         → How should the agent behave?
```

Consolidation is **not** a memory type.

Consolidation is a process that evaluates episodes and other evidence and may:

- create semantic memory;
- revise semantic memory;
- create lessons;
- mark an episode as processed.

---

# Shared Enums

These values should be represented as enums in Pydantic rather than unrestricted strings where practical.

## Confidence

Confidence describes:

> How strongly is this memory supported?

Use semantic categories rather than arbitrary model-generated floating-point values.

```text
low
medium
high
confirmed
```

Suggested internal numeric mapping:

```text
low        = 0.35
medium     = 0.60
high       = 0.85
confirmed  = 1.00
```

The model selects a category.

The application converts that category into a numeric value only where scoring requires it.

---

## Importance

Importance describes:

> How costly would it be if this memory were unavailable in a future relevant session?

Use:

```text
low
normal
high
critical
```

Suggested internal mapping:

```text
low       = 0.25
normal    = 0.50
high      = 0.80
critical  = 1.00
```

Importance is **not** the same as confidence.

Example:

```text
"The deployment was briefly slow at 09:14."

confidence = confirmed
importance = low
```

versus:

```text
"The outage may be caused by a security-group rule."

confidence = medium
importance = high
```

---

# Calculating Importance

Importance should not be determined by a model simply inventing a number.

Agent Memory should calculate or constrain importance using an explicit rubric.

## Importance dimensions

A candidate memory is evaluated across the following dimensions.

### 1. Future usefulness

Will this materially help a future engineering session?

```text
0 = unlikely to matter again
1 = occasionally useful
2 = likely useful
3 = repeatedly useful
```

### 2. Cost of rediscovery

How expensive would it be to rediscover this information?

```text
0 = trivial to rediscover
1 = a few minutes
2 = substantial debugging/research
3 = expensive incident investigation or specialist knowledge
```

### 3. Scope / blast radius

How much of the system can this affect?

```text
0 = tiny/local
1 = one component
2 = multiple services/workflows
3 = production/system-wide
```

### 4. Decision significance

Does this represent a meaningful architectural, operational, or debugging decision?

```text
0 = incidental
1 = useful implementation detail
2 = important decision
3 = architectural / operational invariant
```

### 5. Recurrence value

Would remembering this prevent repeated mistakes or duplicated work?

```text
0 = one-off
1 = possibly reusable
2 = likely to recur
3 = recurring pattern / known failure mode
```

---

## Deterministic importance score

The service can calculate:

```text
raw_score =
    future_usefulness
  + cost_of_rediscovery
  + blast_radius
  + decision_significance
  + recurrence_value
```

Maximum score: `15`

Suggested mapping:

```text
0–3   → low
4–7   → normal
8–11  → high
12–15 → critical
```

This is deliberately simple.

The model may provide the five dimension assessments, but **the application calculates the final importance category**.

This prevents an LLM from inventing unsupported precision such as `importance = 0.873`.

---

## Importance guardrails

Certain cases may impose minimum importance.

Examples:

```text
Confirmed production outage root cause
→ minimum HIGH

Security / data-loss issue
→ minimum HIGH

Explicit architectural invariant
→ minimum HIGH

Developer explicitly says "remember this"
→ minimum NORMAL

Reusable lesson from a costly incident
→ minimum HIGH
```

Likewise:

```text
Temporary command output
→ maximum LOW

Pure conversational context
→ reject

Information trivially discoverable from current code with no contextual value
→ usually LOW or reject
```

---

# Common Types

## MemoryScope

Used to specify where a memory applies.

```python
class MemoryScope(BaseModel):
    environment: str | None = None
    service: str | None = None
    repo: str | None = None
    component: str | None = None
```

Scope values are optional because not every memory is environment- or service-specific.

Examples:

```json
{
  "environment": "production",
  "service": "orders-api"
}
```

or:

```json
{
  "component": "background-jobs"
}
```

---

## MemorySource

Recommended values:

```text
developer_explicit
agent_inferred
repository
documentation
episode
consolidation
external_tool
```

Source describes **where the assertion came from**, not whether it is correct.

---

# Project

## Purpose

Projects provide isolation between independent engineering contexts.

Version 1 may only use one project, but project identity should exist from the beginning.

## Schema

```python
class Project(BaseModel):
    id: str
    name: str
    description: str | None = None
    repo_path: str | None = None
    obsidian_path: str | None = None
    status: Literal["active", "archived"] = "active"
    created_at: datetime
    updated_at: datetime
```

## Validation

- `id` must use `prj_` + ULID.
- `name` cannot be empty.
- paths are metadata only and should not imply that the resource currently exists.
- stack, architecture, database choice, etc. do not belong in Project; those belong in semantic memory.

---

# Working State

## Purpose

Working state describes:

> What is currently happening?

It is mutable and temporary.

A project should generally have **one active working-state record**.

## Schema

```python
class WorkingState(BaseModel):
    project_id: str

    focus: str | None = None

    status: Literal[
        "idle",
        "planning",
        "implementing",
        "investigating",
        "blocked",
        "testing",
        "deploying"
    ]

    known: list[str] = []
    unknown: list[str] = []
    hypotheses: list[str] = []
    blockers: list[str] = []
    next_actions: list[str] = []

    active_files: list[str] = []
    active_services: list[str] = []

    updated_at: datetime
```

## Validation

- working state should describe active work only;
- hypotheses must not be promoted to facts merely because they appear in `known`;
- `next_actions` should contain actionable steps;
- stale working state can be replaced rather than versioned on every update;
- meaningful completed work should become one or more Episodes.

---

# Episode

## Purpose

Episodes answer:

> What happened?

An episode represents one meaningful engineering event.

Examples:

- a production incident;
- a debugging investigation;
- a deployment failure;
- a significant configuration change;
- an experiment that disproved an assumption;
- a completed implementation session with lasting relevance.

Episodes should be summarised but retain more detail than semantic memory.

## Schema

```python
class Episode(BaseModel):
    id: str
    project_id: str

    title: str
    summary: str
    details: list[str] = []

    outcome: Literal[
        "resolved",
        "unresolved",
        "partially_resolved",
        "informational"
    ]

    entities: list[str] = []
    tags: list[str] = []

    scope: MemoryScope = MemoryScope()
    services: list[str] = []

    source: MemorySource

    confidence: ConfidenceLevel

    importance_dimensions: ImportanceDimensions
    importance: ImportanceLevel

    occurred_at: datetime
    created_at: datetime

    consolidation_status: Literal[
        "pending",
        "processed",
        "ignored"
    ] = "pending"
```

## Validation

An Episode should normally:

- describe a meaningful event;
- include enough context to understand what occurred;
- avoid raw transcript content;
- avoid storing routine chatter;
- distinguish confirmed outcome from hypothesis;
- represent one coherent event rather than a whole week of unrelated work.

`importance` should be calculated from `importance_dimensions`; the model should not directly choose an arbitrary numeric value.

---

# ImportanceDimensions

```python
class ImportanceDimensions(BaseModel):
    future_usefulness: int = Field(ge=0, le=3)
    cost_of_rediscovery: int = Field(ge=0, le=3)
    blast_radius: int = Field(ge=0, le=3)
    decision_significance: int = Field(ge=0, le=3)
    recurrence_value: int = Field(ge=0, le=3)
```

Application code calculates the final importance category.

---

# Semantic Memory

## Purpose

Semantic memory answers:

> What do we currently believe to be true?

Semantic memory stores durable project knowledge.

Examples:

- infrastructure relationships;
- architectural facts;
- system invariants;
- project conventions;
- integration behaviour;
- non-obvious implementation constraints.

## Schema

```python
class SemanticMemory(BaseModel):
    id: str
    project_id: str

    namespace: str
    key: str

    statement: str

    scope: MemoryScope = MemoryScope()

    source: MemorySource

    status: Literal[
        "active",
        "superseded",
        "disputed",
        "obsolete"
    ] = "active"

    confidence: ConfidenceLevel

    importance_dimensions: ImportanceDimensions
    importance: ImportanceLevel

    current_revision: int = 1

    created_at: datetime
    updated_at: datetime
```

## Namespace examples

```text
architecture.database
architecture.queue
integration.payments
convention.git
deployment.production
workflow.release
```

Example identity:

```text
architecture.database : postgres.application_ingress
```

## Validation

Semantic memory must:

- represent reusable knowledge, not merely an event;
- have a clear namespace and key;
- avoid mixing multiple unrelated facts;
- include scope where the fact is environment/service/component-specific;
- not silently replace an existing conflicting semantic memory;
- preserve revision history when meaning changes.

---

# Semantic Revision

## Purpose

Semantic revisions preserve how long-term knowledge changes.

Semantic memory should not be destructively overwritten when its meaning changes.

## Schema

```python
class SemanticRevision(BaseModel):
    id: str
    semantic_memory_id: str

    revision_number: int

    previous_statement: str | None
    new_statement: str

    change_type: Literal[
        "created",
        "expanded",
        "corrected",
        "narrowed",
        "split",
        "superseded",
        "marked_obsolete"
    ]

    reason: str

    confidence: ConfidenceLevel

    created_by: Literal[
        "developer",
        "agent",
        "consolidation",
        "system"
    ]

    created_at: datetime
```

## Validation

- revision number must increase monotonically;
- revisions must never silently remove distinct useful information;
- corrections should explain why the previous statement changed;
- evidence should be linked using MemoryLink records;
- disputed knowledge should not automatically become corrected without sufficient authority.

---

# Lesson

## Purpose

Lessons answer:

> How should the agent behave in a similar future situation?

A Lesson is actionable behaviour derived from evidence or explicit developer instruction.

A useful lesson follows:

```text
WHEN
DO
BECAUSE
```

## Schema

```python
class Lesson(BaseModel):
    id: str
    project_id: str

    title: str

    triggers: list[str]
    instruction: str
    reason: str

    category: Literal[
        "debugging",
        "architecture",
        "deployment",
        "workflow",
        "tooling",
        "code_quality",
        "project_convention",
        "other"
    ]

    scope: MemoryScope = MemoryScope()

    source: MemorySource

    priority: Literal[
        "low",
        "normal",
        "high",
        "critical"
    ]

    confidence: ConfidenceLevel

    status: Literal[
        "active",
        "superseded",
        "disabled"
    ] = "active"

    created_at: datetime
    updated_at: datetime
```

## Validation

A Lesson must:

- be actionable;
- state when it applies;
- explain why the instruction exists;
- not simply repeat a semantic fact;
- be based on explicit developer instruction or meaningful supporting evidence;
- not become globally applicable if it is actually project- or service-specific.

---

# Memory Link

## Purpose

Memory links preserve provenance and relationships between memory objects.

## Schema

```python
class MemoryLink(BaseModel):
    id: str

    source_type: Literal[
        "episode",
        "semantic",
        "semantic_revision",
        "lesson"
    ]
    source_id: str

    target_type: Literal[
        "episode",
        "semantic",
        "semantic_revision",
        "lesson"
    ]
    target_id: str

    relationship: Literal[
        "supports",
        "contradicts",
        "updates",
        "derived_from",
        "generated",
        "supersedes",
        "related_to"
    ]

    created_at: datetime
```

## Validation

Because the link is polymorphic, SQLite foreign keys will not fully enforce correctness in v1.

The Python service must verify:

- source exists;
- target exists;
- source and target types match their IDs;
- self-links are rejected unless explicitly allowed;
- relationship is valid for the source/target pair.

---

# Memory Candidate

Agents should not write directly to stored-memory schemas.

First they should produce a candidate.

## Purpose

The candidate object represents:

> The agent believes this information may deserve memory.

## Schema

```python
class MemoryCandidate(BaseModel):
    proposed_type: Literal[
        "episode",
        "semantic",
        "lesson",
        "working_state_update",
        "ignore"
    ]

    content: dict

    rationale: str

    confidence: ConfidenceLevel

    importance_dimensions: ImportanceDimensions | None = None

    related_memory_queries: list[str] = []
```

The service then:

```text
Candidate
    ↓
Pydantic validation
    ↓
Business validation
    ↓
Existing-memory lookup
    ↓
Deduplication / conflict detection
    ↓
Persist / revise / reject / request review
```

---

# Classification Architecture

## Key principle

The model can **propose** where memory belongs.

The memory service owns the final decision.

Do not give any LLM unrestricted SQL access or permission to directly overwrite long-term memory.

---

# Frontier vs Local Models

Memory quality is sufficiently important that the initial system should not require a small local model to make every high-stakes memory decision.

A hybrid approach is recommended.

## Tier 1 — Frontier model responsibilities

Initially use the strongest available coding/reasoning model for:

- identifying meaningful memories at the end of substantial sessions;
- distinguishing Episode vs Semantic vs Lesson;
- identifying contradictions;
- proposing semantic revisions;
- deciding whether an episode contains durable knowledge;
- consolidation where existing semantic meaning could change;
- generating Lessons;
- handling ambiguous or conflicting evidence.

These operations require semantic judgment and mistakes can pollute long-term memory.

---

## Tier 2 — Local model responsibilities

Local Ollama models are well suited to:

- embedding generation;
- tagging;
- entity extraction;
- obvious deduplication assistance;
- session-summary drafts;
- low-risk classification;
- grouping episodes by topic;
- proposing candidate matches;
- generating search queries;
- routine Obsidian rendering assistance.

The local model may propose consolidation changes, but initially those changes should pass through a stronger model or deterministic validation before mutating durable semantic memory.

---

## Tier 3 — Deterministic application logic

Do not ask an LLM to do tasks that normal code can enforce reliably.

Application code should own:

- ULID generation;
- schema validation;
- importance arithmetic;
- confidence mappings;
- status transitions;
- project isolation;
- uniqueness checks;
- namespace/key lookup;
- revision numbering;
- existence checks;
- relationship validation;
- duplicate exact-match detection;
- database transactions;
- permissions around destructive operations.

---

# Recommended Initial Memory Workflow

At the end of a substantial session in Cursor or another MCP client:

```text
Session
   ↓
Frontier model receives:
- session summary / relevant conversation
- current working state
- currently relevant semantic memories
- applicable lessons
   ↓
Produces MemoryCandidate[]
   ↓
Agent Memory validates candidates
   ↓
Existing-memory search
   ↓
┌─────────────────────────────────────┐
│ Episode candidate                   │ → append Episode
│ Working state candidate             │ → update WorkingState
│ Semantic candidate, no existing key │ → create Semantic + revision 1
│ Semantic candidate, same knowledge  │ → add evidence link
│ Semantic candidate, extension       │ → propose revision
│ Semantic candidate, contradiction   │ → review/dispute path
│ Lesson candidate                    │ → validate evidence → create
│ Ignore                              │ → discard
└─────────────────────────────────────┘
```

---

# Recommended Consolidation Workflow

Consolidation should initially be triggered periodically or explicitly rather than after every interaction.

```text
Pending Episodes
      ↓
Retrieve related semantic memories
      ↓
Cluster by topic
      ↓
Strong model evaluates:
- unchanged?
- support existing?
- expand?
- correct?
- split?
- dispute?
- create lesson?
      ↓
Pydantic output schema
      ↓
Deterministic validation
      ↓
Revision proposal
      ↓
Persist
      ↓
Link evidence
      ↓
Mark Episode processed
```

For early versions, consolidation may require developer approval before:

- correcting existing semantic memory;
- marking semantic memory obsolete;
- creating critical Lessons;
- resolving contradictory evidence.

As confidence in the system improves, low-risk consolidation can become automatic.

---

# Model Trust Strategy

Agent Memory should not frame the question as:

> Can a local model be trusted with memory?

Instead classify operations by **risk**.

## Low-risk operations

Can be automated locally:

- embedding;
- tagging;
- topic clustering;
- entity extraction;
- finding candidate related memories;
- formatting Obsidian output.

## Medium-risk operations

Can be locally proposed and strongly validated:

- episode extraction;
- working-state updates;
- duplicate detection;
- session summarisation.

## High-risk operations

Initially use a frontier model and/or developer approval:

- correcting semantic memory;
- deleting/superseding knowledge;
- creating broad Lessons;
- resolving contradictions;
- compressing several detailed episodes into a new durable belief.

This makes the system progressively automatable without making durability dependent on a weaker model from day one.

---

# Developer Correction Flow

The developer must be able to override memory through normal agent interaction.

Example:

```text
Developer:
"The remembered worker pool size is wrong.
It is 300. Show me what Agent Memory currently believes and propose a correction."

Agent:
Current semantic:
architecture.queue:worker_pool_size = 100

Revision history:
v1 ...

Supporting memories:
epi_...

Proposed revision:
300

Reason:
explicit developer correction
```

After confirmation:

```text
new semantic revision
      +
MemoryLink
      +
source = developer_explicit
      +
confidence = confirmed
```

Explicit developer correction should normally outrank agent inference.

---

# Development Environment

Use separate SQLite files rather than a separate codebase.

Example:

```text
data/
├── dev/
│   └── memory.db
└── live/
    └── memory.db
```

Development should default to `dev`.

This isolates:

- schema migrations;
- consolidation experiments;
- importance-scoring changes;
- retrieval experiments;
- destructive memory tests.

A separate test Obsidian vault can also be configured.

---

# Initial Implementation Order

## Phase 1 — Models

Implement Pydantic models for:

```text
Project
MemoryScope
ImportanceDimensions
WorkingState
Episode
SemanticMemory
SemanticRevision
Lesson
MemoryLink
MemoryCandidate
```

No database required yet.

---

## Phase 2 — Validation tests

Create valid and invalid examples for each model.

Test:

- invalid enums;
- missing required fields;
- malformed ULIDs;
- impossible importance dimensions;
- empty semantic keys;
- lessons without triggers;
- episodes without useful summaries;
- bad memory-link IDs.

---

## Phase 3 — Business validation

Implement functions such as:

```text
validate_episode_candidate()
validate_semantic_candidate()
validate_lesson_candidate()
calculate_importance()
```

---

## Phase 4 — SQLite persistence

Only once the contracts are stable should SQL tables be created.

---

# V1 Success Criterion

The schema system is successful when a model can propose memory from an engineering session and Agent Memory can deterministically decide whether the proposal is:

```text
valid
invalid
duplicate
supporting evidence
new semantic knowledge
semantic revision
conflict
lesson
working-state update
ignored
```

without allowing the model to directly manipulate the database.
