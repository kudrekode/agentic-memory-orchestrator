"""
Structural tests for shared types in src.models.common.

Pattern to copy for other models:
1. one happy-path construction test
2. a few ValidationError cases for bad shape / bounds / types
"""

import pytest
from pydantic import ValidationError

from src.models import ImportanceDimensions, MemoryScope


def test_memory_scope_accepts_partial_fields():
    scope = MemoryScope(environment="production", service="orders-api")

    assert scope.environment == "production"
    assert scope.service == "orders-api"
    assert scope.repo is None
    assert scope.component is None


def test_memory_scope_defaults_to_all_none():
    scope = MemoryScope()

    assert scope.model_dump() == {
        "environment": None,
        "service": None,
        "repo": None,
        "component": None,
    }


def test_importance_dimensions_accepts_valid_scores(valid_dims):
    assert valid_dims.future_usefulness == 2
    assert valid_dims.recurrence_value == 1


def test_importance_dimensions_rejects_above_max():
    with pytest.raises(ValidationError) as exc_info:
        ImportanceDimensions(
            future_usefulness=4,
            cost_of_rediscovery=0,
            blast_radius=0,
            decision_significance=0,
            recurrence_value=0,
        )

    assert "future_usefulness" in str(exc_info.value)


def test_importance_dimensions_rejects_below_min():
    with pytest.raises(ValidationError) as exc_info:
        ImportanceDimensions(
            future_usefulness=0,
            cost_of_rediscovery=-1,
            blast_radius=0,
            decision_significance=0,
            recurrence_value=0,
        )

    assert "cost_of_rediscovery" in str(exc_info.value)


def test_importance_dimensions_rejects_missing_field():
    with pytest.raises(ValidationError) as exc_info:
        ImportanceDimensions(
            future_usefulness=1,
            cost_of_rediscovery=1,
            blast_radius=1,
            decision_significance=1,
            # recurrence_value missing
        )

    assert "recurrence_value" in str(exc_info.value)
