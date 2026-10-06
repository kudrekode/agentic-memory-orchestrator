"""Contract tests for the constrained MCP tool surface."""

import asyncio
import json
from datetime import datetime, timezone

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from src.identifiers import new_prefixed_ulid
from src.mcp_server import create_mcp_server
from src.models import Project
from src.storage import SQLiteMemoryStore


def test_mcp_server_exposes_only_memory_boundary_tools(tmp_path):
    server = create_mcp_server(tmp_path / "memory.db")

    tools = asyncio.run(server.list_tools())

    assert {tool.name for tool in tools} == {
        "get_memory_context",
        "get_memory_status",
        "submit_memory_candidates",
        "sync_obsidian",
    }


def test_sync_obsidian_renders_the_project_vault(tmp_path, monkeypatch):
    monkeypatch.delenv("AGENT_MEMORY_VAULT", raising=False)
    database_path = tmp_path / "memory.db"
    vault = tmp_path / "vault"
    now = datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc)
    project = Project(
        id=new_prefixed_ulid("prj"),
        name="Example Project",
        obsidian_path=str(vault),
        created_at=now,
        updated_at=now,
    )
    store = SQLiteMemoryStore(database_path)
    store.migrate()
    store.save_project(project)
    server = create_mcp_server(database_path)

    result = asyncio.run(server.call_tool("sync_obsidian", {"project_id": project.id}))

    payload = json.loads(result.content[0].text)
    assert "Current State.md" in payload["written"]
    assert (vault / "Current State.md").is_file()


def test_sync_obsidian_requires_a_configured_path(tmp_path, monkeypatch):
    monkeypatch.delenv("AGENT_MEMORY_VAULT", raising=False)
    database_path = tmp_path / "memory.db"
    now = datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc)
    project = Project(
        id=new_prefixed_ulid("prj"),
        name="Example Project",
        created_at=now,
        updated_at=now,
    )
    store = SQLiteMemoryStore(database_path)
    store.migrate()
    store.save_project(project)
    server = create_mcp_server(database_path)

    with pytest.raises(ToolError, match="no Obsidian path configured"):
        asyncio.run(server.call_tool("sync_obsidian", {"project_id": project.id}))


def test_submit_memory_candidates_refreshes_a_configured_vault(tmp_path, monkeypatch):
    monkeypatch.delenv("AGENT_MEMORY_VAULT", raising=False)
    database_path = tmp_path / "memory.db"
    vault = tmp_path / "vault"
    now = datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc)
    project = Project(
        id=new_prefixed_ulid("prj"),
        name="Example Project",
        obsidian_path=str(vault),
        created_at=now,
        updated_at=now,
    )
    store = SQLiteMemoryStore(database_path)
    store.migrate()
    store.save_project(project)
    server = create_mcp_server(database_path)

    result = asyncio.run(
        server.call_tool(
            "submit_memory_candidates",
            {
                "bundle": {
                    "project_id": project.id,
                    "candidates": [
                        {
                            "proposed_type": "episode",
                            "content": {
                                "title": "Database connectivity incident",
                                "summary": "Services could not reach the database until ingress was corrected.",
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
                        }
                    ],
                }
            },
        )
    )

    payload = json.loads(result.content[0].text)
    assert payload["obsidian"]["synced"] is True
    note = (vault / "Current State.md").read_text()
    assert "Database connectivity incident" in note


def _saved_project(database_path) -> Project:
    now = datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc)
    project = Project(
        id=new_prefixed_ulid("prj"), name="Example Project", created_at=now, updated_at=now
    )
    store = SQLiteMemoryStore(database_path)
    store.migrate()
    store.save_project(project)
    return project


def test_tools_fall_back_to_the_default_project(tmp_path):
    database_path = tmp_path / "memory.db"
    project = _saved_project(database_path)
    server = create_mcp_server(database_path, default_project_id=project.id)

    result = asyncio.run(server.call_tool("get_memory_status", {}))

    assert json.loads(result.content[0].text)["project_id"] == project.id


def test_tools_require_a_project_when_no_default_is_configured(tmp_path):
    server = create_mcp_server(tmp_path / "memory.db")

    with pytest.raises(ToolError, match="AGENT_MEMORY_PROJECT_ID"):
        asyncio.run(server.call_tool("get_memory_status", {}))


def test_unknown_project_is_reported_as_a_tool_error(tmp_path):
    server = create_mcp_server(tmp_path / "memory.db")

    with pytest.raises(ToolError, match="project not found"):
        asyncio.run(
            server.call_tool(
                "get_memory_context", {"project_id": new_prefixed_ulid("prj")}
            )
        )


def test_submit_uses_default_project_and_configured_client(tmp_path, monkeypatch):
    monkeypatch.delenv("AGENT_MEMORY_VAULT", raising=False)
    database_path = tmp_path / "memory.db"
    project = _saved_project(database_path)
    server = create_mcp_server(
        database_path, default_project_id=project.id, client_name="manual"
    )

    result = asyncio.run(
        server.call_tool(
            "submit_memory_candidates",
            {
                "bundle": {
                    "candidates": [
                        {
                            "proposed_type": "semantic",
                            "content": {
                                "namespace": "convention.git",
                                "key": "branch_naming",
                                "statement": "Feature branches use the feature/ prefix.",
                            },
                            "rationale": "Team convention.",
                            "confidence": "confirmed",
                            "importance_dimensions": {
                                "future_usefulness": 2,
                                "cost_of_rediscovery": 1,
                                "blast_radius": 1,
                                "decision_significance": 1,
                                "recurrence_value": 2,
                            },
                        }
                    ]
                }
            },
        )
    )

    outcome = json.loads(result.content[0].text)["outcomes"][0]
    assert outcome["status"] == "created"
    stored = SQLiteMemoryStore(database_path).get_semantic_by_key(
        project.id, "convention.git", "branch_naming"
    )
    assert stored.source.value == "developer_explicit"
