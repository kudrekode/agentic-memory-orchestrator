"""Transform validated candidates into typed, server-owned memory records."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import TypeAlias

from pydantic import ValidationError

from src.identifiers import new_prefixed_ulid
from src.models import (
    Episode,
    Lesson,
    MemoryCandidate,
    MemorySource,
    ProposedMemoryType,
    SemanticMemory,
)
from src.validation import (
    calculate_importance,
    validate_episode_candidate,
    validate_lesson_candidate,
    validate_semantic_candidate,
)

StoredMemory: TypeAlias = Episode | SemanticMemory | Lesson
IdentifierFactory: TypeAlias = Callable[[str], str]


class CandidateTransformationError(ValueError):
    """A candidate cannot be safely materialized into a stored memory record."""


def materialize_candidate(
    candidate: MemoryCandidate,
    *,
    project_id: str,
    now: datetime,
    source: MemorySource = MemorySource.AGENT_INFERRED,
    id_factory: IdentifierFactory = new_prefixed_ulid,
) -> StoredMemory:
    """Validate and enrich a candidate without performing persistence.

    Server-owned values (IDs, timestamps, source, and importance) are never
    accepted from candidate content.
    """

    _reject_server_owned_fields(candidate)

    if candidate.proposed_type is ProposedMemoryType.EPISODE:
        _require_valid(validate_episode_candidate(candidate))
        dimensions = _require_dimensions(candidate)
        return _build(
            Episode,
            candidate.content,
            {
                "id": id_factory("epi"),
                "project_id": project_id,
                "source": source,
                "confidence": candidate.confidence,
                "importance_dimensions": dimensions,
                "importance": calculate_importance(dimensions),
                "occurred_at": now,
                "created_at": now,
            },
        )
    if candidate.proposed_type is ProposedMemoryType.SEMANTIC:
        _require_valid(validate_semantic_candidate(candidate))
        dimensions = _require_dimensions(candidate)
        return _build(
            SemanticMemory,
            candidate.content,
            {
                "id": id_factory("sem"),
                "project_id": project_id,
                "source": source,
                "confidence": candidate.confidence,
                "importance_dimensions": dimensions,
                "importance": calculate_importance(dimensions),
                "created_at": now,
                "updated_at": now,
            },
        )
    if candidate.proposed_type is ProposedMemoryType.LESSON:
        _require_valid(validate_lesson_candidate(candidate))
        return _build(
            Lesson,
            candidate.content,
            {
                "id": id_factory("les"),
                "project_id": project_id,
                "source": source,
                "confidence": candidate.confidence,
                "created_at": now,
                "updated_at": now,
            },
        )
    if candidate.proposed_type is ProposedMemoryType.WORKING_STATE_UPDATE:
        raise CandidateTransformationError(
            "working-state updates require the current stored state and are applied separately"
        )
    raise CandidateTransformationError("ignore candidates cannot be materialized")


def _require_valid(result: object) -> None:
    errors = getattr(result, "errors", ())
    if errors:
        raise CandidateTransformationError("; ".join(errors))


def _require_dimensions(candidate: MemoryCandidate):
    if candidate.importance_dimensions is None:
        raise CandidateTransformationError(
            "importance_dimensions are required for stored episodes and semantic memories"
        )
    return candidate.importance_dimensions


def _reject_server_owned_fields(candidate: MemoryCandidate) -> None:
    server_fields = {
        "id",
        "project_id",
        "source",
        "confidence",
        "importance",
        "importance_dimensions",
        "created_at",
        "updated_at",
        "occurred_at",
        "current_revision",
    }
    supplied = sorted(server_fields & candidate.content.keys())
    if supplied:
        raise CandidateTransformationError(
            f"candidate content cannot set server-owned fields: {', '.join(supplied)}"
        )


def _build(
    model_type: type[Episode] | type[SemanticMemory] | type[Lesson],
    content: dict,
    server_fields: dict,
) -> StoredMemory:
    try:
        return model_type.model_validate({**content, **server_fields})
    except ValidationError as error:
        raise CandidateTransformationError(str(error)) from error
