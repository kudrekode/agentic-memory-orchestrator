from enum import Enum


class ConfidenceLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CONFIRMED = "confirmed"


class ImportanceLevel(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class MemorySource(str, Enum):
    DEVELOPER_EXPLICIT = "developer_explicit"
    AGENT_INFERRED = "agent_inferred"
    REPOSITORY = "repository"
    DOCUMENTATION = "documentation"
    EPISODE = "episode"
    CONSOLIDATION = "consolidation"
    EXTERNAL_TOOL = "external_tool"


class EpisodeOutcome(str, Enum):
    RESOLVED = "resolved"
    UNRESOLVED = "unresolved"
    PARTIALLY_RESOLVED = "partially_resolved"
    INFORMATIONAL = "informational"


class ConsolidationStatus(str, Enum):
    PENDING = "pending"
    PROCESSED = "processed"
    IGNORED = "ignored"


class SemanticStatus(str, Enum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    DISPUTED = "disputed"
    OBSOLETE = "obsolete"


class LessonStatus(str, Enum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    DISABLED = "disabled"


class ProjectStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class WorkingStateStatus(str, Enum):
    IDLE = "idle"
    PLANNING = "planning"
    IMPLEMENTING = "implementing"
    INVESTIGATING = "investigating"
    BLOCKED = "blocked"
    TESTING = "testing"
    DEPLOYING = "deploying"


class LessonCategory(str, Enum):
    DEBUGGING = "debugging"
    ARCHITECTURE = "architecture"
    DEPLOYMENT = "deployment"
    WORKFLOW = "workflow"
    TOOLING = "tooling"
    CODE_QUALITY = "code_quality"
    PROJECT_CONVENTION = "project_convention"
    OTHER = "other"


class LessonPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class SemanticChangeType(str, Enum):
    CREATED = "created"
    EXPANDED = "expanded"
    CORRECTED = "corrected"
    NARROWED = "narrowed"
    SPLIT = "split"
    SUPERSEDED = "superseded"
    MARKED_OBSOLETE = "marked_obsolete"


class CreatedBy(str, Enum):
    DEVELOPER = "developer"
    AGENT = "agent"
    CONSOLIDATION = "consolidation"
    SYSTEM = "system"


class MemoryObjectType(str, Enum):
    EPISODE = "episode"
    SEMANTIC = "semantic"
    SEMANTIC_REVISION = "semantic_revision"
    LESSON = "lesson"


class MemoryRelationship(str, Enum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    UPDATES = "updates"
    DERIVED_FROM = "derived_from"
    GENERATED = "generated"
    SUPERSEDES = "supersedes"
    RELATED_TO = "related_to"


class ProposedMemoryType(str, Enum):
    EPISODE = "episode"
    SEMANTIC = "semantic"
    LESSON = "lesson"
    WORKING_STATE_UPDATE = "working_state_update"
    IGNORE = "ignore"
