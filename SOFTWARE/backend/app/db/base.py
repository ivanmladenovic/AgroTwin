"""Import all models so Alembic and metadata see them."""

from app.models.ai import AIConversation, AIMessage
from app.models.activity import Activity, ActivityType
from app.models.cost import Cost
from app.models.disease import DiseaseCase
from app.models.document import Document
from app.models.farm import Farm
from app.models.harvest import HarvestEvent
from app.models.weather import WeatherForecastCache
from app.models.invoice import Invoice
from app.models.knowledge import KnowledgeBaseItem, KnowledgeChunk, KnowledgeAsset, KnowledgePage
from app.models.parcel import Parcel
from app.models.photo import Photo
from app.models.row import Row
from app.models.soil import SoilProfileSnapshot
from app.models.soil_lab import SoilLabAnalysis
from app.models.subsidy import Subsidy
from app.models.schedule import OrchardSeason, TaskSchedule
from app.models.tree import Tree
from app.models.user import User

__all__ = [
    "AIConversation",
    "AIMessage",
    "Activity",
    "ActivityType",
    "Cost",
    "DiseaseCase",
    "Document",
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
    "Row",
    "SoilLabAnalysis",
    "SoilProfileSnapshot",
    "Subsidy",
    "TaskSchedule",
    "Tree",
    "User",
    "WeatherForecastCache",
]
