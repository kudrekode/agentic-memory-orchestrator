"""Structural tests for SemanticMemory and SemanticRevision."""

import pytest
from pydantic import ValidationError

from src.models import (
    ConfidenceLevel,
    CreatedBy,
    ImportanceLevel,
    MemorySource,
    SemanticChangeType,
    SemanticMemory,
    SemanticRevision,
    SemanticStatus,
)


def test_semantic_memory_accepts_valid_payload(
    project_id, now, valid_dims, valid_scope
):
    memory = SemanticMemory(
        id="sem_01J00000000000000000000000",
        project_id=project_id,
        namespace="architecture.database",
        key="postgres.application_ingress",
        statement="Production services require database firewall ingress on 5432.",
        scope=valid_scope,
        source=MemorySource.EPISODE,
        status=SemanticStatus.ACTIVE,
        confidence=ConfidenceLevel.HIGH,
        importance_dimensions=valid_dims,
        importance=ImportanceLevel.HIGH,
        current_revision=1,
        created_at=now,
        updated_at=now,
    )

    assert memory.namespace == "architecture.database"
    assert memory.key == "postgres.application_ingress"
    assert memory.scope.environment == "production"


def test_semantic_memory_defaults(project_id, now, valid_dims):
    memory = SemanticMemory(
        id="sem_01J00000000000000000000000",
        project_id=project_id,
        namespace="convention.git",
        key="branch_naming",
        statement="Feature branches use feat/ prefix.",
        source=MemorySource.DEVELOPER_EXPLICIT,
        confidence=ConfidenceLevel.CONFIRMED,
        importance_dimensions=valid_dims,
        importance=ImportanceLevel.HIGH,
        created_at=now,
        updated_at=now,
    )

    assert memory.status == SemanticStatus.ACTIVE
    assert memory.current_revision == 1
    assert memory.scope.service is None


def test_semantic_memory_rejects_invalid_status(project_id, now, valid_dims):
    with pytest.raises(ValidationError) as exc_info:
        SemanticMemory(
            id="sem_01J00000000000000000000000",
            project_id=project_id,
            namespace="architecture.database",
            key="postgres.application_ingress",
            statement="statement",
            source=MemorySource.EPISODE,
            status="archived",
            confidence=ConfidenceLevel.HIGH,
            importance_dimensions=valid_dims,
            importance=ImportanceLevel.HIGH,
            created_at=now,
            updated_at=now,
        )

    assert "status" in str(exc_info.value)


def test_semantic_memory_rejects_missing_key(project_id, now, valid_dims):
    with pytest.raises(ValidationError) as exc_info:
        SemanticMemory(
            id="sem_01J00000000000000000000000",
            project_id=project_id,
            namespace="architecture.database",
            statement="statement",
            source=MemorySource.EPISODE,
            confidence=ConfidenceLevel.HIGH,
            importance_dimensions=valid_dims,
            importance=ImportanceLevel.HIGH,
            created_at=now,
            updated_at=now,
        )

    assert "key" in str(exc_info.value)


def test_semantic_memory_rejects_invalid_nested_dimensions(project_id, now):
    with pytest.raises(ValidationError) as exc_info:
        SemanticMemory(
            id="sem_01J00000000000000000000000",
            project_id=project_id,
            namespace="architecture.database",
            key="postgres.application_ingress",
            statement="statement",
            source=MemorySource.EPISODE,
            confidence=ConfidenceLevel.HIGH,
            importance_dimensions={
                "future_usefulness": -1,
                "cost_of_rediscovery": 0,
                "blast_radius": 0,
                "decision_significance": 0,
                "recurrence_value": 0,
            },
            importance=ImportanceLevel.HIGH,
            created_at=now,
            updated_at=now,
        )

    assert "future_usefulness" in str(exc_info.value)


def test_semantic_revision_accepts_valid_payload(now):
    revision = SemanticRevision(
        id="rev_01J00000000000000000000000",
        semantic_memory_id="sem_01J00000000000000000000000",
        revision_number=2,
        previous_statement="Old ingress rule.",
        new_statement="Updated ingress rule on 5432.",
        change_type=SemanticChangeType.CORRECTED,
        reason="Developer confirmed port.",
        confidence=ConfidenceLevel.CONFIRMED,
        created_by=CreatedBy.DEVELOPER,
        created_at=now,
    )

    assert revision.change_type == SemanticChangeType.CORRECTED
    assert revision.created_by == CreatedBy.DEVELOPER


def test_semantic_revision_allows_null_previous_statement(now):
    revision = SemanticRevision(
        id="rev_01J00000000000000000000000",
        semantic_memory_id="sem_01J00000000000000000000000",
        revision_number=1,
        previous_statement=None,
        new_statement="Initial statement.",
        change_type=SemanticChangeType.CREATED,
        reason="First revision.",
        confidence=ConfidenceLevel.HIGH,
        created_by=CreatedBy.AGENT,
        created_at=now,
    )

    assert revision.previous_statement is None


def test_semantic_revision_rejects_invalid_change_type(now):
    with pytest.raises(ValidationError) as exc_info:
        SemanticRevision(
            id="rev_01J00000000000000000000000",
            semantic_memory_id="sem_01J00000000000000000000000",
            revision_number=1,
            previous_statement=None,
            new_statement="statement",
            change_type="rewritten",
            reason="bad type",
            confidence=ConfidenceLevel.HIGH,
            created_by=CreatedBy.AGENT,
            created_at=now,
        )

    assert "change_type" in str(exc_info.value)


def test_semantic_revision_rejects_missing_reason(now):
    with pytest.raises(ValidationError) as exc_info:
        SemanticRevision(
            id="rev_01J00000000000000000000000",
            semantic_memory_id="sem_01J00000000000000000000000",
            revision_number=1,
            previous_statement=None,
            new_statement="statement",
            change_type=SemanticChangeType.CREATED,
            confidence=ConfidenceLevel.HIGH,
            created_by=CreatedBy.AGENT,
            created_at=now,
        )

    assert "reason" in str(exc_info.value)
