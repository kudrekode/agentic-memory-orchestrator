"""Environment-driven settings shared by the MCP server, CLI, and vault sync."""

from __future__ import annotations

import os

DB_ENV = "AGENT_MEMORY_DB"
PROJECT_ENV = "AGENT_MEMORY_PROJECT_ID"
VAULT_ENV = "AGENT_MEMORY_VAULT"
CLIENT_ENV = "AGENT_MEMORY_CLIENT"

DEFAULT_DB_PATH = "data/dev/memory.db"
DEFAULT_CLIENT = "mcp"


def database_path() -> str:
    return _env(DB_ENV) or DEFAULT_DB_PATH


def default_project_id() -> str | None:
    return _env(PROJECT_ENV)


def vault_path() -> str | None:
    return _env(VAULT_ENV)


def client_name() -> str:
    return _env(CLIENT_ENV) or DEFAULT_CLIENT


def _env(name: str) -> str | None:
    value = os.environ.get(name)
    if value is None or not value.strip():
        return None
    return value.strip()
