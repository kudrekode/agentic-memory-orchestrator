"""Structural tests for MemoryLink."""

import pytest
from pydantic import ValidationError

from src.models import MemoryLink, MemoryObjectType, MemoryRelationship


def test_memory_link_accepts_valid_payload(now):
    link = MemoryLink(
        id="lnk_01J00000000000000000000000",
        source_type=MemoryObjectType.EPISODE,
        source_id="epi_01J00000000000000000000000",
        target_type=MemoryObjectType.SEMANTIC,
        target_id="sem_01J00000000000000000000000",
        relationship=MemoryRelationship.SUPPORTS,
        created_at=now,
    )

    assert link.source_type == MemoryObjectType.EPISODE
    assert link.relationship == MemoryRelationship.SUPPORTS


def test_memory_link_accepts_enum_values_as_strings(now):
    link = MemoryLink(
        id="lnk_01J00000000000000000000000",
        source_type="lesson",
        source_id="les_01J00000000000000000000000",
        target_type="episode",
        target_id="epi_01J00000000000000000000000",
        relationship="derived_from",
        created_at=now,
    )

    assert link.source_type == MemoryObjectType.LESSON
    assert link.relationship == MemoryRelationship.DERIVED_FROM


def test_memory_link_rejects_invalid_source_type(now):
    with pytest.raises(ValidationError) as exc_info:
        MemoryLink(
            id="lnk_01J00000000000000000000000",
            source_type="working_state",
            source_id="ws_1",
            target_type=MemoryObjectType.SEMANTIC,
            target_id="sem_1",
            relationship=MemoryRelationship.RELATED_TO,
            created_at=now,
        )

    assert "source_type" in str(exc_info.value)


def test_memory_link_rejects_invalid_relationship(now):
    with pytest.raises(ValidationError) as exc_info:
        MemoryLink(
            id="lnk_01J00000000000000000000000",
            source_type=MemoryObjectType.EPISODE,
            source_id="epi_1",
            target_type=MemoryObjectType.LESSON,
            target_id="les_1",
            relationship="caused_by",
            created_at=now,
        )

    assert "relationship" in str(exc_info.value)


def test_memory_link_rejects_missing_target_id(now):
    with pytest.raises(ValidationError) as exc_info:
        MemoryLink(
            id="lnk_01J00000000000000000000000",
            source_type=MemoryObjectType.EPISODE,
            source_id="epi_1",
            target_type=MemoryObjectType.SEMANTIC,
            relationship=MemoryRelationship.SUPPORTS,
            created_at=now,
        )

    assert "target_id" in str(exc_info.value)
