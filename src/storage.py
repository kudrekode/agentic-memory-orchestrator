"""Local, versioned SQLite persistence for agent memory records."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from src.models import (
    Episode,
    Lesson,
    MemoryLink,
    MemoryObjectType,
    Project,
    SemanticMemory,
    SemanticRevision,
    WorkingState,
)
from src.transformation import StoredMemory

_SCHEMA_VERSION = 1


class MemoryNotFoundError(LookupError):
    """A requested memory record does not exist in the scoped local store."""


class SQLiteMemoryStore:
    """Repository for one developer's local agent memory SQLite database."""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    @property
    def schema_version(self) -> int:
        try:
            with self._connect() as connection:
                row = connection.execute(
                    "SELECT MAX(version) AS version FROM schema_migrations"
                ).fetchone()
        except sqlite3.OperationalError:
            return 0
        return row["version"] or 0

    def migrate(self) -> None:
        """Apply the initial local schema exactly once."""

        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL
                )
                """
            )
            applied = {
                row["version"]
                for row in connection.execute("SELECT version FROM schema_migrations")
            }
            if 1 not in applied:
                connection.executescript(_INITIAL_SCHEMA)
                connection.execute(
                    "INSERT INTO schema_migrations (version, applied_at) VALUES (?, datetime('now'))",
                    (_SCHEMA_VERSION,),
                )

    def save_project(self, project: Project) -> None:
        with self._transaction() as connection:
            self._insert_project(connection, project)

    def get_project(self, project_id: str) -> Project:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM projects WHERE id = ?", (project_id,)
            ).fetchone()
        if row is None:
            raise MemoryNotFoundError(f"project not found: {project_id}")
        return Project.model_validate(dict(row))

    def list_projects(self) -> list[Project]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM projects ORDER BY created_at, id"
            ).fetchall()
        return [Project.model_validate(dict(row)) for row in rows]

    def save_episode(self, episode: Episode) -> None:
        with self._transaction() as connection:
            self._insert_episode(connection, episode)

    def get_episode(self, episode_id: str, project_id: str) -> Episode:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM episodes WHERE id = ? AND project_id = ?",
                (episode_id, project_id),
            ).fetchone()
        if row is None:
            raise MemoryNotFoundError(f"episode not found in project: {episode_id}")
        return Episode.model_validate(_decode_episode(row))

    def list_recent_episodes(self, project_id: str, limit: int = 10) -> list[Episode]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM episodes
                WHERE project_id = ?
                ORDER BY occurred_at DESC
                LIMIT ?
                """,
                (project_id, limit),
            ).fetchall()
        return [Episode.model_validate(_decode_episode(row)) for row in rows]

    def list_episodes(self, project_id: str) -> list[Episode]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM episodes
                WHERE project_id = ?
                ORDER BY occurred_at DESC, id
                """,
                (project_id,),
            ).fetchall()
        return [Episode.model_validate(_decode_episode(row)) for row in rows]

    def save_semantic_memory(self, memory: SemanticMemory) -> None:
        with self._transaction() as connection:
            try:
                self._insert_semantic_memory(connection, memory)
            except sqlite3.IntegrityError as error:
                if "semantic_memories.project_id, semantic_memories.namespace, semantic_memories.key" in str(error):
                    raise ValueError(
                        "semantic memory with this project, namespace, and key already exists"
                    ) from error
                raise

    def get_semantic_memory(self, memory_id: str, project_id: str) -> SemanticMemory:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM semantic_memories WHERE id = ? AND project_id = ?",
                (memory_id, project_id),
            ).fetchone()
        if row is None:
            raise MemoryNotFoundError(f"semantic memory not found in project: {memory_id}")
        return SemanticMemory.model_validate(_decode_semantic_memory(row))

    def get_semantic_by_key(
        self, project_id: str, namespace: str, key: str
    ) -> SemanticMemory:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM semantic_memories
                WHERE project_id = ? AND namespace = ? AND key = ?
                """,
                (project_id, namespace, key),
            ).fetchone()
        if row is None:
            raise MemoryNotFoundError(f"semantic memory not found: {namespace}:{key}")
        return SemanticMemory.model_validate(_decode_semantic_memory(row))

    def list_active_semantic_memories(self, project_id: str) -> list[SemanticMemory]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM semantic_memories
                WHERE project_id = ? AND status = 'active'
                ORDER BY namespace, key
                """,
                (project_id,),
            ).fetchall()
        return [SemanticMemory.model_validate(_decode_semantic_memory(row)) for row in rows]

    def list_semantic_memories(self, project_id: str) -> list[SemanticMemory]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM semantic_memories
                WHERE project_id = ?
                ORDER BY namespace, key, id
                """,
                (project_id,),
            ).fetchall()
        return [SemanticMemory.model_validate(_decode_semantic_memory(row)) for row in rows]

    def save_semantic_revision(self, revision: SemanticRevision) -> None:
        with self._transaction() as connection:
            self._require_entity(connection, revision.semantic_memory_id, MemoryObjectType.SEMANTIC)
            connection.execute(
                """
                INSERT INTO semantic_revisions (
                    id, semantic_memory_id, revision_number, previous_statement,
                    new_statement, change_type, reason, confidence, created_by, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    revision.id,
                    revision.semantic_memory_id,
                    revision.revision_number,
                    revision.previous_statement,
                    revision.new_statement,
                    revision.change_type.value,
                    revision.reason,
                    revision.confidence.value,
                    revision.created_by.value,
                    _timestamp(revision.created_at),
                ),
            )

    def list_semantic_revisions(self, semantic_memory_id: str) -> list[SemanticRevision]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM semantic_revisions
                WHERE semantic_memory_id = ?
                ORDER BY revision_number
                """,
                (semantic_memory_id,),
            ).fetchall()
        return [SemanticRevision.model_validate(dict(row)) for row in rows]

    def save_lesson(self, lesson: Lesson) -> None:
        with self._transaction() as connection:
            self._insert_lesson(connection, lesson)

    def get_lesson(self, lesson_id: str, project_id: str) -> Lesson:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM lessons WHERE id = ? AND project_id = ?",
                (lesson_id, project_id),
            ).fetchone()
        if row is None:
            raise MemoryNotFoundError(f"lesson not found in project: {lesson_id}")
        return Lesson.model_validate(_decode_lesson(row))

    def list_active_lessons(self, project_id: str) -> list[Lesson]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM lessons
                WHERE project_id = ? AND status = 'active'
                ORDER BY priority DESC, title
                """,
                (project_id,),
            ).fetchall()
        return [Lesson.model_validate(_decode_lesson(row)) for row in rows]

    def list_lessons(self, project_id: str) -> list[Lesson]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM lessons
                WHERE project_id = ?
                ORDER BY category, title, id
                """,
                (project_id,),
            ).fetchall()
        return [Lesson.model_validate(_decode_lesson(row)) for row in rows]

    def replace_working_state(self, state: WorkingState) -> None:
        with self._transaction() as connection:
            connection.execute(
                """
                INSERT INTO working_states (
                    project_id, focus, status, known, unknown, hypotheses, blockers,
                    next_actions, active_files, active_services, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(project_id) DO UPDATE SET
                    focus = excluded.focus,
                    status = excluded.status,
                    known = excluded.known,
                    unknown = excluded.unknown,
                    hypotheses = excluded.hypotheses,
                    blockers = excluded.blockers,
                    next_actions = excluded.next_actions,
                    active_files = excluded.active_files,
                    active_services = excluded.active_services,
                    updated_at = excluded.updated_at
                """,
                (
                    state.project_id,
                    state.focus,
                    state.status.value,
                    _json(state.known),
                    _json(state.unknown),
                    _json(state.hypotheses),
                    _json(state.blockers),
                    _json(state.next_actions),
                    _json(state.active_files),
                    _json(state.active_services),
                    _timestamp(state.updated_at),
                ),
            )

    def get_working_state(self, project_id: str) -> WorkingState:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM working_states WHERE project_id = ?", (project_id,)
            ).fetchone()
        if row is None:
            raise MemoryNotFoundError(f"working state not found for project: {project_id}")
        return WorkingState.model_validate(_decode_working_state(row))

    def save_memory_link(self, link: MemoryLink) -> None:
        with self._transaction() as connection:
            if link.source_id == link.target_id:
                raise ValueError("memory links cannot link a record to itself")
            source_project = self._entity_project_id(
                connection, link.source_id, link.source_type
            )
            target_project = self._entity_project_id(
                connection, link.target_id, link.target_type
            )
            if source_project != target_project:
                raise ValueError("memory links cannot cross project boundaries")
            connection.execute(
                """
                INSERT INTO memory_links (
                    id, source_type, source_id, target_type, target_id, relationship, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    link.id,
                    link.source_type.value,
                    link.source_id,
                    link.target_type.value,
                    link.target_id,
                    link.relationship.value,
                    _timestamp(link.created_at),
                ),
            )

    def get_memory_link(self, link_id: str) -> MemoryLink:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM memory_links WHERE id = ?", (link_id,)
            ).fetchone()
        if row is None:
            raise MemoryNotFoundError(f"memory link not found: {link_id}")
        return MemoryLink.model_validate(dict(row))

    def list_memory_links_for_project(self, project_id: str) -> list[MemoryLink]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                WITH project_entities AS (
                    SELECT id FROM episodes WHERE project_id = ?
                    UNION
                    SELECT id FROM semantic_memories WHERE project_id = ?
                    UNION
                    SELECT id FROM lessons WHERE project_id = ?
                    UNION
                    SELECT semantic_revisions.id
                    FROM semantic_revisions
                    JOIN semantic_memories
                        ON semantic_memories.id = semantic_revisions.semantic_memory_id
                    WHERE semantic_memories.project_id = ?
                )
                SELECT memory_links.*
                FROM memory_links
                WHERE source_id IN (SELECT id FROM project_entities)
                   OR target_id IN (SELECT id FROM project_entities)
                ORDER BY id
                """,
                (project_id, project_id, project_id, project_id),
            ).fetchall()
        return [MemoryLink.model_validate(dict(row)) for row in rows]

    def save_records(self, records: Sequence[StoredMemory]) -> None:
        """Persist a group of independent records in one transaction."""

        with self._transaction() as connection:
            for record in records:
                if isinstance(record, Episode):
                    self._insert_episode(connection, record)
                elif isinstance(record, SemanticMemory):
                    self._insert_semantic_memory(connection, record)
                elif isinstance(record, Lesson):
                    self._insert_lesson(connection, record)
                else:
                    raise TypeError(f"unsupported stored record: {type(record).__name__}")

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        with self._connect() as connection:
            try:
                connection.execute("BEGIN")
                yield connection
            except Exception:
                connection.rollback()
                raise
            else:
                connection.commit()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @staticmethod
    def _insert_project(connection: sqlite3.Connection, project: Project) -> None:
        connection.execute(
            """
            INSERT INTO projects (
                id, name, description, repo_path, obsidian_path, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project.id,
                project.name,
                project.description,
                project.repo_path,
                project.obsidian_path,
                project.status.value,
                _timestamp(project.created_at),
                _timestamp(project.updated_at),
            ),
        )

    @staticmethod
    def _insert_episode(connection: sqlite3.Connection, episode: Episode) -> None:
        connection.execute(
            """
            INSERT INTO episodes (
                id, project_id, title, summary, details, outcome, entities, tags, scope,
                services, source, confidence, importance_dimensions, importance, occurred_at,
                created_at, consolidation_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                episode.id,
                episode.project_id,
                episode.title,
                episode.summary,
                _json(episode.details),
                episode.outcome.value,
                _json(episode.entities),
                _json(episode.tags),
                _json(episode.scope.model_dump()),
                _json(episode.services),
                episode.source.value,
                episode.confidence.value,
                _json(episode.importance_dimensions.model_dump()),
                episode.importance.value,
                _timestamp(episode.occurred_at),
                _timestamp(episode.created_at),
                episode.consolidation_status.value,
            ),
        )

    @staticmethod
    def _insert_semantic_memory(
        connection: sqlite3.Connection, memory: SemanticMemory
    ) -> None:
        connection.execute(
            """
            INSERT INTO semantic_memories (
                id, project_id, namespace, key, statement, scope, source, status,
                confidence, importance_dimensions, importance, current_revision, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                memory.id,
                memory.project_id,
                memory.namespace,
                memory.key,
                memory.statement,
                _json(memory.scope.model_dump()),
                memory.source.value,
                memory.status.value,
                memory.confidence.value,
                _json(memory.importance_dimensions.model_dump()),
                memory.importance.value,
                memory.current_revision,
                _timestamp(memory.created_at),
                _timestamp(memory.updated_at),
            ),
        )

    @staticmethod
    def _insert_lesson(connection: sqlite3.Connection, lesson: Lesson) -> None:
        connection.execute(
            """
            INSERT INTO lessons (
                id, project_id, title, triggers, instruction, reason, category, scope,
                source, priority, confidence, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                lesson.id,
                lesson.project_id,
                lesson.title,
                _json(lesson.triggers),
                lesson.instruction,
                lesson.reason,
                lesson.category.value,
                _json(lesson.scope.model_dump()),
                lesson.source.value,
                lesson.priority.value,
                lesson.confidence.value,
                lesson.status.value,
                _timestamp(lesson.created_at),
                _timestamp(lesson.updated_at),
            ),
        )

    def _entity_project_id(
        self, connection: sqlite3.Connection, identifier: str, entity_type: MemoryObjectType
    ) -> str:
        table = {
            MemoryObjectType.EPISODE: "episodes",
            MemoryObjectType.SEMANTIC: "semantic_memories",
            MemoryObjectType.LESSON: "lessons",
        }.get(entity_type)
        if table is None:
            if entity_type is MemoryObjectType.SEMANTIC_REVISION:
                row = connection.execute(
                    """
                    SELECT memory.project_id
                    FROM semantic_revisions revision
                    JOIN semantic_memories memory ON memory.id = revision.semantic_memory_id
                    WHERE revision.id = ?
                    """,
                    (identifier,),
                ).fetchone()
            else:
                row = None
        else:
            row = connection.execute(
                f"SELECT project_id FROM {table} WHERE id = ?", (identifier,)
            ).fetchone()
        if row is None:
            raise MemoryNotFoundError(
                f"{entity_type.value} endpoint not found: {identifier}"
            )
        return row["project_id"]

    def _require_entity(
        self, connection: sqlite3.Connection, identifier: str, entity_type: MemoryObjectType
    ) -> None:
        self._entity_project_id(connection, identifier, entity_type)


