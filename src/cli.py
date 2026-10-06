"""Command-line setup for a local agent memory database."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path

from src import config
from src.identifiers import new_prefixed_ulid
from src.models import Project
from src.storage import SQLiteMemoryStore


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="agent-memory", description="Manage a local agent memory database."
    )
    parser.add_argument(
        "--db",
        default=None,
        help=f"SQLite path (default: ${config.DB_ENV} or {config.DEFAULT_DB_PATH})",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    init = commands.add_parser("init", help="create the database and a project")
    init.add_argument("--name", required=True, help="human-readable project name")
    init.add_argument("--description", default=None)
    init.add_argument("--repo-path", default=None, help="repository this memory describes")
    init.add_argument(
        "--obsidian-path", default=None, help="vault directory for generated notes"
    )

    commands.add_parser("projects", help="list projects in the database")

    args = parser.parse_args(argv)
    database = Path(args.db or config.database_path()).expanduser()
    store = SQLiteMemoryStore(database)
    store.migrate()

    if args.command == "init":
        return _init(store, database, args)
    return _list(store)


def _init(store: SQLiteMemoryStore, database: Path, args: argparse.Namespace) -> int:
    now = datetime.now(timezone.utc)
    project = Project(
        id=new_prefixed_ulid("prj"),
        name=args.name,
        description=args.description,
        repo_path=_absolute(args.repo_path),
        obsidian_path=_absolute(args.obsidian_path),
        created_at=now,
        updated_at=now,
    )
    store.save_project(project)
    print(f"Created project {project.name}: {project.id}")
    print(f"Database: {database.resolve()}")
    print()
    print("Add these to the env block of your MCP server config:")
    print(f'  "{config.DB_ENV}": "{database.resolve()}",')
    print(f'  "{config.PROJECT_ENV}": "{project.id}"')
    return 0


def _list(store: SQLiteMemoryStore) -> int:
    projects = store.list_projects()
    if not projects:
        print("No projects. Run: agent-memory init --name <name>")
        return 0
    for project in projects:
        print(f"{project.id}  {project.name}  ({project.status.value})")
    return 0


def _absolute(path: str | None) -> str | None:
    if path is None:
        return None
    return str(Path(path).expanduser().resolve())


if __name__ == "__main__":
    sys.exit(main())
