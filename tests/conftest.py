"""Shared fixtures for structural model tests."""

from datetime import datetime, timezone

import pytest

from src.models import ImportanceDimensions, MemoryScope


@pytest.fixture
def now() -> datetime:
    return datetime(2026, 10, 5, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def project_id() -> str:
    return "prj_01J00000000000000000000000"


@pytest.fixture
def valid_dims() -> ImportanceDimensions:
    return ImportanceDimensions(
        future_usefulness=2,
        cost_of_rediscovery=2,
        blast_radius=1,
        decision_significance=2,
        recurrence_value=1,
    )


@pytest.fixture
def valid_scope() -> MemoryScope:
    return MemoryScope(environment="production", service="orders-api")
