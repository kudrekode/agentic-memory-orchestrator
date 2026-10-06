"""Structural tests for WorkingState."""

import pytest
from pydantic import ValidationError

from src.models import WorkingState, WorkingStateStatus


def test_working_state_accepts_valid_payload(project_id, now):
    state = WorkingState(
        project_id=project_id,
        focus="Database connectivity",
        status=WorkingStateStatus.INVESTIGATING,
        known=["Connection timeout on first query"],
        unknown=["Whether SG allows ingress on 5432"],
        hypotheses=["Missing SG rule"],
        blockers=["Need prod access"],
        next_actions=["Inspect database firewall"],
        active_files=["infra/security-groups.ts"],
        active_services=["orders-api"],
        updated_at=now,
    )

    assert state.status == WorkingStateStatus.INVESTIGATING
    assert state.next_actions == ["Inspect database firewall"]


def test_working_state_defaults(project_id, now):
    state = WorkingState(project_id=project_id, updated_at=now)

    assert state.status == WorkingStateStatus.IDLE
    assert state.focus is None
    assert state.known == []
    assert state.unknown == []
    assert state.hypotheses == []
    assert state.blockers == []
    assert state.next_actions == []
    assert state.active_files == []
    assert state.active_services == []


def test_working_state_rejects_invalid_status(project_id, now):
    with pytest.raises(ValidationError) as exc_info:
        WorkingState(
            project_id=project_id,
            status="done",
            updated_at=now,
        )

    assert "status" in str(exc_info.value)


def test_working_state_rejects_missing_project_id(now):
    with pytest.raises(ValidationError) as exc_info:
        WorkingState(updated_at=now)

    assert "project_id" in str(exc_info.value)


def test_working_state_rejects_non_list_known(project_id, now):
    with pytest.raises(ValidationError) as exc_info:
        WorkingState(
            project_id=project_id,
            known="not a list",
            updated_at=now,
        )

    assert "known" in str(exc_info.value)
