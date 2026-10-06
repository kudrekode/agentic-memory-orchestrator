from datetime import datetime, timezone

from pydantic import AwareDatetime, BaseModel, Field, field_validator, model_validator

from src.identifiers import require_prefixed_ulid
from src.models.common import (
    ImportanceDimensions,
    MemoryScope,
    calculate_importance,
)
from src.models.enums import (
    ConfidenceLevel,
    ConsolidationStatus,
    CreatedBy,
    EpisodeOutcome,
    ImportanceLevel,
    LessonCategory,
    LessonPriority,
    LessonStatus,
    MemoryObjectType,
    MemoryRelationship,
    MemorySource,
    ProjectStatus,
    ProposedMemoryType,
    SemanticChangeType,
    SemanticStatus,
    WorkingStateStatus,
)


class Project(BaseModel):
    """
    Isolation boundary for an independent engineering context.

    Stack/architecture facts belong in semantic memory, not here.
    """

    id: str
    name: str
    description: str | None = None
    repo_path: str | None = None
    obsidian_path: str | None = None
    status: ProjectStatus = ProjectStatus.ACTIVE
    created_at: AwareDatetime
    updated_at: AwareDatetime

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        return require_prefixed_ulid(value, "prj")

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return _non_blank(value, "name")


class WorkingState(BaseModel):
    """
    Mutable, temporary state of active work for a project.

    A project should generally have one active working-state record.
    """

    project_id: str
    focus: str | None = None
    status: WorkingStateStatus = WorkingStateStatus.IDLE
    known: list[str] = Field(default_factory=list)
    unknown: list[str] = Field(default_factory=list)
    hypotheses: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)
    active_files: list[str] = Field(default_factory=list)
    active_services: list[str] = Field(default_factory=list)
    updated_at: AwareDatetime

    @field_validator("project_id")
    @classmethod
    def validate_project_id(cls, value: str) -> str:
        return require_prefixed_ulid(value, "prj")


class Episode(BaseModel):
    """One meaningful engineering event."""

    id: str
    project_id: str
    title: str
    summary: str
    details: list[str] = Field(default_factory=list)
    outcome: EpisodeOutcome
    entities: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    scope: MemoryScope = Field(default_factory=MemoryScope)
    services: list[str] = Field(default_factory=list)
    source: MemorySource
    confidence: ConfidenceLevel
    importance_dimensions: ImportanceDimensions
    importance: ImportanceLevel
    occurred_at: AwareDatetime
    created_at: AwareDatetime
    consolidation_status: ConsolidationStatus = ConsolidationStatus.PENDING

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        return require_prefixed_ulid(value, "epi")

    @field_validator("project_id")
    @classmethod
    def validate_project_id(cls, value: str) -> str:
        return require_prefixed_ulid(value, "prj")

    @model_validator(mode="after")
    def validate_importance(self) -> "Episode":
        _require_calculated_importance(self.importance_dimensions, self.importance)
        return self


class SemanticMemory(BaseModel):
    """
    Durable project knowledge: what we currently believe to be true.

    Meaning changes go through SemanticRevision, not silent overwrite.
    """

    id: str
    project_id: str
    namespace: str
    key: str
    statement: str
    scope: MemoryScope = Field(default_factory=MemoryScope)
    source: MemorySource
    status: SemanticStatus = SemanticStatus.ACTIVE
    confidence: ConfidenceLevel
    importance_dimensions: ImportanceDimensions
    importance: ImportanceLevel
    current_revision: int = 1
    created_at: AwareDatetime
    updated_at: AwareDatetime

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        return require_prefixed_ulid(value, "sem")

    @field_validator("project_id")
    @classmethod
    def validate_project_id(cls, value: str) -> str:
        return require_prefixed_ulid(value, "prj")

    @field_validator("namespace", "key", "statement")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        return _non_blank(value, "semantic field")

    @model_validator(mode="after")
    def validate_importance(self) -> "SemanticMemory":
        _require_calculated_importance(self.importance_dimensions, self.importance)
        return self


