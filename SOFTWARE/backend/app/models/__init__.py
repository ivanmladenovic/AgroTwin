"""SQLAlchemy domain models."""

from app.models.base import Base
from app.models.activity import Activity, ActivityType
from app.models.ai import AIConversation, AIMessage
from app.models.cost import Cost, CostCategory
from app.models.disease import DiseaseCase, DiseaseObservation
from app.models.document import Document
from app.models.farm import Farm
from app.models.invoice import Invoice
from app.models.knowledge import KnowledgeBaseItem, KnowledgeChunk, KnowledgeAsset, KnowledgePage
from app.models.parcel import Parcel
from app.models.photo import Photo
from app.models.row import Row
from app.models.tree import Tree
from app.models.user import User
from app.models.analysis import DiseaseAnalysis
from app.models.harvest import HarvestEvent
from app.models.soil import SoilProfileSnapshot
from app.models.soil_lab import SoilLabAnalysis, SoilLabResult
from app.models.subsidy import Subsidy
from app.models.schedule import OrchardSeason, TaskSchedule
from app.models.planning import ExpertReview, PlanningPlan, PlanningPlanItem, PlanningSeason
from app.models.planting import PlantingBatch
from app.models.weather import WeatherForecastCache
from app.models.satellite import SatelliteAnomaly, SatelliteObservation, SatelliteZoneMetric
from app.models.intelligence import (
    ParcelAlert,
    ParcelAnalysisEvent,
    ParcelAnalysisRun,
    UserNotification,
)
from app.models.workforce import WorkTask, WorkTaskType, Worker
from app.models.passport import HarvestLot, HarvestLotSequence, PassportSnapshot
from app.models.compliance import ComplianceReportDefinition, ComplianceReportRun
from app.models.enterprise import (
    EnterpriseAlertReview,
    EnterpriseAuditEvent,
    EnterpriseFollowUp,
    EnterpriseMembership,
    EnterpriseOrganization,
    EnterpriseParcelAssignment,
    EnterprisePlanningSeason,
    EnterprisePurchase,
    EnterpriseSupplierLink,
    EnterpriseSupplierPrice,
    EnterpriseYieldPlan,
    EnterpriseYieldPlanItem,
)
import app.models.activity as activity_module
import app.models.ai as ai_module
import app.models.cost as cost_module
import app.models.disease as disease_module
import app.models.document as document_module
import app.models.farm as farm_module
import app.models.knowledge as knowledge_module
import app.models.parcel as parcel_module
import app.models.row as row_module
import app.models.tree as tree_module
import app.models.user as user_module

user_module.Farm = Farm
user_module.AIConversation = AIConversation
farm_module.User = User
farm_module.Parcel = Parcel
parcel_module.Farm = Farm
parcel_module.Row = Row
parcel_module.Tree = Tree
row_module.Parcel = Parcel
row_module.Tree = Tree
tree_module.Parcel = Parcel
tree_module.Row = Row
tree_module.DiseaseCase = DiseaseCase
activity_module.Cost = Cost
cost_module.Activity = Activity
disease_module.Tree = Tree
document_module.KnowledgeChunk = KnowledgeChunk
document_module.KnowledgePage = KnowledgePage
document_module.KnowledgeAsset = KnowledgeAsset
knowledge_module.Document = Document
ai_module.User = User

__all__ = [
    "AIConversation",
    "AIMessage",
    "Activity",
    "ActivityType",
    "Base",
    "Cost",
    "CostCategory",
    "DiseaseAnalysis",
    "DiseaseCase",
    "DiseaseObservation",
    "Document",
    "ExpertReview",
    "Farm",
    "HarvestEvent",
    "Invoice",
    "KnowledgeBaseItem",
    "KnowledgeChunk",
    "KnowledgeAsset",
    "KnowledgePage",
    "OrchardSeason",
    "Parcel",
    "Photo",
    "PlanningPlan",
    "PlanningPlanItem",
    "PlanningSeason",
    "PlantingBatch",
    "Row",
    "SoilLabAnalysis",
    "SoilLabResult",
    "SoilProfileSnapshot",
    "Subsidy",
    "SatelliteAnomaly",
    "SatelliteObservation",
    "SatelliteZoneMetric",
    "ParcelAlert",
    "ParcelAnalysisEvent",
    "ParcelAnalysisRun",
    "UserNotification",
    "TaskSchedule",
    "Tree",
    "User",
    "WeatherForecastCache",
    "WorkTaskType",
    "Worker",
    "WorkTask",
    "HarvestLot",
    "HarvestLotSequence",
    "PassportSnapshot",
    "ComplianceReportDefinition",
    "ComplianceReportRun",
    "EnterpriseOrganization",
    "EnterpriseMembership",
    "EnterpriseSupplierLink",
    "EnterpriseParcelAssignment",
    "EnterprisePlanningSeason",
    "EnterpriseYieldPlan",
    "EnterpriseYieldPlanItem",
    "EnterpriseAuditEvent",
    "EnterpriseAlertReview",
    "EnterpriseFollowUp",
]
