"""Business-rule tests for memory candidates."""

import pytest
from pydantic import ValidationError

from src.models import ImportanceDimensions, ImportanceLevel
from src.validation import (
    calculate_importance,
    validate_episode_candidate,
    validate_lesson_candidate,
    validate_semantic_candidate,
    validate_working_state_update,
)


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (0, ImportanceLevel.LOW),
        (3, ImportanceLevel.LOW),
        (4, ImportanceLevel.NORMAL),
        (7, ImportanceLevel.NORMAL),
        (8, ImportanceLevel.HIGH),
        (11, ImportanceLevel.HIGH),
        (12, ImportanceLevel.CRITICAL),
        (15, ImportanceLevel.CRITICAL),
    ],
)
def test_calculate_importance_uses_documented_thresholds(score, expected):
    dimensions = ImportanceDimensions(
        future_usefulness=3,
        cost_of_rediscovery=3,
        blast_radius=3,
        decision_significance=3,
        recurrence_value=score - 12,
    ) if score >= 12 else _dimensions_for_score(score)

    assert calculate_importance(dimensions) is expected


def test_calculate_importance_validates_mapping_bounds():
    with pytest.raises(ValidationError):
        calculate_importance(
            {
                "future_usefulness": 4,
                "cost_of_rediscovery": 0,
                "blast_radius": 0,
                "decision_significance": 0,
                "recurrence_value": 0,
            }
        )


def test_episode_candidate_accepts_coherent_event():
    result = validate_episode_candidate(
        {
            "title": "Database connectivity failure",
            "summary": "Application services could not reach the database until the firewall ingress rule was corrected.",
            "outcome": "resolved",
        }
    )

    assert result.valid


def test_episode_candidate_rejects_hypothetical_resolved_outcome():
    result = validate_episode_candidate(
        {
            "title": "Database incident",
            "summary": "The missing ingress rule might have caused the timeout, but this remains unverified.",
            "outcome": "resolved",
        }
    )

    assert not result
    assert any("hypothesis" in error for error in result.errors)


def test_semantic_candidate_requires_scope_for_environment_specific_knowledge():
    result = validate_semantic_candidate(
        {
            "namespace": "architecture.database",
            "key": "postgres.application_ingress",
            "statement": "Production services require database firewall ingress on port 5432.",
        }
    )

    assert not result
    assert "scope is required" in result.errors[0]


def test_semantic_candidate_accepts_scoped_reusable_fact():
    result = validate_semantic_candidate(
        {
            "namespace": "architecture.database",
            "key": "postgres.application_ingress",
            "statement": "Services require database firewall ingress on port 5432.",
            "scope": {"environment": "production", "service": "orders-api"},
        }
    )

    assert result.is_valid


def test_lesson_candidate_rejects_semantic_fact():
    result = validate_lesson_candidate(
        {
            "triggers": ["database timeout"],
            "instruction": "Postgres uses a firewall ingress rule.",
            "reason": "It is required for connectivity.",
        }
    )

    assert not result
    assert any("semantic fact" in error for error in result.errors)


def test_lesson_candidate_requires_when_do_because():
    result = validate_lesson_candidate(
        {
            "triggers": ["database timeout"],
            "instruction": "Inspect the database and service firewall rules first.",
            "reason": "This is a recurring connection failure mode.",
        }
    )

    assert result.valid


def test_working_state_rejects_hypothesis_in_known():
    result = validate_working_state_update(
        {
            "focus": "Database connectivity investigation",
            "status": "investigating",
            "known": ["The missing security-group rule might be the cause."],
            "hypotheses": [],
            "next_actions": ["Inspect the database firewall rules."],
        }
    )

    assert not result
    assert any("hypothetical" in error for error in result.errors)


def test_working_state_accepts_active_actionable_update():
    result = validate_working_state_update(
        {
            "focus": "Database connectivity investigation",
            "status": "investigating",
            "known": ["A connection timeout occurs on the first database query."],
            "hypotheses": ["The database firewall lacks application ingress."],
            "next_actions": ["Inspect the database firewall rules."],
        }
    )

    assert result.valid


def _dimensions_for_score(score: int) -> ImportanceDimensions:
    values = []
    for _ in range(5):
        value = min(3, score)
        values.append(value)
        score -= value
    return ImportanceDimensions(
        future_usefulness=values[0],
        cost_of_rediscovery=values[1],
        blast_radius=values[2],
        decision_significance=values[3],
        recurrence_value=values[4],
    )
