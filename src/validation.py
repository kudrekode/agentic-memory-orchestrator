"""Deterministic business validation for proposed memory candidates.

These checks deliberately validate candidate shape and obvious category mistakes.
They do not attempt to replace the model's contextual judgment or repository
lookups, which happen later in the memory pipeline.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from src.models import (
    EpisodeOutcome,
    ImportanceDimensions,
    ImportanceLevel,
    MemoryCandidate,
    MemoryScope,
    ProposedMemoryType,
    WorkingStateStatus,
)
from src.models.common import calculate_importance as _calculate_importance

_IDENTIFIER = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")
_TEMPORAL_EVENT = re.compile(
    r"\b(today|yesterday|this morning|deployed|deployment|incident|"
    r"investigat(?:ed|ion)|failed|resolved)\b",
    re.IGNORECASE,
)
_ENVIRONMENT = re.compile(
    r"\b(production|prod|staging|stage|development|dev|local)\b",
    re.IGNORECASE,
)
_HYPOTHETICAL = re.compile(
    r"\b(maybe|might|possibly|suspect(?:ed)?|hypothesis|likely)\b",
    re.IGNORECASE,
)
_ACTION = re.compile(
    r"^(add|check|confirm|create|disable|enable|inspect|run|test|use|"
    r"verify|update|review|avoid|prefer|ensure|set|remove|restart|"
    r"deploy|investigate|compare|open|read|write|fix)\b",
    re.IGNORECASE,
)
_FACT_STATEMENT = re.compile(
    r"^(?:\S+\s+)?(is|are|was|were|has|have|uses|requires|supports|"
    r"contains|provides|runs)\b",
    re.IGNORECASE,
)
_RAW_TRANSCRIPT = re.compile(r"^\s*(user|assistant|developer|tool)\s*:", re.IGNORECASE)


@dataclass(frozen=True)
class ValidationResult:
    """The outcome of deterministic candidate validation."""

    errors: tuple[str, ...] = ()

    @property
    def valid(self) -> bool:
        return not self.errors

    @property
    def is_valid(self) -> bool:
        """Alias for callers that prefer an explicit predicate name."""
        return self.valid

    def __bool__(self) -> bool:
        return self.valid


def calculate_importance(dimensions: ImportanceDimensions | Mapping[str, int]) -> ImportanceLevel:
    """Map the five validated rubric dimensions to a deterministic category."""

    if not isinstance(dimensions, ImportanceDimensions):
        dimensions = ImportanceDimensions.model_validate(dimensions)

    return _calculate_importance(dimensions)


def validate_episode_candidate(
    candidate: MemoryCandidate | Mapping[str, Any],
) -> ValidationResult:
    """Check that a proposed Episode is one coherent, meaningful event."""

    content, errors = _content_for(candidate, ProposedMemoryType.EPISODE)
    title = _text(content, "title", errors)
    summary = _text(content, "summary", errors, minimum_length=20)
    outcome = content.get("outcome")

    if title and len(title) < 3:
        errors.append("title must contain at least 3 characters")
    if summary and _RAW_TRANSCRIPT.match(summary):
        errors.append("summary must be a summary, not raw transcript content")
    if summary and _is_chatter(summary):
        errors.append("summary appears to be routine chatter rather than an event")

    parsed_outcome = _parse_enum(outcome, EpisodeOutcome, "outcome", errors)
    if parsed_outcome is EpisodeOutcome.RESOLVED and summary and _HYPOTHETICAL.search(summary):
        errors.append("resolved outcome cannot be described only as a hypothesis")
    if parsed_outcome is EpisodeOutcome.UNRESOLVED and summary and re.search(
        r"\b(fixed|resolved|completed)\b", summary, re.IGNORECASE
    ):
        errors.append("unresolved outcome conflicts with the summary")
    if title and summary and _appears_multiple_events(title, summary):
        errors.append("candidate appears to combine multiple unrelated events")

    return ValidationResult(tuple(errors))


def validate_semantic_candidate(
    candidate: MemoryCandidate | Mapping[str, Any],
) -> ValidationResult:
    """Check that a proposed Semantic memory is a scoped, reusable fact."""

    content, errors = _content_for(candidate, ProposedMemoryType.SEMANTIC)
    namespace = _text(content, "namespace", errors)
    key = _text(content, "key", errors)
    statement = _text(content, "statement", errors, minimum_length=10)

    if namespace and not _IDENTIFIER.fullmatch(namespace):
        errors.append("namespace must be a lowercase dotted identifier")
    if key and not _IDENTIFIER.fullmatch(key):
        errors.append("key must be a lowercase identifier")
    if statement and _TEMPORAL_EVENT.search(statement):
        errors.append("statement describes an event; store reusable knowledge instead")

    if statement and _ENVIRONMENT.search(statement) and not _has_scope(content.get("scope")):
        errors.append("scope is required for environment-specific knowledge")
    return ValidationResult(tuple(errors))


def validate_lesson_candidate(
    candidate: MemoryCandidate | Mapping[str, Any],
) -> ValidationResult:
    """Check that a Lesson follows the WHEN / DO / BECAUSE structure."""

    content, errors = _content_for(candidate, ProposedMemoryType.LESSON)
    triggers = content.get("triggers")
    instruction = _text(content, "instruction", errors, minimum_length=5)
    _text(content, "reason", errors, minimum_length=5)

    if not isinstance(triggers, list) or not any(
        isinstance(trigger, str) and trigger.strip() for trigger in triggers or []
    ):
        errors.append("triggers must contain at least one useful condition")
    elif any(not isinstance(trigger, str) or not trigger.strip() for trigger in triggers):
        errors.append("triggers cannot contain blank values")

    if instruction and not _ACTION.match(instruction):
        if _FACT_STATEMENT.match(instruction):
            errors.append("instruction is a semantic fact, not an action")
        else:
            errors.append("instruction must start with an actionable verb")
    return ValidationResult(tuple(errors))


def validate_working_state_update(
    candidate: MemoryCandidate | Mapping[str, Any],
) -> ValidationResult:
    """Check that a working-state update captures current, actionable work."""

    content, errors = _content_for(candidate, ProposedMemoryType.WORKING_STATE_UPDATE)
    _text(content, "focus", errors, minimum_length=3)
    status = _parse_enum(content.get("status"), WorkingStateStatus, "status", errors)
    if status is WorkingStateStatus.IDLE:
        errors.append("working-state updates must describe active work, not idle state")

    known = _string_list(content, "known", errors)
    hypotheses = _string_list(content, "hypotheses", errors)
    if set(item.casefold() for item in known) & set(item.casefold() for item in hypotheses):
        errors.append("hypotheses must not also appear in known facts")
    if any(_HYPOTHETICAL.search(item) for item in known):
        errors.append("known facts must not contain hypothetical language")

    for action in _string_list(content, "next_actions", errors):
        if not _ACTION.match(action):
            errors.append("next_actions must start with an actionable verb")
            break
    return ValidationResult(tuple(errors))


def _content_for(
    candidate: MemoryCandidate | Mapping[str, Any], expected_type: ProposedMemoryType
) -> tuple[Mapping[str, Any], list[str]]:
    errors: list[str] = []
    if isinstance(candidate, MemoryCandidate):
        if candidate.proposed_type is not expected_type:
            errors.append(f"candidate proposed_type must be {expected_type.value}")
        return candidate.content, errors
    if not isinstance(candidate, Mapping):
        return {}, ["candidate must be a MemoryCandidate or mapping"]
    if "content" in candidate:
        proposed_type = candidate.get("proposed_type")
        if proposed_type is not None and proposed_type != expected_type.value:
            errors.append(f"candidate proposed_type must be {expected_type.value}")
        content = candidate.get("content")
        if not isinstance(content, Mapping):
            errors.append("candidate content must be a mapping")
            return {}, errors
        return content, errors
    return candidate, errors


def _text(
    content: Mapping[str, Any], field: str, errors: list[str], minimum_length: int = 1
) -> str:
    value = content.get(field)
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{field} must be a non-blank string")
        return ""
    value = value.strip()
    if len(value) < minimum_length:
        errors.append(f"{field} must contain at least {minimum_length} characters")
    return value


def _string_list(content: Mapping[str, Any], field: str, errors: list[str]) -> list[str]:
    value = content.get(field, [])
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        errors.append(f"{field} must be a list of non-blank strings")
        return []
    return [item.strip() for item in value]


def _parse_enum(value: Any, enum_type: Any, field: str, errors: list[str]) -> Any:
    try:
        return enum_type(value)
    except (TypeError, ValueError):
        errors.append(f"{field} must be a valid {enum_type.__name__}")
        return None


def _has_scope(value: Any) -> bool:
    if isinstance(value, MemoryScope):
        return any(value.model_dump().values())
    return isinstance(value, Mapping) and any(value.values())


def _is_chatter(summary: str) -> bool:
    return len(summary.split()) < 5 or summary.casefold() in {
        "done",
        "fixed it",
        "looks good",
        "all good",
        "thanks",
    }


def _appears_multiple_events(title: str, summary: str) -> bool:
    return bool(re.search(r"\b(and then|unrelated|also completed)\b", f"{title} {summary}", re.I))
