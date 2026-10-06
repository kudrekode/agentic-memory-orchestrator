"""Application service connecting candidate validation, transformation, and storage."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

from src import config
from src.identifiers import new_prefixed_ulid
from src.models import (
    Episode,
    Lesson,
    MemoryCandidate,
    MemoryCandidateBundle,
    MemoryLink,
    MemoryObjectType,
    MemoryRelationship,
    MemorySource,
    SemanticMemory,
    WorkingState,
)
from src.obsidian_sync import ObsidianSyncError, ObsidianSyncResult, sync_project
from src.storage import MemoryNotFoundError, SQLiteMemoryStore
from src.transformation import CandidateTransformationError, materialize_candidate
from src.validation import validate_working_state_update


class CandidateOutcome(BaseModel):
    """The deterministic outcome for a single submitted candidate."""

    index: int
    status: Literal[
        "created", "duplicate", "linked", "conflict", "rejected", "ignored"
    ]
    memory_id: str | None = None
    reason: str | None = None


class ObsidianSyncStatus(BaseModel):
    """Whether a save refreshed the generated Obsidian vault."""

    synced: bool
    vault_path: str | None = None
    written: list[str] = Field(default_factory=list)
    removed: list[str] = Field(default_factory=list)
    skipped_reason: str | None = None
    error: str | None = None


class MemoryProcessingResult(BaseModel):
    """Inspectable result for one submitted memory checkpoint."""

    outcomes: list[CandidateOutcome] = Field(default_factory=list)
    working_state_updated: bool = False
    obsidian: ObsidianSyncStatus


class MemoryContext(BaseModel):
    """Read-only project context suitable for an agent's next step."""

    working_state: WorkingState | None = None
    active_semantics: list[SemanticMemory] = Field(default_factory=list)
    active_lessons: list[Lesson] = Field(default_factory=list)
    recent_episodes: list[Episode] = Field(default_factory=list)


class MemoryService:
    """Safe candidate-processing and recall boundary over a local store."""

    def __init__(self, store: SQLiteMemoryStore):
        self.store = store

    def process_bundle(
        self, bundle: MemoryCandidateBundle, *, now: datetime | None = None
    ) -> MemoryProcessingResult:
        """Process each candidate independently and return all routing outcomes."""

        self.store.get_project(bundle.project_id)
        now = now or datetime.now(timezone.utc)
        source = (
            MemorySource.DEVELOPER_EXPLICIT
            if bundle.submitted_by == "manual"
            else MemorySource.AGENT_INFERRED
        )
        outcomes: list[CandidateOutcome] = []
        supporting_episode_ids: list[str] = []
        for index, candidate in enumerate(bundle.candidates):
            outcome = self._process_candidate(
                candidate,
                bundle.project_id,
                index,
                now,
                source,
                supporting_episode_ids,
            )
            outcomes.append(outcome)
            if outcome.status == "created" and outcome.memory_id and candidate.proposed_type.value == "episode":
                supporting_episode_ids.append(outcome.memory_id)
        working_state_updated = False
        if bundle.working_state_update is not None:
            self._apply_working_state(bundle.working_state_update, bundle.project_id, now)
            working_state_updated = True
        return MemoryProcessingResult(
            outcomes=outcomes,
            working_state_updated=working_state_updated,
            obsidian=self._refresh_vault(bundle.project_id),
        )

    def sync_obsidian(self, project_id: str) -> ObsidianSyncResult:
        """Replace the project's generated vault notes from current SQLite memory."""

        self.store.get_project(project_id)
        return sync_project(self.store, project_id)

    def get_memory_context(
        self, project_id: str, *, recent_episode_limit: int = 10
    ) -> MemoryContext:
        """Read the current project-scoped context without mutating memory."""

        self.store.get_project(project_id)
        try:
            working_state = self.store.get_working_state(project_id)
        except MemoryNotFoundError:
            working_state = None
        return MemoryContext(
            working_state=working_state,
            active_semantics=self.store.list_active_semantic_memories(project_id),
            active_lessons=self.store.list_active_lessons(project_id),
            recent_episodes=self.store.list_recent_episodes(
                project_id, recent_episode_limit
            ),
        )

    def _process_candidate(
        self,
        candidate: MemoryCandidate,
        project_id: str,
        index: int,
        now: datetime,
        source: MemorySource,
        supporting_episode_ids: list[str],
    ) -> CandidateOutcome:
        if candidate.proposed_type.value == "ignore":
            return CandidateOutcome(index=index, status="ignored", reason=candidate.rationale)
        try:
            record = materialize_candidate(
                candidate,
                project_id=project_id,
                now=now,
                source=source,
            )
        except CandidateTransformationError as error:
            return CandidateOutcome(index=index, status="rejected", reason=str(error))

        if isinstance(record, SemanticMemory):
            try:
                existing = self.store.get_semantic_by_key(
                    project_id, record.namespace, record.key
                )
            except MemoryNotFoundError:
                self.store.save_semantic_memory(record)
                return CandidateOutcome(
                    index=index, status="created", memory_id=record.id
                )
            if existing.statement == record.statement:
                for episode_id in supporting_episode_ids:
                    self.store.save_memory_link(
                        MemoryLink(
                            id=new_prefixed_ulid("lnk"),
                            source_type=MemoryObjectType.EPISODE,
                            source_id=episode_id,
                            target_type=MemoryObjectType.SEMANTIC,
                            target_id=existing.id,
                            relationship=MemoryRelationship.SUPPORTS,
                            created_at=now,
                        )
                    )
                return CandidateOutcome(
                    index=index,
                    status="linked" if supporting_episode_ids else "duplicate",
                    memory_id=existing.id,
                    reason="semantic memory with the same statement already exists",
                )
            return CandidateOutcome(
                index=index,
                status="conflict",
                memory_id=existing.id,
                reason="semantic key exists with a different statement",
            )

        self.store.save_records([record])
        return CandidateOutcome(index=index, status="created", memory_id=record.id)

    def _apply_working_state(
        self, candidate: MemoryCandidate, project_id: str, now: datetime
    ) -> None:
        validation = validate_working_state_update(candidate)
        if not validation:
            raise ValueError("; ".join(validation.errors))
        try:
            current = self.store.get_working_state(project_id).model_dump()
        except MemoryNotFoundError:
            current = {
                "project_id": project_id,
                "known": [],
                "unknown": [],
                "hypotheses": [],
                "blockers": [],
                "next_actions": [],
                "active_files": [],
                "active_services": [],
            }
        state = WorkingState.model_validate(
            {
                **current,
                **candidate.content,
                "project_id": project_id,
                "updated_at": now,
            }
        )
        self.store.replace_working_state(state)

    def _refresh_vault(self, project_id: str) -> ObsidianSyncStatus:
        project = self.store.get_project(project_id)
        configured = project.obsidian_path or config.vault_path()
        if configured is None or not str(configured).strip():
            return ObsidianSyncStatus(
                synced=False, skipped_reason="no Obsidian path configured"
            )
        try:
            result = sync_project(self.store, project_id)
        except (ObsidianSyncError, OSError) as error:
            return ObsidianSyncStatus(synced=False, error=str(error))
        return ObsidianSyncStatus(
            synced=True,
            vault_path=result.vault_path,
            written=result.written,
            removed=result.removed,
        )
