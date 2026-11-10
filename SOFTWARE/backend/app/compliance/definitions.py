from __future__ import annotations

from dataclasses import dataclass

from app.models.enums import ComplianceReportType


@dataclass(frozen=True)
class ReportDefinitionSpec:
    type: ComplianceReportType
    title: str
    description: str
    data_source: str
    template: str = "tabular_v1"
    version: str = "1.0"
    sort_order: int = 0
    include_in_default_package: bool = True


REPORT_DEFINITIONS: list[ReportDefinitionSpec] = [
    ReportDefinitionSpec(
        type=ComplianceReportType.FARM_PROFILE,
        title="01 Profil gazdinstva",
        description="Osnovni profil gazdinstva iz evidencije AgroTwin.",
        data_source="farms",
        sort_order=10,
    ),
    ReportDefinitionSpec(
        type=ComplianceReportType.PARCEL_REGISTER,
        title="02 Registar parcela",
        description="Registar parcela i osnovnih podataka o proizvodnji.",
        data_source="parcels",
        sort_order=20,
    ),
    ReportDefinitionSpec(
        type=ComplianceReportType.PLANT_PROTECTION,
        title="03 Zaštita bilja",
        description="Evidencija tretmana i zaštite bilja iz dnevnika aktivnosti.",
        data_source="activities.treatment",
        sort_order=30,
    ),
    ReportDefinitionSpec(
        type=ComplianceReportType.FERTILIZATION_INPUTS,
        title="04 Đubrenje i unosi",
        description="Evidencija đubrenja i unosa hraniva.",
        data_source="activities.fertilization",
        sort_order=40,
    ),
    ReportDefinitionSpec(
        type=ComplianceReportType.HARVEST_TRACEABILITY,
        title="05 Berba i sledljivost",
        description="Berba i sledljivost lotova (lot / digitalni pasoš).",
        data_source="harvest_lots",
        sort_order=50,
    ),
    ReportDefinitionSpec(
        type=ComplianceReportType.FARM_ACTIVITY,
        title="06 Aktivnosti na gazdinstvu",
        description="Aktivnosti na farmi, uključujući radnike i troškove gde postoje.",
        data_source="activities+work_tasks",
        sort_order=60,
    ),
    ReportDefinitionSpec(
        type=ComplianceReportType.IRRIGATION_WATER,
        title="07 Navodnjavanje i voda",
        description="Navodnjavanje — profil parcele i evidentirane aktivnosti.",
        data_source="parcels.irrigation+activities.irrigation",
        sort_order=70,
        include_in_default_package=True,
    ),
    ReportDefinitionSpec(
        type=ComplianceReportType.COMPLIANCE_PACKAGE,
        title="Paket usaglašenosti / audita",
        description="Paket izabranih PDF izveštaja za pripremu dokumentacije.",
        data_source="package",
        sort_order=100,
        include_in_default_package=False,
    ),
]

GENERATED_VIA = "Generisano kroz AgroTwin platformu"

DISCLAIMER = (
    "Izveštaj usaglašenosti AgroTwin. Pripremljen isključivo iz evidencije sačuvane u AgroTwin. "
    "Ovaj dokument ne sertifikuje gazdinstvo i ne garantuje usklađenost sa GLOBALG.A.P. "
    "niti bilo kojim drugim standardom."
)
