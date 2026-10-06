"""Tests for the project setup command line."""

import re

from src import config
from src.cli import main
from src.storage import SQLiteMemoryStore


def test_init_creates_database_and_project(tmp_path, capsys):
    database = tmp_path / "nested" / "memory.db"

    exit_code = main(
        [
            "--db",
            str(database),
            "init",
            "--name",
            "Example Project",
            "--obsidian-path",
            str(tmp_path / "vault"),
        ]
    )

    assert exit_code == 0
    output = capsys.readouterr().out
    project_id = re.search(r"prj_[0-9A-Z]{26}", output).group(0)
    assert f'"{config.PROJECT_ENV}": "{project_id}"' in output
    project = SQLiteMemoryStore(database).get_project(project_id)
    assert project.name == "Example Project"
    assert project.obsidian_path == str((tmp_path / "vault").resolve())


def test_projects_lists_every_project(tmp_path, capsys):
    database = tmp_path / "memory.db"
    main(["--db", str(database), "init", "--name", "First"])
    main(["--db", str(database), "init", "--name", "Second"])
    capsys.readouterr()

    main(["--db", str(database), "projects"])

    lines = capsys.readouterr().out.strip().splitlines()
    assert [line.split("  ")[1] for line in lines] == ["First", "Second"]


def test_projects_explains_how_to_start_when_empty(tmp_path, capsys):
    main(["--db", str(tmp_path / "memory.db"), "projects"])

    assert "agent-memory init" in capsys.readouterr().out


def test_database_path_comes_from_the_environment(tmp_path, monkeypatch, capsys):
    database = tmp_path / "from-env.db"
    monkeypatch.setenv(config.DB_ENV, str(database))

    main(["init", "--name", "Env Project"])

    assert database.is_file()
    assert "Env Project" in capsys.readouterr().out
