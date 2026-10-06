"""Structural tests for Project."""

import pytest
from pydantic import ValidationError

from src.models import Project, ProjectStatus


def test_project_accepts_valid_payload(now):
    project = Project(
        id="prj_01J00000000000000000000000",
        name="example-project",
        description="Main product repo",
        repo_path="/Users/me/code/example-project",
        obsidian_path="/Users/me/Obsidian/Example",
        status=ProjectStatus.ACTIVE,
        created_at=now,
        updated_at=now,
    )

    assert project.name == "example-project"
    assert project.status == ProjectStatus.ACTIVE


def test_project_defaults_status_to_active(now):
    project = Project(
        id="prj_01J00000000000000000000000",
        name="example-project",
        created_at=now,
        updated_at=now,
    )

    assert project.status == ProjectStatus.ACTIVE
    assert project.description is None
    assert project.repo_path is None


def test_project_accepts_status_as_string(now):
    project = Project(
        id="prj_01J00000000000000000000000",
        name="example-project",
        status="archived",
        created_at=now,
        updated_at=now,
    )

    assert project.status == ProjectStatus.ARCHIVED


def test_project_rejects_invalid_status(now):
    with pytest.raises(ValidationError) as exc_info:
        Project(
            id="prj_01J00000000000000000000000",
            name="example-project",
            status="deleted",
            created_at=now,
            updated_at=now,
        )

    assert "status" in str(exc_info.value)


def test_project_rejects_missing_name(now):
    with pytest.raises(ValidationError) as exc_info:
        Project(
            id="prj_01J00000000000000000000000",
            created_at=now,
            updated_at=now,
        )

    assert "name" in str(exc_info.value)
