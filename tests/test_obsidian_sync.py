"""Tests for the one-way SQLite to Obsidian projection."""

import json
from datetime import datetime, timezone

import pytest

from src.identifiers import new_prefixed_ulid
from src.models import (
    ConfidenceLevel,
    CreatedBy,
    Episode,
    EpisodeOutcome,
    ImportanceDimensions,
    ImportanceLevel,
    Lesson,
    LessonCategory,
    LessonPriority,
    MemoryLink,
    MemoryObjectType,
    MemoryRelationship,
    MemoryScope,
    MemorySource,
    Project,
    SemanticChangeType,
    SemanticMemory,
    SemanticRevision,
    WorkingState,
    WorkingStateStatus,
)
from src.obsidian_sync import ObsidianSyncError, sync_project
from src.storage import SQLiteMemoryStore


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


def _seed(store, now, dimensions, vault):
    project = Project(
        id=new_prefixed_ulid("prj"),
        name="Example Project",
        obsidian_path=str(vault),
        created_at=now,
        updated_at=now,
    )
    episode = Episode(
        id=new_prefixed_ulid("epi"),
        project_id=project.id,
        title="Database connectivity incident",
        summary="Services could not reach the database until ingress was corrected.",
        details=["A connection timeout occurred on the first query."],
        outcome=EpisodeOutcome.RESOLVED,
        tags=["incident"],
        scope=MemoryScope(environment="production", service="orders-api"),
        source=MemorySource.DEVELOPER_EXPLICIT,
        confidence=ConfidenceLevel.CONFIRMED,
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
        statement="Production services require database ingress on port 5432.",
        scope=MemoryScope(environment="production", service="orders-api"),
        source=MemorySource.EPISODE,
        confidence=ConfidenceLevel.HIGH,
        importance_dimensions=dimensions,
        importance=ImportanceLevel.HIGH,
        created_at=now,
        updated_at=now,
    )
    lesson = Lesson(
        id=new_prefixed_ulid("les"),
        project_id=project.id,
        title="Check security groups before application code",
        triggers=["database timeout", "connection timeout"],
        instruction="Inspect database and service firewall rules first.",
        reason="This is a recurring connectivity failure mode.",
        category=LessonCategory.DEBUGGING,
        source=MemorySource.AGENT_INFERRED,
        priority=LessonPriority.HIGH,
        confidence=ConfidenceLevel.HIGH,
        created_at=now,
        updated_at=now,
    )
    store.save_project(project)
    store.save_episode(episode)
    store.save_semantic_memory(semantic)
    store.save_semantic_revision(
        SemanticRevision(
            id=new_prefixed_ulid("rev"),
            semantic_memory_id=semantic.id,
            revision_number=1,
            previous_statement=None,
            new_statement=semantic.statement,
            change_type=SemanticChangeType.CREATED,
            reason="Confirmed after the ingress rule was added.",
            confidence=ConfidenceLevel.HIGH,
            created_by=CreatedBy.AGENT,
            created_at=now,
        )
    )
    store.save_lesson(lesson)
    store.save_memory_link(
        MemoryLink(
            id=new_prefixed_ulid("lnk"),
            source_type=MemoryObjectType.EPISODE,
            source_id=episode.id,
            target_type=MemoryObjectType.SEMANTIC,
            target_id=semantic.id,
            relationship=MemoryRelationship.SUPPORTS,
            created_at=now,
        )
    )
    store.replace_working_state(
        WorkingState(
            project_id=project.id,
            focus="Database connectivity",
            status=WorkingStateStatus.INVESTIGATING,
            known=["A connection timeout occurs on the first query."],
            next_actions=["Verify the staging security group."],
            updated_at=now,
        )
    )
    return project, episode, semantic, lesson


def test_sync_writes_notes_and_wikilinks(store, now, dimensions, tmp_path):
    vault = tmp_path / "vault"
    project, episode, semantic, lesson = _seed(store, now, dimensions, vault)

    result = sync_project(store, project.id)

    episode_note = (vault / "Episodes" / f"{episode.id}.md").read_text()
    semantic_note = (vault / "Semantic" / f"{semantic.id}.md").read_text()
    current_state = (vault / "Current State.md").read_text()
    assert result.removed == []
    assert f"Episodes/{episode.id}.md" in result.written
    assert "Services could not reach the database" in episode_note
    assert f"[[{semantic.id}|architecture.database/postgres.application_ingress]]" in episode_note
    assert "supports by" in semantic_note
    assert "Confirmed after the ingress rule was added." in semantic_note
    assert "Database connectivity" in current_state
    assert f"[[{lesson.id}|Check security groups before application code]]" in (
        vault / "Lessons.md"
    ).read_text()
    assert (vault / ".agent-memory-manifest.json").is_file()


def test_second_sync_is_stable(store, now, dimensions, tmp_path):
    vault = tmp_path / "vault"
    project, *_ = _seed(store, now, dimensions, vault)
    first = sync_project(store, project.id)
    before = {
        relative: (vault / relative).read_text()
        for relative in first.written
    }

    second = sync_project(store, project.id)

    assert second.removed == []
    assert second.written == first.written
    assert {relative: (vault / relative).read_text() for relative in second.written} == before


def test_sync_removes_stale_generated_files_only(store, now, dimensions, tmp_path):
    vault = tmp_path / "vault"
    project, *_ = _seed(store, now, dimensions, vault)
    sync_project(store, project.id)
    stale = vault / "Episodes" / "stale.md"
    stale.write_text("stale")
    outside = tmp_path / "outside.md"
    outside.write_text("keep")
    manifest_path = vault / ".agent-memory-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["files"].extend(["Episodes/stale.md", "../outside.md"])
    manifest_path.write_text(json.dumps(manifest))

    result = sync_project(store, project.id)

    assert "Episodes/stale.md" in result.removed
    assert not stale.exists()
    assert outside.read_text() == "keep"


def test_sync_requires_an_obsidian_path(store, now):
    project = Project(
        id=new_prefixed_ulid("prj"),
        name="Example Project",
        created_at=now,
        updated_at=now,
    )
    store.save_project(project)

    with pytest.raises(ObsidianSyncError):
        sync_project(store, project.id)
