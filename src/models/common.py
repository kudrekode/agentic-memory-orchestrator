from pydantic import BaseModel, Field

from src.models.enums import ImportanceLevel


class MemoryScope(BaseModel):
    """Where a memory object applies."""
    environment: str | None = None
    service: str | None = None
    repo: str | None = None
    component: str | None = None


class ImportanceDimensions(BaseModel):
    """
    Rubric scores used to calculate final importance.
    Each dimension is 0–3. Application code maps the sum to ImportanceLevel.
    """
    future_usefulness: int = Field(ge=0, le=3)
    cost_of_rediscovery: int = Field(ge=0, le=3)
    blast_radius: int = Field(ge=0, le=3)
    decision_significance: int = Field(ge=0, le=3)
    recurrence_value: int = Field(ge=0, le=3)


def calculate_importance(dimensions: ImportanceDimensions) -> ImportanceLevel:
    """Map validated importance dimensions to the documented category."""

    score = sum(dimensions.model_dump().values())
    if score <= 3:
        return ImportanceLevel.LOW
    if score <= 7:
        return ImportanceLevel.NORMAL
    if score <= 11:
        return ImportanceLevel.HIGH
    return ImportanceLevel.CRITICAL
