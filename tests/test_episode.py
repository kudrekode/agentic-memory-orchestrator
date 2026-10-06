"""Structural tests for Episode, including nested common types."""

import pytest
from pydantic import ValidationError

from src.models import (
    ConfidenceLevel,
    ConsolidationStatus,
    Episode,
    EpisodeOutcome,
    ImportanceLevel,
    MemorySource,
)


def test_episode_accepts_valid_payload(project_id, now, valid_dims, valid_scope):
    episode = Episode(
        id="epi_01J00000000000000000000000",
        project_id=project_id,
        title="Database connectivity failure",
        summary="Services could not reach the database due to a firewall misconfiguration.",
        details=["connection timeout", "Connection count near zero"],
        outcome=EpisodeOutcome.RESOLVED,
        entities=["Postgres", "orders-api"],
        tags=["networking", "incident"],
        scope=valid_scope,
        services=["orders-api"],
        source=MemorySource.AGENT_INFERRED,
        confidence=ConfidenceLevel.HIGH,
        importance_dimensions=valid_dims,
        importance=ImportanceLevel.HIGH,
        occurred_at=now,
        created_at=now,
    )

    assert episode.outcome == EpisodeOutcome.RESOLVED
    assert episode.scope.service == "orders-api"
    assert episode.importance_dimensions.future_usefulness == 2
    assert episode.consolidation_status == ConsolidationStatus.PENDING


def test_episode_defaults_lists_and_scope(project_id, now, valid_dims):
    episode = Episode(
        id="epi_01J00000000000000000000000",
        project_id=project_id,
        title="Quick note",
        summary="Useful session outcome.",
        outcome=EpisodeOutcome.INFORMATIONAL,
        source=MemorySource.DEVELOPER_EXPLICIT,
        confidence=ConfidenceLevel.CONFIRMED,
        importance_dimensions=valid_dims,
        importance=ImportanceLevel.HIGH,
        occurred_at=now,
        created_at=now,
    )

    assert episode.details == []
    assert episode.entities == []
    assert episode.tags == []
    assert episode.services == []
    assert episode.scope.environment is None


def test_episode_accepts_nested_dims_as_dict(project_id, now):
    episode = Episode(
        id="epi_01J00000000000000000000000",
        project_id=project_id,
        title="Dict nested types",
        summary="Scope and dims provided as dicts.",
        outcome="resolved",
        scope={"environment": "staging"},
        source="agent_inferred",
        confidence="high",
        importance_dimensions={
            "future_usefulness": 1,
            "cost_of_rediscovery": 1,
            "blast_radius": 1,
            "decision_significance": 1,
            "recurrence_value": 1,
        },
        importance="normal",
        occurred_at=now,
        created_at=now,
    )

    assert episode.scope.environment == "staging"
    assert episode.outcome == EpisodeOutcome.RESOLVED


def test_episode_rejects_invalid_outcome(project_id, now, valid_dims):
    with pytest.raises(ValidationError) as exc_info:
        Episode(
            id="epi_01J00000000000000000000000",
            project_id=project_id,
            title="Bad outcome",
            summary="summary",
            outcome="fixed",
            source=MemorySource.AGENT_INFERRED,
            confidence=ConfidenceLevel.HIGH,
            importance_dimensions=valid_dims,
            importance=ImportanceLevel.HIGH,
            occurred_at=now,
            created_at=now,
        )

    assert "outcome" in str(exc_info.value)


def test_episode_rejects_missing_summary(project_id, now, valid_dims):
    with pytest.raises(ValidationError) as exc_info:
        Episode(
            id="epi_01J00000000000000000000000",
            project_id=project_id,
            title="No summary",
            outcome=EpisodeOutcome.RESOLVED,
            source=MemorySource.AGENT_INFERRED,
            confidence=ConfidenceLevel.HIGH,
            importance_dimensions=valid_dims,
            importance=ImportanceLevel.HIGH,
            occurred_at=now,
            created_at=now,
        )

    assert "summary" in str(exc_info.value)


def test_episode_rejects_invalid_nested_dimensions(project_id, now):
    with pytest.raises(ValidationError) as exc_info:
        Episode(
            id="epi_01J00000000000000000000000",
            project_id=project_id,
            title="Bad dims",
            summary="summary",
            outcome=EpisodeOutcome.RESOLVED,
            source=MemorySource.AGENT_INFERRED,
            confidence=ConfidenceLevel.HIGH,
            importance_dimensions={
                "future_usefulness": 9,
                "cost_of_rediscovery": 0,
                "blast_radius": 0,
                "decision_significance": 0,
                "recurrence_value": 0,
            },
            importance=ImportanceLevel.HIGH,
            occurred_at=now,
            created_at=now,
        )

    assert "future_usefulness" in str(exc_info.value)
