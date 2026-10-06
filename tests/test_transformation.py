"""Tests for turning accepted candidates into server-owned memory records."""

from datetime import datetime, timezone

import pytest

from src.models import (
    ConfidenceLevel,
    Episode,
    ImportanceDimensions,
    Lesson,
    MemoryCandidate,
    MemorySource,
    ProposedMemoryType,
    SemanticMemory,
)
from src.transformation import CandidateTransformationError, materialize_candidate


@pytest.fixture
def project_id() -> str:
    return "prj_01J00000000000000000000000"


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


def test_materialize_episode_assigns_server_owned_fields(project_id, now, dimensions):
    record = materialize_candidate(
        MemoryCandidate(
            proposed_type=ProposedMemoryType.EPISODE,
            content={
                "title": "Database connectivity incident",
                "summary": "Application services could not reach the database until ingress was corrected.",
                "outcome": "resolved",
            },
            rationale="A production issue with reusable debugging context.",
            confidence=ConfidenceLevel.HIGH,
            importance_dimensions=dimensions,
        ),
        project_id=project_id,
        now=now,
    )

    assert isinstance(record, Episode)
    assert record.id.startswith("epi_")
    assert record.project_id == project_id
    assert record.source is MemorySource.AGENT_INFERRED
    assert record.importance.value == "high"
    assert record.occurred_at == now
    assert record.created_at == now


def test_materialize_semantic_creates_deterministic_importance(
    project_id, now, dimensions
):
    record = materialize_candidate(
        MemoryCandidate(
            proposed_type=ProposedMemoryType.SEMANTIC,
            content={
                "namespace": "architecture.database",
                "key": "postgres.application_ingress",
                "statement": "Services require database ingress on port 5432.",
            },
            rationale="Observed during a confirmed incident.",
            confidence=ConfidenceLevel.HIGH,
            importance_dimensions=dimensions,
        ),
        project_id=project_id,
        now=now,
        source=MemorySource.EPISODE,
    )

    assert isinstance(record, SemanticMemory)
    assert record.id.startswith("sem_")
    assert record.current_revision == 1
    assert record.importance.value == "high"
    assert record.created_at == record.updated_at == now


def test_materialize_lesson_does_not_require_importance_dimensions(project_id, now):
    record = materialize_candidate(
        MemoryCandidate(
            proposed_type=ProposedMemoryType.LESSON,
            content={
                "title": "Check ingress before application code",
                "triggers": ["database timeout"],
                "instruction": "Inspect database and service firewall rules first.",
                "reason": "This failure mode recurs during connectivity incidents.",
                "category": "debugging",
                "priority": "high",
            },
            rationale="A reusable debugging procedure.",
            confidence=ConfidenceLevel.HIGH,
        ),
        project_id=project_id,
        now=now,
    )

    assert isinstance(record, Lesson)
    assert record.id.startswith("les_")
    assert record.created_at == record.updated_at == now


@pytest.mark.parametrize(
    "proposed_type, content",
    [
        (
            ProposedMemoryType.EPISODE,
            {
                "title": "Incomplete incident",
                "summary": "The failure was investigated during the deployment.",
                "outcome": "resolved",
            },
        ),
        (
            ProposedMemoryType.SEMANTIC,
            {
                "namespace": "architecture.database",
                "key": "ingress",
                "statement": "The database requires ingress from the application service.",
            },
        ),
    ],
)
def test_materialize_requires_importance_dimensions(project_id, now, proposed_type, content):
    candidate = MemoryCandidate(
        proposed_type=proposed_type,
        content=content,
        rationale="Candidate needs a score.",
        confidence=ConfidenceLevel.HIGH,
    )

    with pytest.raises(CandidateTransformationError, match="importance_dimensions"):
        materialize_candidate(candidate, project_id=project_id, now=now)


def test_materialize_rejects_invalid_business_candidate(project_id, now, dimensions):
    candidate = MemoryCandidate(
        proposed_type=ProposedMemoryType.EPISODE,
        content={
            "title": "Chatter",
            "summary": "Done.",
            "outcome": "informational",
        },
        rationale="Not a memory.",
        confidence=ConfidenceLevel.LOW,
        importance_dimensions=dimensions,
    )

    with pytest.raises(CandidateTransformationError, match="routine chatter"):
        materialize_candidate(candidate, project_id=project_id, now=now)
