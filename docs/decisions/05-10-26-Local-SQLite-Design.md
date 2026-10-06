# 05-10-26 — Local SQLite persistence design

## Decision

Agent Memory v1 uses one SQLite database file per developer and environment. The
database is local and is not shared, placed in Git, or synchronized through a
file-sync service.

The Python persistence layer is the only interface to the database. It stores
validated Pydantic records and enforces project boundaries, transaction
boundaries, and database-dependent integrity checks.

## Database location

The application receives a database path explicitly. Recommended local paths:

```text
data/dev/memory.db
data/live/memory.db
```

Tests use a temporary SQLite database; no test writes to either local path.

## Schema

Schema version 1 contains:

```text
schema_migrations
projects
working_states
episodes
semantic_memories
semantic_revisions
lessons
memory_links
```

`working_states.project_id` is the primary key, enforcing one current mutable
state per project. `semantic_memories` has a unique `(project_id, namespace,
key)` constraint. Semantic revisions are unique per `(semantic_memory_id,
revision_number)`.

Episodes, semantic memories, and lessons retain their list and scope fields as
JSON text. Queryable identity, status, timestamps, source, confidence, and
importance fields use explicit SQLite columns.

## Referential integrity

SQLite foreign keys enforce:

- every stored memory belongs to an existing Project;
- each Working State belongs to an existing Project;
- every Semantic Revision belongs to an existing Semantic memory.

Memory links are polymorphic, so SQLite cannot safely represent both endpoints
as foreign keys. The Python store checks that each referenced endpoint exists,
has the declared type, belongs to the same project, and is not a self-link.

## Transaction boundary

Each repository write uses a transaction. `save_records()` persists a group of
independent Episode, Semantic, and Lesson records atomically. Higher-level
candidate processing will later combine record creation, links, revisions,
episode status changes, and Working State changes in one transaction.

## Not included in v1

- multi-user sharing or synchronization;
- embeddings and vector indexes;
- direct SQL MCP tools;
- deduplication/conflict resolution policy;
- semantic-revision transition policy;
- migrations after schema version 1.

These are application-level concerns or future persistence migrations, not
reasons to weaken the initial local schema.
