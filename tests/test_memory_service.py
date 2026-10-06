"""Tests for candidate processing and safe recall services."""

from datetime import datetime, timezone

import pytest

from src.identifiers import new_prefixed_ulid
from src.memory_service import MemoryService
from src.models import (
    MemorySource,
    MemoryCandidateBundle,
    Project,
)
from src.storage import SQLiteMemoryStore


@pytest.fixture
def now() -> datetime:
    return datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def project(now) -> Project:
    return Project(
        id=new_prefixed_ulid("prj"),
        name="Example Project",
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def service(tmp_path, project) -> MemoryService:
    store = SQLiteMemoryStore(tmp_path / "memory.db")
    store.migrate()
    store.save_project(project)
    return MemoryService(store)


def test_process_bundle_creates_episode_and_semantic(service, project, now):
    result = service.process_bundle(
        MemoryCandidateBundle.model_validate(
            {
                "project_id": project.id,
                "submitted_by": "manual",
                "submitted_at": now,
                "candidates": [
                    {
                        "proposed_type": "episode",
                        "content": {
                            "title": "Database connectivity incident",
                            "summary": "Application services could not reach the database until ingress was corrected.",
                            "outcome": "resolved",
                        },
                        "rationale": "A meaningful production incident.",
                        "confidence": "high",
                        "importance_dimensions": {
                            "future_usefulness": 2,
                            "cost_of_rediscovery": 2,
                            "blast_radius": 1,
                            "decision_significance": 2,
                            "recurrence_value": 1,
                        },
                    },
                    {
                        "proposed_type": "semantic",
                        "content": {
                            "namespace": "architecture.database",
                            "key": "postgres.application_ingress",
                            "statement": "Services require database ingress on port 5432.",
                        },
                        "rationale": "A reusable infrastructure constraint.",
                        "confidence": "high",
                        "importance_dimensions": {
                            "future_usefulness": 2,
                            "cost_of_rediscovery": 2,
                            "blast_radius": 1,
                            "decision_significance": 2,
                            "recurrence_value": 1,
                        },
                    },
                ],
            }
        )
    )

    assert [outcome.status for outcome in result.outcomes] == ["created", "created"]
    assert all(outcome.memory_id for outcome in result.outcomes)
    episode = service.get_memory_context(project.id).recent_episodes[0]
    assert episode.title.startswith("Database")
    assert episode.source is MemorySource.DEVELOPER_EXPLICIT


def test_process_bundle_routes_same_semantic_key_to_conflict(service, project, now):
    bundle_data = {
        "project_id": project.id,
        "submitted_by": "cursor",
        "submitted_at": now,
        "candidates": [
            {
                "proposed_type": "semantic",
                "content": {
                    "namespace": "architecture.database",
                    "key": "postgres.application_ingress",
                    "statement": "Services require database ingress on port 5432.",
                },
                "rationale": "A reusable infrastructure constraint.",
                "confidence": "high",
                "importance_dimensions": {
                    "future_usefulness": 2,
                    "cost_of_rediscovery": 2,
                    "blast_radius": 1,
                    "decision_significance": 2,
                    "recurrence_value": 1,
                },
            }
        ],
    }
    service.process_bundle(MemoryCandidateBundle.model_validate(bundle_data))
    bundle_data["candidates"][0]["content"]["statement"] = (
        "Services require database ingress on port 5433."
    )

    result = service.process_bundle(MemoryCandidateBundle.model_validate(bundle_data))

    assert result.outcomes[0].status == "conflict"
    assert service.get_memory_context(project.id).active_semantics[0].statement.endswith(
        "5432."
    )


def test_process_bundle_rejects_invalid_candidate_without_writing(service, project, now):
    result = service.process_bundle(
        MemoryCandidateBundle.model_validate(
            {
                "project_id": project.id,
                "submitted_by": "manual",
                "submitted_at": now,
                "candidates": [
                    {
                        "proposed_type": "episode",
                        "content": {
                            "title": "Chatter",
                            "summary": "Done.",
                            "outcome": "informational",
                        },
                        "rationale": "Not worth retaining.",
                        "confidence": "low",
                        "importance_dimensions": {
                            "future_usefulness": 0,
                            "cost_of_rediscovery": 0,
                            "blast_radius": 0,
                            "decision_significance": 0,
                            "recurrence_value": 0,
                        },
                    }
                ],
            }
        )
    )

    assert result.outcomes[0].status == "rejected"
    assert service.get_memory_context(project.id).recent_episodes == []


def test_process_bundle_skips_obsidian_when_no_path_is_configured(
    service, project, now, monkeypatch
):
    monkeypatch.delenv("AGENT_MEMORY_VAULT", raising=False)

    result = service.process_bundle(
        MemoryCandidateBundle.model_validate(
            {
                "project_id": project.id,
                "submitted_by": "manual",
                "submitted_at": now,
                "candidates": [],
            }
        )
    )

    assert result.obsidian.synced is False
    assert result.obsidian.skipped_reason == "no Obsidian path configured"


def test_process_bundle_keeps_the_save_when_the_vault_path_is_invalid(
    now, tmp_path, monkeypatch
):
    monkeypatch.delenv("AGENT_MEMORY_VAULT", raising=False)
    vault_file = tmp_path / "not-a-vault"
    vault_file.write_text("file")
    project = Project(
        id=new_prefixed_ulid("prj"),
        name="Example Project",
        obsidian_path=str(vault_file),
        created_at=now,
        updated_at=now,
    )
    store = SQLiteMemoryStore(tmp_path / "memory.db")
    store.migrate()
    store.save_project(project)
    service = MemoryService(store)

    result = service.process_bundle(
        MemoryCandidateBundle.model_validate(
            {
                "project_id": project.id,
                "submitted_by": "manual",
                "submitted_at": now,
                "working_state_update": {
                    "proposed_type": "working_state_update",
                    "content": {
                        "focus": "Vault failure should not block the save.",
                        "status": "investigating",
                    },
                    "rationale": "Current active work.",
                    "confidence": "high",
                },
            }
        )
    )

    assert result.working_state_updated
    assert result.obsidian.synced is False
    assert result.obsidian.error
    assert service.get_memory_context(project.id).working_state.focus.startswith("Vault")


def test_process_bundle_replaces_working_state(service, project, now):
    result = service.process_bundle(
        MemoryCandidateBundle.model_validate(
            {
                "project_id": project.id,
                "submitted_by": "local-agent",
                "submitted_at": now,
                "working_state_update": {
                    "proposed_type": "working_state_update",
                    "content": {
                        "focus": "Database connectivity investigation",
                        "status": "investigating",
                        "known": ["A connection timeout occurs on the first database query."],
                        "hypotheses": ["Database ingress is missing."],
                        "next_actions": ["Inspect the database firewall rules."],
                    },
                    "rationale": "Current active work.",
                    "confidence": "high",
                },
            }
        )
    )

    assert result.working_state_updated
    assert service.get_memory_context(project.id).working_state.focus.startswith("Database")
