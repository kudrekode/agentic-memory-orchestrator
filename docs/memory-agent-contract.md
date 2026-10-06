# Memory Agent Contract

This is the portable instruction contract for any frontier-capable agent that
uses Agent Memory. In a future monorepo, root agent skills should reference this file
rather than duplicate its rules.

## Authority boundary

The agent may propose memory. Agent Memory decides whether it is valid, how it is
stored, and whether it changes existing knowledge.

The agent must not:

- write SQLite or call raw database tools;
- construct stored `Episode`, `SemanticMemory`, `Lesson`, or `MemoryLink`
  records directly;
- generate IDs, timestamps, revision numbers, or final importance categories;
- silently replace semantic knowledge;
- promote a hypothesis to a confirmed fact.

## When to use Agent Memory

Use memory capture after meaningful engineering work, such as:

- an incident, investigation, deployment problem, or significant experiment;
- an architectural decision or non-obvious system constraint;
- a reusable debugging, deployment, workflow, or project-convention lesson;
- an active-work update needed to resume safely in a later session.

Do not capture routine conversation, raw transcripts, temporary command output,
trivial edits, or facts readily rediscovered from current code without useful
context.

## Required interaction flow

```text
1. Read the current Working State and relevant recalled context.
2. Decide whether there is a meaningful candidate.
3. Produce a structured candidate bundle.
4. Submit it through the constrained Agent Memory MCP tool.
5. Read the structured result.
6. Continue with the accepted/rejected/conflict outcome; do not bypass it.
```

The MCP tool name and transport may change, but this authority boundary does
not.

## Candidate bundle

The agent submits zero or more `MemoryCandidate` objects and one optional
working-state update. The outer bundle belongs to one project and one
session/checkpoint. Omit `project_id` to use the server's configured default
project (`AGENT_MEMORY_PROJECT_ID`).

```json
{
  "project_id": "optional; defaults to AGENT_MEMORY_PROJECT_ID",
  "session_summary": "Optional short summary of this checkpoint.",
  "candidates": [
    {
      "proposed_type": "episode",
      "content": {},
      "rationale": "Why this is worth retaining.",
      "confidence": "high",
      "importance_dimensions": {
        "future_usefulness": 0,
        "cost_of_rediscovery": 0,
        "blast_radius": 0,
        "decision_significance": 0,
        "recurrence_value": 0
      },
      "related_memory_queries": []
    }
  ]
}
```

Each importance dimension is an integer from `0` through `3`. The agent
proposes these dimensions; Agent Memory calculates the final category.

## Candidate types

### Episode — what happened?

Use for one meaningful engineering event.

```json
{
  "proposed_type": "episode",
  "content": {
    "title": "Database connectivity incident",
    "summary": "Application services could not reach the database until the firewall ingress rule was corrected.",
    "outcome": "resolved",
    "details": ["A connection timeout occurred on the first query."],
    "scope": {"environment": "production", "service": "orders-api"},
    "tags": ["incident", "networking"]
  }
}
```

The summary must describe one event with enough context. Use `unresolved` or
`partially_resolved` when the outcome is not confirmed.

### Semantic — what is believed to be true?

Use for reusable project knowledge, not a timeline of what happened.

```json
{
  "proposed_type": "semantic",
  "content": {
    "namespace": "architecture.database",
    "key": "postgres.application_ingress",
    "statement": "Production services require database firewall ingress on port 5432.",
    "scope": {"environment": "production", "service": "orders-api"}
  }
}
```

Use a namespace and stable key. Include scope for environment-, service-, repo-,
or component-specific knowledge. If relevant knowledge may already exist, use
`related_memory_queries`; never claim it can be overwritten.

### Lesson — how should an agent behave?

Use a WHEN / DO / BECAUSE structure.

```json
{
  "proposed_type": "lesson",
  "content": {
    "title": "Check firewall ingress before application code",
    "triggers": ["database timeout", "connection timeout on first query"],
    "instruction": "Inspect database and service firewall rules before changing application code.",
    "reason": "This is a recurring connectivity failure mode.",
    "category": "debugging",
    "priority": "high",
    "scope": {"service": "orders-api"}
  }
}
```

A factual statement is not a lesson. A lesson must tell a future agent when to
act, what to do, and why.

`instruction` must start with one of these verbs:

```text
add, check, confirm, create, disable, enable, inspect, run, test, use,
verify, update, review, avoid, prefer, ensure, set, remove, restart,
deploy, investigate, compare, open, read, write, fix
```

The check is case-insensitive and applies to the first word. "Call" and "For"
are rejected. The same list applies to each `next_actions` entry on a
working-state update.

### Working-state update — what is active now?

Use for current work only.

```json
{
  "proposed_type": "working_state_update",
  "content": {
    "focus": "Database connectivity investigation",
    "status": "investigating",
    "known": ["A connection timeout occurs on the first database query."],
    "hypotheses": ["The database firewall lacks application ingress."],
    "next_actions": ["Inspect the database firewall rules."]
  }
}
```

Keep known facts and hypotheses separate. Completed work belongs in an Episode.

### Ignore

Use `ignore` when an item should not be retained. It needs rationale but creates
no durable record.

## Consolidation contract

During consolidation, the agent receives pending Episodes plus related semantic
records, revisions, links, and lessons. It may propose:

```text
unchanged | support | expand | correct | split | dispute | supersede | lesson
```

It must provide the evidence and rationale for the proposal. Agent Memory verifies
references, authority, allowed transitions, and revision numbers, then either
persists the decision, marks it for review, or rejects it.

## Monorepo use

When Agent Memory is vendored into a larger repository:

```text
repo/
├── frontend/
├── backend/
├── agent-memory/
│   └── docs/memory-agent-contract.md
└── .cursor/skills/
    └── memory-capture/SKILL.md
```

The root `memory-capture` skill should remain short and direct agents to read
`agent-memory/docs/memory-agent-contract.md` before proposing or consolidating memory.
This document remains the single canonical contract.
