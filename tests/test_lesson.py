"""Structural tests for Lesson."""

import pytest
from pydantic import ValidationError

from src.models import (
    ConfidenceLevel,
    Lesson,
    LessonCategory,
    LessonPriority,
    LessonStatus,
    MemorySource,
)


def test_lesson_accepts_valid_payload(project_id, now, valid_scope):
    lesson = Lesson(
        id="les_01J00000000000000000000000",
        project_id=project_id,
        title="Check SG ingress first",
        triggers=["db timeout", "connection timeout"],
        instruction="Inspect database and service firewall rules before app code.",
        reason="Recurring failure mode across incidents.",
        category=LessonCategory.DEBUGGING,
        scope=valid_scope,
        source=MemorySource.CONSOLIDATION,
        priority=LessonPriority.HIGH,
        confidence=ConfidenceLevel.HIGH,
        status=LessonStatus.ACTIVE,
        created_at=now,
        updated_at=now,
    )

    assert lesson.category == LessonCategory.DEBUGGING
    assert lesson.triggers == ["db timeout", "connection timeout"]
    assert lesson.scope.service == "orders-api"


def test_lesson_defaults_status_and_scope(project_id, now):
    lesson = Lesson(
        id="les_01J00000000000000000000000",
        project_id=project_id,
        title="Use feat/ prefix",
        triggers=["creating a branch"],
        instruction="Name feature branches feat/...",
        reason="Team convention.",
        category=LessonCategory.PROJECT_CONVENTION,
        source=MemorySource.DEVELOPER_EXPLICIT,
        priority=LessonPriority.NORMAL,
        confidence=ConfidenceLevel.CONFIRMED,
        created_at=now,
        updated_at=now,
    )

    assert lesson.status == LessonStatus.ACTIVE
    assert lesson.scope.environment is None


def test_lesson_rejects_invalid_category(project_id, now):
    with pytest.raises(ValidationError) as exc_info:
        Lesson(
            id="les_01J00000000000000000000000",
            project_id=project_id,
            title="Bad category",
            triggers=["x"],
            instruction="do y",
            reason="because z",
            category="security",
            source=MemorySource.AGENT_INFERRED,
            priority=LessonPriority.LOW,
            confidence=ConfidenceLevel.MEDIUM,
            created_at=now,
            updated_at=now,
        )

    assert "category" in str(exc_info.value)


def test_lesson_rejects_invalid_priority(project_id, now):
    with pytest.raises(ValidationError) as exc_info:
        Lesson(
            id="les_01J00000000000000000000000",
            project_id=project_id,
            title="Bad priority",
            triggers=["x"],
            instruction="do y",
            reason="because z",
            category=LessonCategory.TOOLING,
            source=MemorySource.AGENT_INFERRED,
            priority="medium",
            confidence=ConfidenceLevel.MEDIUM,
            created_at=now,
            updated_at=now,
        )

    assert "priority" in str(exc_info.value)


def test_lesson_rejects_missing_triggers(project_id, now):
    with pytest.raises(ValidationError) as exc_info:
        Lesson(
            id="les_01J00000000000000000000000",
            project_id=project_id,
            title="No triggers",
            instruction="do y",
            reason="because z",
            category=LessonCategory.WORKFLOW,
            source=MemorySource.AGENT_INFERRED,
            priority=LessonPriority.NORMAL,
            confidence=ConfidenceLevel.MEDIUM,
            created_at=now,
            updated_at=now,
        )

    assert "triggers" in str(exc_info.value)


def test_lesson_rejects_invalid_status(project_id, now):
    with pytest.raises(ValidationError) as exc_info:
        Lesson(
            id="les_01J00000000000000000000000",
            project_id=project_id,
            title="Bad status",
            triggers=["x"],
            instruction="do y",
            reason="because z",
            category=LessonCategory.OTHER,
            source=MemorySource.AGENT_INFERRED,
            priority=LessonPriority.LOW,
            confidence=ConfidenceLevel.LOW,
            status="archived",
            created_at=now,
            updated_at=now,
        )

    assert "status" in str(exc_info.value)