def _timestamp(value: Any) -> str:
    return value.isoformat()


def _json(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), sort_keys=True)


def _decode_episode(row: sqlite3.Row) -> dict[str, Any]:
    return {
        **dict(row),
        "details": json.loads(row["details"]),
        "entities": json.loads(row["entities"]),
        "tags": json.loads(row["tags"]),
        "scope": json.loads(row["scope"]),
        "services": json.loads(row["services"]),
        "importance_dimensions": json.loads(row["importance_dimensions"]),
    }


def _decode_semantic_memory(row: sqlite3.Row) -> dict[str, Any]:
    return {
        **dict(row),
        "scope": json.loads(row["scope"]),
        "importance_dimensions": json.loads(row["importance_dimensions"]),
    }


def _decode_lesson(row: sqlite3.Row) -> dict[str, Any]:
    return {
        **dict(row),
        "triggers": json.loads(row["triggers"]),
        "scope": json.loads(row["scope"]),
    }


def _decode_working_state(row: sqlite3.Row) -> dict[str, Any]:
    values = dict(row)
    for field in (
        "known",
        "unknown",
        "hypotheses",
        "blockers",
        "next_actions",
        "active_files",
        "active_services",
    ):
        values[field] = json.loads(values[field])
    return values


_INITIAL_SCHEMA = """
CREATE TABLE projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    repo_path TEXT,
    obsidian_path TEXT,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE working_states (
    project_id TEXT PRIMARY KEY REFERENCES projects(id),
    focus TEXT,
    status TEXT NOT NULL,
    known TEXT NOT NULL,
    unknown TEXT NOT NULL,
    hypotheses TEXT NOT NULL,
    blockers TEXT NOT NULL,
    next_actions TEXT NOT NULL,
    active_files TEXT NOT NULL,
    active_services TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE episodes (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id),
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    details TEXT NOT NULL,
    outcome TEXT NOT NULL,
    entities TEXT NOT NULL,
    tags TEXT NOT NULL,
    scope TEXT NOT NULL,
    services TEXT NOT NULL,
    source TEXT NOT NULL,
    confidence TEXT NOT NULL,
    importance_dimensions TEXT NOT NULL,
    importance TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    consolidation_status TEXT NOT NULL
);
CREATE INDEX episodes_project_occurred_at ON episodes(project_id, occurred_at DESC);
CREATE INDEX episodes_project_consolidation
    ON episodes(project_id, consolidation_status);

CREATE TABLE semantic_memories (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id),
    namespace TEXT NOT NULL,
    key TEXT NOT NULL,
    statement TEXT NOT NULL,
    scope TEXT NOT NULL,
    source TEXT NOT NULL,
    status TEXT NOT NULL,
    confidence TEXT NOT NULL,
    importance_dimensions TEXT NOT NULL,
    importance TEXT NOT NULL,
    current_revision INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(project_id, namespace, key)
);
CREATE INDEX semantic_memories_project_namespace ON semantic_memories(project_id, namespace);
CREATE INDEX semantic_memories_project_status
    ON semantic_memories(project_id, status);

CREATE TABLE semantic_revisions (
    id TEXT PRIMARY KEY,
    semantic_memory_id TEXT NOT NULL REFERENCES semantic_memories(id),
    revision_number INTEGER NOT NULL,
    previous_statement TEXT,
    new_statement TEXT NOT NULL,
    change_type TEXT NOT NULL,
    reason TEXT NOT NULL,
    confidence TEXT NOT NULL,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(semantic_memory_id, revision_number)
);
CREATE INDEX semantic_revisions_memory
    ON semantic_revisions(semantic_memory_id);

CREATE TABLE lessons (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id),
    title TEXT NOT NULL,
    triggers TEXT NOT NULL,
    instruction TEXT NOT NULL,
    reason TEXT NOT NULL,
    category TEXT NOT NULL,
    scope TEXT NOT NULL,
    source TEXT NOT NULL,
    priority TEXT NOT NULL,
    confidence TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX lessons_project_status ON lessons(project_id, status);

CREATE TABLE memory_links (
    id TEXT PRIMARY KEY,
    source_type TEXT NOT NULL,
    source_id TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    relationship TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX memory_links_source ON memory_links(source_type, source_id);
CREATE INDEX memory_links_target ON memory_links(target_type, target_id);
"""
