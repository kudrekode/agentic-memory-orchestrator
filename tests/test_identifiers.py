"""Contract tests for prefixed ULID identifiers."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from src.identifiers import is_prefixed_ulid, new_prefixed_ulid
from src.models import (
    ConfidenceLevel,
    Episode,
    EpisodeOutcome,
    ImportanceDimensions,
    ImportanceLevel,
    MemoryLink,
    MemoryObjectType,
    MemoryRelationship,
    MemorySource,
    Project,
    SemanticMemory,
)


@pytest.mark.parametrize("prefix", ["prj", "epi", "sem", "rev", "les", "lnk"])
def test_new_prefixed_ulid_has_required_prefix_and_canonical_shape(prefix):
    identifier = new_prefixed_ulid(prefix)

    assert is_prefixed_ulid(identifier, prefix)
    assert len(identifier) == 30


def test_new_prefixed_ulids_are_unique():
    identifiers = {new_prefixed_ulid("epi") for _ in range(100)}

    assert len(identifiers) == 100


def test_new_prefixed_ulid_rejects_unknown_prefix():
    with pytest.raises(ValueError, match="unsupported"):
        new_prefixed_ulid("memory")


def test_project_rejects_wrong_prefixed_id(now):
    with pytest.raises(ValidationError, match="prj_"):
        Project(
            id="epi_01J00000000000000000000000",
            name="Example Project",
            created_at=now,
            updated_at=now,
        )


def test_project_rejects_blank_name(now):
    with pytest.raises(ValidationError, match="name"):
        Project(
            id=new_prefixed_ulid("prj"),
            name="   ",
            created_at=now,
            updated_at=now,
        )


def test_project_rejects_naive_timestamps():
    with pytest.raises(ValidationError, match="timezone"):
        Project(
            id=new_prefixed_ulid("prj"),
            name="Example Project",
            created_at=datetime(2026, 10, 5, 12, 0),
            updated_at=datetime(2026, 10, 5, 12, 0),
        )


def test_episode_rejects_wrong_entity_id_prefix(now, valid_dims):
    with pytest.raises(ValidationError, match="epi_"):
        Episode(
            id=new_prefixed_ulid("sem"),
            project_id=new_prefixed_ulid("prj"),
            title="Database connectivity incident",
            summary="Application services could not reach the database until ingress was corrected.",
            outcome=EpisodeOutcome.RESOLVED,
            source=MemorySource.AGENT_INFERRED,
            confidence=ConfidenceLevel.HIGH,
            importance_dimensions=valid_dims,
            importance=ImportanceLevel.HIGH,
            occurred_at=now,
            created_at=now,
        )


def test_memory_link_rejects_wrong_link_and_entity_id_prefixes(now):
    with pytest.raises(ValidationError, match="lnk_"):
        MemoryLink(
            id=new_prefixed_ulid("epi"),
            source_type=MemoryObjectType.EPISODE,
            source_id=new_prefixed_ulid("sem"),
            target_type=MemoryObjectType.SEMANTIC,
            target_id=new_prefixed_ulid("sem"),
            relationship=MemoryRelationship.SUPPORTS,
            created_at=now,
        )


def test_stored_importance_must_match_dimensions(now):
    with pytest.raises(ValidationError, match="importance"):
        SemanticMemory(
            id=new_prefixed_ulid("sem"),
            project_id=new_prefixed_ulid("prj"),
            namespace="architecture.database",
            key="postgres.application_ingress",
            statement="Services require database ingress on port 5432.",
            source=MemorySource.EPISODE,
            confidence=ConfidenceLevel.HIGH,
            importance_dimensions=ImportanceDimensions(
                future_usefulness=0,
                cost_of_rediscovery=0,
                blast_radius=0,
                decision_significance=0,
                recurrence_value=0,
            ),
            importance=ImportanceLevel.HIGH,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