class SemanticRevision(BaseModel):
    """
    Provenance record for a change to semantic memory.

    Semantic memory should not be destructively overwritten when meaning changes.
    """

    id: str
    semantic_memory_id: str
    revision_number: int
    previous_statement: str | None
    new_statement: str
    change_type: SemanticChangeType
    reason: str
    confidence: ConfidenceLevel
    created_by: CreatedBy
    created_at: AwareDatetime

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        return require_prefixed_ulid(value, "rev")

    @field_validator("semantic_memory_id")
    @classmethod
    def validate_semantic_memory_id(cls, value: str) -> str:
        return require_prefixed_ulid(value, "sem")


class Lesson(BaseModel):
    """
    Actionable behaviour for similar future situations.

    Shape: WHEN (triggers) / DO (instruction) / BECAUSE (reason).
    """

    id: str
    project_id: str
    title: str
    triggers: list[str]
    instruction: str
    reason: str
    category: LessonCategory
    scope: MemoryScope = Field(default_factory=MemoryScope)
    source: MemorySource
    priority: LessonPriority
    confidence: ConfidenceLevel
    status: LessonStatus = LessonStatus.ACTIVE
    created_at: AwareDatetime
    updated_at: AwareDatetime

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        return require_prefixed_ulid(value, "les")

    @field_validator("project_id")
    @classmethod
    def validate_project_id(cls, value: str) -> str:
        return require_prefixed_ulid(value, "prj")


class MemoryLink(BaseModel):
    """Relationship / provenance edge between memory objects."""

    id: str
    source_type: MemoryObjectType
    source_id: str
    target_type: MemoryObjectType
    target_id: str
    relationship: MemoryRelationship
    created_at: AwareDatetime

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        return require_prefixed_ulid(value, "lnk")

    @model_validator(mode="after")
    def validate_entity_id_prefixes(self) -> "MemoryLink":
        _require_entity_id(self.source_id, self.source_type)
        _require_entity_id(self.target_id, self.target_type)
        return self


class MemoryCandidate(BaseModel):
    """
    Proposed memory from an agent.

    Validated by the memory service before becoming a stored memory object.
    """

    proposed_type: ProposedMemoryType
    content: dict
    rationale: str
    confidence: ConfidenceLevel
    importance_dimensions: ImportanceDimensions | None = None
    related_memory_queries: list[str] = Field(default_factory=list)


class MemoryCandidateBundle(BaseModel):
    """A project-scoped checkpoint submitted through the application boundary."""

    project_id: str
    session_id: str | None = None
    session_summary: str | None = None
    candidates: list[MemoryCandidate] = Field(default_factory=list)
    working_state_update: MemoryCandidate | None = None
    submitted_by: str
    """Client that submitted the bundle. "manual" marks developer-explicit memory."""
    submitted_at: AwareDatetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @field_validator("project_id")
    @classmethod
    def validate_project_id(cls, value: str) -> str:
        return require_prefixed_ulid(value, "prj")

    @field_validator("submitted_by")
    @classmethod
    def validate_submitted_by(cls, value: str) -> str:
        return _non_blank(value, "submitted_by")

    @model_validator(mode="after")
    def validate_working_state_candidate(self) -> "MemoryCandidateBundle":
        if (
            self.working_state_update is not None
            and self.working_state_update.proposed_type
            is not ProposedMemoryType.WORKING_STATE_UPDATE
        ):
            raise ValueError(
                "working_state_update must have proposed_type working_state_update"
            )
        if any(
            candidate.proposed_type is ProposedMemoryType.WORKING_STATE_UPDATE
            for candidate in self.candidates
        ):
            raise ValueError(
                "working_state_update must be supplied separately from candidates"
            )
        return self


def _non_blank(value: str, field_name: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError(f"{field_name} cannot be blank")
    return value


def _require_calculated_importance(
    dimensions: ImportanceDimensions, importance: ImportanceLevel
) -> None:
    expected = calculate_importance(dimensions)
    if importance is not expected:
        raise ValueError(
            "importance must match the calculated value from importance_dimensions"
        )


def _require_entity_id(value: str, entity_type: MemoryObjectType) -> None:
    prefixes = {
        MemoryObjectType.EPISODE: "epi",
        MemoryObjectType.SEMANTIC: "sem",
        MemoryObjectType.SEMANTIC_REVISION: "rev",
        MemoryObjectType.LESSON: "les",
    }
    require_prefixed_ulid(value, prefixes[entity_type])
