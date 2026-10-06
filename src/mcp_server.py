"""Stdio MCP interface for the constrained local agent memory service."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from src import config
from src.memory_service import MemoryService
from src.models import MemoryCandidateBundle
from src.obsidian_sync import ObsidianSyncError
from src.storage import MemoryNotFoundError, SQLiteMemoryStore

SERVER_NAME = "Agent Memory"


def create_mcp_server(
    database_path: str | Path,
    *,
    default_project_id: str | None = None,
    client_name: str = config.DEFAULT_CLIENT,
) -> MCPServer:
    """Create an MCP server backed by one initialized local SQLite database.

    ``default_project_id`` is used whenever a tool call omits ``project_id``.
    """

    store = SQLiteMemoryStore(database_path)
    store.migrate()
    service = MemoryService(store)
    server = MCPServer(
        SERVER_NAME,
        instructions=(
            "Use this memory server only through these constrained tools. Submit "
            "candidates, not stored records or SQL. Read the returned decision "
            "result before assuming any memory was persisted. A successful submit "
            "refreshes the Obsidian vault when a path is configured; sync_obsidian "
            "refreshes it on demand. SQLite remains the source of truth. "
            "project_id may be omitted when the server has a default project."
        ),
    )

    def resolve_project(project_id: str | None) -> str:
        resolved = project_id or default_project_id
        if not resolved:
            raise ToolError(
                f"project_id is required: pass it or set {config.PROJECT_ENV}"
            )
        return resolved

    @server.tool()
    def get_memory_context(
        project_id: str | None = None, recent_episode_limit: int = 10
    ) -> dict:
        """Return project-scoped working state, active knowledge, lessons, and episodes."""

        try:
            context = service.get_memory_context(
                resolve_project(project_id), recent_episode_limit=recent_episode_limit
            )
        except MemoryNotFoundError as error:
            raise ToolError(str(error)) from error
        return context.model_dump(mode="json")

    @server.tool()
    def get_memory_status(project_id: str | None = None) -> dict:
        """Return compact counts for the current project memory context."""

        resolved = resolve_project(project_id)
        try:
            context = service.get_memory_context(resolved)
        except MemoryNotFoundError as error:
            raise ToolError(str(error)) from error
        return {
            "project_id": resolved,
            "has_working_state": context.working_state is not None,
            "active_semantic_count": len(context.active_semantics),
            "active_lesson_count": len(context.active_lessons),
            "recent_episode_count": len(context.recent_episodes),
        }

    @server.tool()
    def submit_memory_candidates(bundle: dict[str, Any]) -> dict:
        """Validate, route, and persist a project-scoped bundle of memory candidates."""

        submitted_bundle = MemoryCandidateBundle.model_validate(
            {
                **bundle,
                "project_id": resolve_project(bundle.get("project_id")),
                "submitted_by": client_name,
                "submitted_at": datetime.now(timezone.utc),
            }
        )
        try:
            result = service.process_bundle(submitted_bundle)
        except MemoryNotFoundError as error:
            raise ToolError(str(error)) from error
        return result.model_dump(mode="json")

    @server.tool()
    def sync_obsidian(project_id: str | None = None) -> dict:
        """Replace one project's generated Obsidian notes from current SQLite memory."""

        try:
            result = service.sync_obsidian(resolve_project(project_id))
        except MemoryNotFoundError as error:
            raise ToolError(str(error)) from error
        except ObsidianSyncError as error:
            raise ToolError(str(error)) from error
        return result.model_dump(mode="json")

    return server


def main() -> None:
    """Run the memory server over stdio for an MCP host."""

    create_mcp_server(
        config.database_path(),
        default_project_id=config.default_project_id(),
        client_name=config.client_name(),
    ).run(transport="stdio")


if __name__ == "__main__":
    main()
