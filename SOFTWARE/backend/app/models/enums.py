import enum

from sqlalchemy import Enum as SAEnum


def pg_enum(enum_cls: type[enum.Enum], name: str) -> SAEnum:
    return SAEnum(
        enum_cls,
        name=name,
        native_enum=True,
        values_callable=lambda members: [item.value for item in members],
    )


class ScopeType(str, enum.Enum):
    """Where an activity or cost belongs in the orchard hierarchy."""

    FARM = "farm"
    PARCEL = "parcel"
    ROW = "row"
    TREE = "tree"


class TreeStatus(str, enum.Enum):
    ACTIVE = "active"
    REPLACED = "replaced"
    REMOVED = "removed"


class HealthStatus(str, enum.Enum):
    HEALTHY = "healthy"
    MONITORING = "monitoring"
    ISSUE = "issue"
    UNKNOWN = "unknown"


class WellLocation(str, enum.Enum):
    NORTH = "north"
    NORTHEAST = "northeast"
    EAST = "east"
    SOUTHEAST = "southeast"
    SOUTH = "south"
    SOUTHWEST = "southwest"
    WEST = "west"
    NORTHWEST = "northwest"


class ActivityStatus(str, enum.Enum):
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class DiseaseSeverity(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DiseaseCaseStatus(str, enum.Enum):
    OPEN = "open"
    MONITORING = "monitoring"
    RESOLVED = "resolved"
    UNKNOWN = "unknown"


class DiseaseCategory(str, enum.Enum):
    DISEASE = "disease"
    PEST = "pest"
    NUTRIENT_DEFICIENCY = "nutrient_deficiency"
    WATER_STRESS = "water_stress"
    PHYSICAL_DAMAGE = "physical_damage"
    UNKNOWN = "unknown"
    OTHER = "other"


class AttachmentEntityType(str, enum.Enum):
    FARM = "farm"
    PARCEL = "parcel"
    ROW = "row"
    TREE = "tree"
    ACTIVITY = "activity"
    COST = "cost"
    DISEASE_CASE = "disease_case"
    OBSERVATION = "observation"
    KNOWLEDGE_BASE_ITEM = "knowledge_base_item"
    HARVEST_EVENT = "harvest_event"


class HarvestQualityCategory(str, enum.Enum):
    PREMIUM = "premium"
    STANDARD = "standard"
    LOWER = "lower"
    OTHER = "other"


class KnowledgeCategory(str, enum.Enum):
    MANUAL = "manual"
    DISEASE_GUIDE = "disease_guide"
    PEST_GUIDE = "pest_guide"
    NUTRITION_GUIDE = "nutrition_guide"
    PLANT_PROTECTION = "plant_protection"
    BEST_PRACTICE = "best_practice"
    OTHER = "other"


class DocumentStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class InvoiceCategory(str, enum.Enum):
    FUEL = "fuel"
    OTHER = "other"


class InvoiceKind(str, enum.Enum):
    MACHINE = "machine"
    EQUIPMENT = "equipment"
    OTHER = "other"


class AIMessageRole(str, enum.Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


ATTACHMENT_ENTITY_TYPE = pg_enum(AttachmentEntityType, "attachment_entity_type")
