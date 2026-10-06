"""Structural tests for MemoryCandidate."""

import pytest
from pydantic import ValidationError

from src.models import ConfidenceLevel, MemoryCandidate, ProposedMemoryType


def test_memory_candidate_accepts_valid_payload(valid_dims):
    candidate = MemoryCandidate(
        proposed_type=ProposedMemoryType.EPISODE,
        content={
            "title": "Database outage",
            "summary": "SG misconfiguration blocked DB access.",
        },
        rationale="Confirmed production incident with lasting knowledge.",
        confidence=ConfidenceLevel.HIGH,
        importance_dimensions=valid_dims,
        related_memory_queries=["database firewall"],
    )

    assert candidate.proposed_type == ProposedMemoryType.EPISODE
    assert candidate.content["title"] == "Database outage"
    assert candidate.importance_dimensions is not None


def test_memory_candidate_allows_null_importance_dimensions():
    candidate = MemoryCandidate(
        proposed_type=ProposedMemoryType.IGNORE,
        content={},
        rationale="Routine chatter, not worth storing.",
        confidence=ConfidenceLevel.LOW,
    )

    assert candidate.importance_dimensions is None
    assert candidate.related_memory_queries == []


def test_memory_candidate_accepts_working_state_update():
    candidate = MemoryCandidate(
        proposed_type="working_state_update",
        content={"focus": "SG investigation", "status": "investigating"},
        rationale="Active debugging session.",
        confidence="medium",
    )

    assert candidate.proposed_type == ProposedMemoryType.WORKING_STATE_UPDATE
    assert candidate.confidence == ConfidenceLevel.MEDIUM


def test_memory_candidate_rejects_invalid_proposed_type():
    with pytest.raises(ValidationError) as exc_info:
        MemoryCandidate(
            proposed_type="note",
            content={},
            rationale="bad type",
            confidence=ConfidenceLevel.LOW,
        )

    assert "proposed_type" in str(exc_info.value)


def test_memory_candidate_rejects_non_dict_content():
    with pytest.raises(ValidationError) as exc_info:
        MemoryCandidate(
            proposed_type=ProposedMemoryType.SEMANTIC,
            content="not a dict",
            rationale="bad content shape",
            confidence=ConfidenceLevel.MEDIUM,
        )

    assert "content" in str(exc_info.value)


def test_memory_candidate_rejects_invalid_nested_dimensions():
    with pytest.raises(ValidationError) as exc_info:
        MemoryCandidate(
            proposed_type=ProposedMemoryType.LESSON,
            content={"title": "x"},
            rationale="dims out of range",
            confidence=ConfidenceLevel.MEDIUM,
            importance_dimensions={
                "future_usefulness": 4,
                "cost_of_rediscovery": 0,
                "blast_radius": 0,
                "decision_significance": 0,
                "recurrence_value": 0,
            },
        )

    assert "future_usefulness" in str(exc_info.value)


def test_memory_candidate_rejects_missing_rationale():
    with pytest.raises(ValidationError) as exc_info:
        MemoryCandidate(
            proposed_type=ProposedMemoryType.EPISODE,
            content={"title": "x"},
            confidence=ConfidenceLevel.HIGH,
        )

    assert "rationale" in str(exc_info.value)
