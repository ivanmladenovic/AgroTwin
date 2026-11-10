import enum

from sqlalchemy import Enum as SAEnum


def pg_enum(enum_cls: type[enum.Enum], name: str, *, create_type: bool = True) -> SAEnum:
    return SAEnum(
        enum_cls,
        name=name,
        native_enum=True,
        create_type=create_type,
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


class PlanningSeasonStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class PlanningPlanType(str, enum.Enum):
    PROTECTION = "protection"
    NUTRITION = "nutrition"
    IRRIGATION = "irrigation"


class PlanningPlanStatus(str, enum.Enum):
    DRAFT = "draft"
    READY_FOR_REVIEW = "ready_for_review"
    EXPERT_REVIEW = "expert_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    ACTIVE = "active"
    COMPLETED = "completed"


class PlanningItemStatus(str, enum.Enum):
    PLANNED = "planned"
    MONITOR = "monitor"
    OBSERVED = "observed"
    NEEDS_REVIEW = "needs_review"
    APPROVED = "approved"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class PlanningItemSource(str, enum.Enum):
    SYSTEM = "system"
    AGRONOMIC_RULE = "agronomic_rule"
    PREVIOUS_PLAN = "previous_plan"
    HISTORY = "history"
    USER = "user"
    AI = "ai"


class PlanningExpertReviewStatus(str, enum.Enum):
    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    APPROVED = "approved"
    MODIFIED = "modified"
    REJECTED = "rejected"


class ExpertReviewStatus(str, enum.Enum):
    """Standalone ExpertReview audit-trail statuses (subset without not_required)."""

    PENDING = "pending"
    APPROVED = "approved"
    MODIFIED = "modified"
    REJECTED = "rejected"


class PlanningScopeType(str, enum.Enum):
    """Plan item scope — subset of orchard hierarchy (no farm-wide plans)."""

    PARCEL = "parcel"
    ROW = "row"
    TREE = "tree"


class PlanningItemKind(str, enum.Enum):
    """Shared plan item kinds across protection / nutrition / irrigation.

    No pesticide or fertilizer product recommendations in Phase 5–6 foundation.
    """

    MONITORING = "monitoring"
    OBSERVATION = "observation"
    ASSESSMENT = "assessment"
    EXPERT_REVIEW = "expert_review"
    INTERVENTION_PENDING = "intervention_pending"
    # Nutrition (Phase 6)
    SOIL_REVIEW = "soil_review"
    NUTRITION_MONITORING = "nutrition_monitoring"
    FERTILIZATION_WINDOW = "fertilization_window"
    # Irrigation (Phase 6)
    IRRIGATION_MONITORING = "irrigation_monitoring"
    IRRIGATION_WINDOW = "irrigation_window"
    ESTIMATED_NEED = "estimated_need"
    SYSTEM_CALCULATION = "system_calculation"


class IrrigationType(str, enum.Enum):
    DRIP = "drip"
    SPRINKLER = "sprinkler"
    MICROSPRINKLER = "microsprinkler"
    OTHER = "other"


class PlanningStream(str, enum.Enum):
    PREVENTIVE = "preventive"
    REACTIVE = "reactive"


class PlanningPriorityLevel(str, enum.Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class ProductionMethod(str, enum.Enum):
    CONVENTIONAL = "conventional"
    ORGANIC = "organic"


class OrganicScope(str, enum.Enum):
    NONE = "none"
    ENTIRE_PARCEL = "entire_parcel"
    PART_OF_PARCEL = "part_of_parcel"


class PlantingBatchScope(str, enum.Enum):
    PARCEL = "parcel"
    ROW = "row"


class SoilLabExtractionStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class SoilLabVerificationStatus(str, enum.Enum):
    EXTRACTED = "extracted"
    NEEDS_REVIEW = "needs_review"
    VERIFIED = "verified"
    SKIPPED = "skipped"


class ActivitySemanticType(str, enum.Enum):
    """Planning-facing meaning of a journal record. Does not replace activity_types catalog."""

    OBSERVATION = "observation"
    PROBLEM = "problem"
    TREATMENT = "treatment"
    FERTILIZATION = "fertilization"
    IRRIGATION = "irrigation"
    MONITORING = "monitoring"
    PRUNING = "pruning"
    PLANTING = "planting"
    OTHER = "other"


class ObservationCategory(str, enum.Enum):
    DISEASE = "disease"
    PEST = "pest"
    NUTRIENT = "nutrient"
    WEATHER_DAMAGE = "weather_damage"
    WATER_STRESS = "water_stress"
    TREE_HEALTH = "tree_health"
    FRUIT = "fruit"
    LEAF = "leaf"
    SOIL = "soil"
    OTHER = "other"
    UNKNOWN = "unknown"


class ObservationStatus(str, enum.Enum):
    NEW = "new"
    MONITORING = "monitoring"
    CONFIRMED = "confirmed"
    RESOLVED = "resolved"
    REJECTED = "rejected"
    UNKNOWN = "unknown"


class SatelliteProcessingStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class SatelliteAnomalyKind(str, enum.Enum):
    BELOW_PARCEL_MEAN = "below_parcel_mean"
    SUDDEN_DECLINE = "sudden_decline"
    PERSISTENT_LOW = "persistent_low"


class ParcelAnalysisEventKind(str, enum.Enum):
    SATELLITE_OBSERVATION = "satellite_observation"
    SATELLITE_ANOMALY = "satellite_anomaly"
    WEATHER_EVENT = "weather_event"
    ACTIVITY_PROTECTION = "activity_protection"
    ACTIVITY_FERTILIZATION = "activity_fertilization"
    ACTIVITY_IRRIGATION = "activity_irrigation"
    HARVEST_RECORDED = "harvest_recorded"
    YIELD_DEVIATION = "yield_deviation"
    MANUAL_REQUEST = "manual_request"
    SCHEDULED = "scheduled"


class ParcelAlertSeverity(str, enum.Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class ParcelAlertStatus(str, enum.Enum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class ParcelAnalysisRunStatus(str, enum.Enum):
    SKIPPED = "skipped"
    COMPLETED = "completed"
    FAILED = "failed"


class WorkTaskStatus(str, enum.Enum):
    PLANNED = "planned"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class CostSource(str, enum.Enum):
    ACTIVITY = "activity"
    WORK_TASK = "work_task"


class PassportStatus(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    FINALIZED = "finalized"
    REVOKED = "revoked"


class ComplianceReportType(str, enum.Enum):
    FARM_PROFILE = "farm_profile"
    PARCEL_REGISTER = "parcel_register"
    PLANT_PROTECTION = "plant_protection"
    FERTILIZATION_INPUTS = "fertilization_inputs"
    HARVEST_TRACEABILITY = "harvest_traceability"
    FARM_ACTIVITY = "farm_activity"
    IRRIGATION_WATER = "irrigation_water"
    COMPLIANCE_PACKAGE = "compliance_package"


class ComplianceReportFormat(str, enum.Enum):
    JSON = "json"
    CSV = "csv"
    PDF = "pdf"
    ZIP = "zip"


class EnterpriseOrgStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class EnterpriseMembershipRole(str, enum.Enum):
    ENTERPRISE_ADMIN = "enterprise_admin"
    ENTERPRISE_ANALYST = "enterprise_analyst"
    ENTERPRISE_VIEWER = "enterprise_viewer"


class EnterpriseMembershipStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    INVITED = "invited"


class EnterpriseRelationshipStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"


class EnterpriseAssignmentStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"


class EnterpriseSeasonStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    CLOSED = "closed"


class EnterpriseYieldPlanStatus(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class EnterpriseScenarioType(str, enum.Enum):
    CONSERVATIVE = "conservative"
    REALISTIC = "realistic"
    OPTIMISTIC = "optimistic"
    CUSTOM = "custom"


class EnterpriseAuditAction(str, enum.Enum):
    ORG_UPDATED = "org_updated"
    MEMBER_ADDED = "member_added"
    MEMBER_UPDATED = "member_updated"
    SUPPLIER_ASSIGNED = "supplier_assigned"
    SUPPLIER_UPDATED = "supplier_updated"
    PARCEL_ASSIGNED = "parcel_assigned"
    PARCEL_UPDATED = "parcel_updated"
    SEASON_CREATED = "season_created"
    PLAN_CREATED = "plan_created"
    PLAN_RECALCULATED = "plan_recalculated"
    EXPORT_GENERATED = "export_generated"
    SUPPLIER_PRICE_UPSERTED = "supplier_price_upserted"
    PURCHASE_CREATED = "purchase_created"
    PURCHASE_UPDATED = "purchase_updated"
    PURCHASE_DELETED = "purchase_deleted"
    ALERT_REVIEWED = "alert_reviewed"
    FOLLOW_UP_CREATED = "follow_up_created"
    FOLLOW_UP_UPDATED = "follow_up_updated"
    FOLLOW_UP_STATUS_CHANGED = "follow_up_status_changed"


class EnterprisePurchaseCurrency(str, enum.Enum):
    RSD = "RSD"
    EUR = "EUR"


class EnterpriseQuantityBasis(str, enum.Enum):
    """Whether quantity/price refers to in-shell (bruto) or kernel (neto)."""

    BRUTO = "bruto"
    NETO = "neto"


ATTACHMENT_ENTITY_TYPE = pg_enum(AttachmentEntityType, "attachment_entity_type")
