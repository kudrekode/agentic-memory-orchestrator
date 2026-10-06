"""Integration tests for the local SQLite persistence layer."""

from datetime import datetime, timezone

import pytest

from src.identifiers import new_prefixed_ulid
from src.models import (
    ConfidenceLevel,
    Episode,
    EpisodeOutcome,
    ImportanceDimensions,
    ImportanceLevel,
    MemoryLink,
    MemoryObjectType,
    MemoryRelationship,
    MemoryScope,
    MemorySource,
    Project,
    SemanticMemory,
    WorkingState,
    WorkingStateStatus,
)
from src.storage import MemoryNotFoundError, SQLiteMemoryStore


@pytest.fixture
def now() -> datetime:
    return datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def dimensions() -> ImportanceDimensions:
    return ImportanceDimensions(
        future_usefulness=2,
        cost_of_rediscovery=2,
        blast_radius=1,
        decision_significance=2,
        recurrence_value=1,
    )


@pytest.fixture
def store(tmp_path) -> SQLiteMemoryStore:
    database = SQLiteMemoryStore(tmp_path / "memory.db")
    database.migrate()
    return database


def test_new_database_has_no_schema_version_before_migration(tmp_path):
    assert SQLiteMemoryStore(tmp_path / "memory.db").schema_version == 0


@pytest.fixture
def project(now) -> Project:
    return Project(
        id=new_prefixed_ulid("prj"),
        name="Example Project",
        repo_path="/code/example-project",
        created_at=now,
        updated_at=now,
    )


def test_migrate_creates_versioned_local_database(store):
    assert store.schema_version == 1


def test_project_and_episode_round_trip_preserves_nested_data(
    store, project, now, dimensions
):
    store.save_project(project)
    episode = Episode(
        id=new_prefixed_ulid("epi"),
        project_id=project.id,
        title="Database connectivity incident",
        summary="Application services could not reach the database until ingress was corrected.",
        details=["A connection timeout occurred on the first query."],
        outcome=EpisodeOutcome.RESOLVED,
        entities=["Postgres", "orders-api"],
        tags=["incident", "networking"],
        scope=MemoryScope(environment="production", service="orders-api"),
        services=["orders-api"],
        source=MemorySource.AGENT_INFERRED,
        confidence=ConfidenceLevel.HIGH,
        importance_dimensions=dimensions,
        importance=ImportanceLevel.HIGH,
        occurred_at=now,
        created_at=now,
    )

    store.save_episode(episode)

    assert store.get_project(project.id) == project
    assert store.get_episode(episode.id, project.id) == episode


def test_storage_enforces_project_isolation(store, project, now, dimensions):
    store.save_project(project)
    episode = Episode(
        id=new_prefixed_ulid("epi"),
        project_id=project.id,
        title="Database connectivity incident",
        summary="Application services could not reach the database until ingress was corrected.",
        outcome=EpisodeOutcome.RESOLVED,
        source=MemorySource.AGENT_INFERRED,
        confidence=ConfidenceLevel.HIGH,
        importance_dimensions=dimensions,
        importance=ImportanceLevel.HIGH,
        occurred_at=now,
        created_at=now,
    )
    store.save_episode(episode)

    with pytest.raises(MemoryNotFoundError):
        store.get_episode(episode.id, new_prefixed_ulid("prj"))


def test_semantic_key_is_unique_within_a_project(store, project, now, dimensions):
    store.save_project(project)
    semantic = SemanticMemory(
        id=new_prefixed_ulid("sem"),
        project_id=project.id,
        namespace="architecture.database",
        key="postgres.application_ingress",
        statement="Services require database ingress on port 5432.",
        source=MemorySource.EPISODE,
        confidence=ConfidenceLevel.HIGH,
        importance_dimensions=dimensions,
        importance=ImportanceLevel.HIGH,
        created_at=now,
        updated_at=now,
    )
    store.save_semantic_memory(semantic)

    duplicate = semantic.model_copy(update={"id": new_prefixed_ulid("sem")})
    with pytest.raises(ValueError, match="already exists"):
        store.save_semantic_memory(duplicate)


def test_working_state_replacement_keeps_one_state_per_project(store, project, now):
    store.save_project(project)
    store.replace_working_state(
        WorkingState(
            project_id=project.id,
            focus="Initial investigation",
            status=WorkingStateStatus.INVESTIGATING,
            known=["The database connection times out."],
            updated_at=now,
        )
    )
    replacement = WorkingState(
        project_id=project.id,
        focus="Verify security-group ingress",
        status=WorkingStateStatus.TESTING,
        next_actions=["Test connectivity from the service."],
        updated_at=now,
    )
    store.replace_working_state(replacement)

    assert store.get_working_state(project.id) == replacement


def test_memory_link_requires_persisted_typed_endpoints(store, project, now, dimensions):
    store.save_project(project)
    episode = Episode(
        id=new_prefixed_ulid("epi"),
        project_id=project.id,
        title="Database connectivity incident",
        summary="Application services could not reach the database until ingress was corrected.",
        outcome=EpisodeOutcome.RESOLVED,
        source=MemorySource.AGENT_INFERRED,
        confidence=ConfidenceLevel.HIGH,
        importance_dimensions=dimensions,
        importance=ImportanceLevel.HIGH,
        occurred_at=now,
        created_at=now,
    )
    semantic = SemanticMemory(
        id=new_prefixed_ulid("sem"),
        project_id=project.id,
        namespace="architecture.database",
        key="postgres.application_ingress",
        statement="Services require database ingress on port 5432.",
        source=MemorySource.EPISODE,
        confidence=ConfidenceLevel.HIGH,
        importance_dimensions=dimensions,
        importance=ImportanceLevel.HIGH,
        created_at=now,
        updated_at=now,
    )
    store.save_records([episode, semantic])

    link = MemoryLink(
        id=new_prefixed_ulid("lnk"),
        source_type=MemoryObjectType.EPISODE,
        source_id=episode.id,
        target_type=MemoryObjectType.SEMANTIC,
        target_id=semantic.id,
        relationship=MemoryRelationship.SUPPORTS,
        created_at=now,
    )
    store.save_memory_link(link)

    assert store.get_memory_link(link.id) == link
