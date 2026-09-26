"""Idempotent presentation history for the real Kusiljevo parcel.

Does not delete existing trees, activities or costs. Re-running skips
records that already exist (same title + date on the same parcel).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.activity import Activity
from app.models.cost import Cost
from app.models.disease import DiseaseCase, DiseaseObservation
from app.models.enums import (
    ActivityStatus,
    AttachmentEntityType,
    DiseaseCaseStatus,
    DiseaseCategory,
    DiseaseSeverity,
    HarvestQualityCategory,
    HealthStatus,
    ScopeType,
    TreeStatus,
    WellLocation,
)
from app.models.farm import Farm
from app.models.harvest import HarvestEvent
from app.models.parcel import Parcel
from app.models.photo import Photo
from app.models.row import Row
from app.models.tree import Tree
from app.models.user import User
from app.services.catalog import CatalogService
from app.services.disease import DiseaseService
from app.storage import get_storage
from app.storage.png import solid_png

KUSILJEVO = "Kusiljevo"


def seed_kusiljevo_presentation(db: Session, user: User, farm: Farm) -> None:
    parcel = db.scalars(select(Parcel).where(Parcel.farm_id == farm.id, Parcel.name == KUSILJEVO)).first()
    if parcel is None:
        return

    farm.name = "Voćnjak Kusiljevo"
    farm.location_name = "Kusiljevo, Srbija"
    farm.description = "Zasad lesnika Tonda di Giffoni sa oprašivačima, 26 redova × 73 mesta."
    farm.area_hectares = parcel.area_hectares or Decimal("4.7500")
    user.full_name = "Ivan Mladenović"
    parcel.notes = (
        "Zasad iz 2022. na blagoj padini iznad sela. Glavna sorta Tonda di Giffoni, "
        "oprašivači Tonda Gentile Romana i Nocchione. Sistem kap po kap od prve godine."
    )
    if parcel.well_location is None:
        parcel.well_location = WellLocation.WEST
        parcel.well_x = Decimal("-6.0000")
        parcel.well_y = Decimal("62.5000")
    db.flush()

    catalogs = CatalogService(db)
    types = {item.slug: item for item in catalogs.catalogs.list_activity_types()}
    categories = {item.slug: item for item in catalogs.catalogs.list_cost_categories()}

    _apply_replacements(db, parcel)
    _seed_history(db, user, farm, parcel, types, categories)
    _seed_health(db, user, farm, parcel)
    _seed_harvests(db, user, farm, parcel)


def _tree_at(db: Session, parcel_id: object, row_number: int, position: int) -> Tree | None:
    row = db.scalars(select(Row).where(Row.parcel_id == parcel_id, Row.row_number == row_number)).first()
    if row is None:
        return None
    return db.scalars(select(Tree).where(Tree.row_id == row.id, Tree.position_in_row == position)).first()


def _apply_replacements(db: Session, parcel: Parcel) -> None:
    existing = db.scalar(
        select(Tree.id).where(Tree.parcel_id == parcel.id, Tree.status != TreeStatus.ACTIVE).limit(1)
    )
    if existing is not None:
        return
    replacements = (
        (8, 12, 2023),
        (8, 41, 2023),
        (15, 7, 2024),
        (21, 58, 2024),
        (4, 33, 2025),
    )
    for row_number, position, year in replacements:
        tree = _tree_at(db, parcel.id, row_number, position)
        if tree is None:
            continue
        tree.status = TreeStatus.REPLACED
        tree.planting_year = year
        tree.health_status = HealthStatus.HEALTHY
    db.flush()


def _seed_history(db: Session, user: User, farm: Farm, parcel: Parcel, types: dict, categories: dict) -> None:
    row_14 = db.scalars(select(Row).where(Row.parcel_id == parcel.id, Row.row_number == 14)).first()
    tree_r14 = _tree_at(db, parcel.id, 14, 38)
    tree_r6 = _tree_at(db, parcel.id, 6, 22)

    records: list[dict] = [
        # 2022 — zasnivanje
        {
            "on": date(2022, 3, 8),
            "type": "maintenance",
            "title": "Priprema zemljišta i razmeravanje",
            "description": "Oranje, tanjiranje i razmeravanje 26 redova pre sadnje.",
            "qty": "4.75",
            "unit": "ha",
            "costs": [("3200.00", "machinery", "Rad traktora i priprema parcele"), ("480.00", "fuel", "Gorivo")],
        },
        {
            "on": date(2022, 3, 18),
            "type": "planting",
            "title": "Sadnja lesnika",
            "description": "Sadnja Tonda di Giffoni sa redovima oprašivača Romana i Nocchione.",
            "qty": "1898",
            "unit": "kom",
            "costs": [
                ("9110.40", "planting_material", "Sadnice lesnika"),
                ("2840.00", "labor", "Rad na sadnji"),
            ],
        },
        {
            "on": date(2022, 4, 4),
            "type": "maintenance",
            "title": "Postavljanje sistema kap po kap",
            "description": "Glavni vod, laterale i kapaljke duž svih redova. Bunar na zapadnoj strani.",
            "costs": [
                ("11850.00", "equipment", "Cijevi, kapaljke i filteri"),
                ("1960.00", "labor", "Montaža sistema"),
            ],
        },
        {
            "on": date(2022, 4, 16),
            "type": "fertilization",
            "title": "Starter đubrenje uz sadnju",
            "description": "NPK 15-15-15 uz sadnice, 80 g po stablu.",
            "qty": "152",
            "unit": "kg",
            "costs": [("980.00", "fertilizers", "Starter NPK"), ("220.00", "labor", "Unošenje đubriva")],
        },
        {
            "on": date(2022, 6, 12),
            "type": "irrigation",
            "title": "Navodnjavanje, jun 2022.",
            "qty": "42",
            "unit": "m³",
            "costs": [("210.00", "water", "Voda"), ("95.00", "electricity", "Pumpa")],
        },
        {
            "on": date(2022, 7, 9),
            "type": "irrigation",
            "title": "Navodnjavanje, jul 2022.",
            "qty": "68",
            "unit": "m³",
            "costs": [("340.00", "water", "Voda"), ("120.00", "electricity", "Pumpa")],
        },
        {
            "on": date(2022, 8, 3),
            "type": "irrigation",
            "title": "Navodnjavanje, avgust 2022.",
            "qty": "71",
            "unit": "m³",
            "costs": [("355.00", "water", "Voda"), ("125.00", "electricity", "Pumpa")],
        },
        {
            "on": date(2022, 8, 20),
            "type": "maintenance",
            "title": "Košenje međureda i okopavanje",
            "costs": [("640.00", "labor", "Košenje i okopavanje"), ("180.00", "fuel", "Gorivo")],
        },
        {
            "on": date(2022, 11, 12),
            "type": "inspection",
            "title": "Jesenski pregled prijema sadnica",
            "description": "Procenjen prijem oko 99 %. Dve praznine ostavljene za prolećnu dopunu.",
        },
        # 2023
        {
            "on": date(2023, 2, 18),
            "type": "pruning",
            "title": "Formativna rezidba, zima 2023.",
            "description": "Formiranje čaše na Tonda di Giffoni, skraćivanje oprašivača.",
            "costs": [("1280.00", "labor", "Rezidba"), ("90.00", "fuel", "Gorivo")],
        },
        {
            "on": date(2023, 3, 22),
            "type": "tree_replacement",
            "title": "Dopuna uginulih sadnica",
            "description": "Zamenjene sadnice u redu 8. Prijem posle prve zime.",
            "qty": "2",
            "unit": "kom",
            "costs": [("28.00", "planting_material", "Sadnice za zamenu"), ("80.00", "labor", "Ponovna sadnja")],
        },
        {
            "on": date(2023, 4, 6),
            "type": "fertilization",
            "title": "Prolećno đubrenje 2023.",
            "qty": "190",
            "unit": "kg",
            "costs": [("1120.00", "fertilizers", "KAN i NPK"), ("160.00", "labor", "Rasturanje")],
        },
        {
            "on": date(2023, 5, 11),
            "type": "spraying",
            "title": "Prskanje protiv bakterioze, maj 2023.",
            "qty": "380",
            "unit": "L",
            "costs": [("420.00", "plant_protection", "Bakarni preparat"), ("180.00", "labor", "Prskanje"), ("70.00", "fuel", "Gorivo")],
        },
        {
            "on": date(2023, 6, 16),
            "type": "spraying",
            "title": "Prskanje protiv lisnih vaši, jun 2023.",
            "qty": "360",
            "unit": "L",
            "costs": [("310.00", "plant_protection", "Insekticid"), ("170.00", "labor", "Prskanje")],
        },
        {
            "on": date(2023, 7, 8),
            "type": "irrigation",
            "title": "Navodnjavanje, jul 2023.",
            "qty": "92",
            "unit": "m³",
            "costs": [("460.00", "water", "Voda"), ("140.00", "electricity", "Pumpa")],
        },
        {
            "on": date(2023, 8, 2),
            "type": "irrigation",
            "title": "Navodnjavanje, avgust 2023.",
            "qty": "88",
            "unit": "m³",
            "costs": [("440.00", "water", "Voda"), ("135.00", "electricity", "Pumpa")],
        },
        {
            "on": date(2023, 9, 14),
            "type": "inspection",
            "title": "Pregled rasta posle druge sezone",
            "description": "Krošnje u formiranju, bez berbe. Redovi 3–6 oprašivača u dobrom stanju.",
        },
        {
            "on": date(2023, 10, 20),
            "type": "maintenance",
            "title": "Jesensko košenje i pregled sistema",
            "costs": [("390.00", "labor", "Košenje"), ("85.00", "maintenance", "Filteri i kapaljke")],
        },
        # 2024
        {
            "on": date(2024, 2, 10),
            "type": "pruning",
            "title": "Zimska rezidba 2024.",
            "costs": [("1420.00", "labor", "Rezidba"), ("110.00", "fuel", "Gorivo")],
        },
        {
            "on": date(2024, 3, 19),
            "type": "fertilization",
            "title": "Prolećno đubrenje 2024.",
            "qty": "210",
            "unit": "kg",
            "costs": [("1260.00", "fertilizers", "NPK i KAN"), ("170.00", "labor", "Rasturanje")],
        },
        {
            "on": date(2024, 4, 2),
            "type": "tree_replacement",
            "title": "Zamena slabo primljenih stabala",
            "qty": "2",
            "unit": "kom",
            "costs": [("32.00", "planting_material", "Sadnice"), ("90.00", "labor", "Sadnja")],
        },
        {
            "on": date(2024, 4, 24),
            "type": "spraying",
            "title": "Prskanje pred cvetanje 2024.",
            "qty": "420",
            "unit": "L",
            "costs": [("510.00", "plant_protection", "Fungicid i bakar"), ("190.00", "labor", "Prskanje"), ("80.00", "fuel", "Gorivo")],
        },
        {
            "on": date(2024, 5, 28),
            "type": "spraying",
            "title": "Prskanje posle cvetanja 2024.",
            "qty": "410",
            "unit": "L",
            "costs": [("480.00", "plant_protection", "Zaštita plodića"), ("185.00", "labor", "Prskanje")],
        },
        {
            "on": date(2024, 6, 21),
            "type": "irrigation",
            "title": "Navodnjavanje, jun 2024.",
            "qty": "96",
            "unit": "m³",
            "costs": [("480.00", "water", "Voda"), ("150.00", "electricity", "Pumpa")],
        },
        {
            "on": date(2024, 7, 18),
            "type": "irrigation",
            "title": "Navodnjavanje, jul 2024.",
            "qty": "110",
            "unit": "m³",
            "costs": [("550.00", "water", "Voda"), ("165.00", "electricity", "Pumpa")],
        },
        {
            "on": date(2024, 8, 9),
            "type": "spraying",
            "title": "Prskanje protiv pepelnice, avgust 2024.",
            "qty": "390",
            "unit": "L",
            "costs": [("360.00", "plant_protection", "Fungicid"), ("175.00", "labor", "Prskanje")],
        },
        {
            "on": date(2024, 9, 26),
            "type": "harvesting",
            "title": "Prva probna berba 2024.",
            "description": "Mali urod treće godine. Ručno sakupljanje uz ivice redova 1–10.",
            "qty": "180",
            "unit": "kg",
            "costs": [("620.00", "harvesting", "Berba i vreće"), ("340.00", "labor", "Dnevnice")],
        },
        {
            "on": date(2024, 11, 8),
            "type": "fertilization",
            "title": "Jesenje đubrenje stajnjakom 2024.",
            "qty": "12",
            "unit": "t",
            "costs": [("780.00", "fertilizers", "Stajnjak"), ("260.00", "machinery", "Rasturanje")],
        },
        # 2025 — prva ozbiljnija berba
        {
            "on": date(2025, 2, 6),
            "type": "pruning",
            "title": "Zimska rezidba 2025.",
            "costs": [("1580.00", "labor", "Rezidba"), ("125.00", "fuel", "Gorivo")],
        },
        {
            "on": date(2025, 3, 14),
            "type": "fertilization",
            "title": "Prolećno đubrenje 2025.",
            "qty": "230",
            "unit": "kg",
            "costs": [("1380.00", "fertilizers", "NPK 6-12-24 i KAN"), ("180.00", "labor", "Rasturanje")],
        },
        {
            "on": date(2025, 4, 12),
            "type": "spraying",
            "title": "Prskanje pred cvetanje 2025.",
            "qty": "450",
            "unit": "L",
            "costs": [("560.00", "plant_protection", "Bakarni i fungicid"), ("200.00", "labor", "Prskanje"), ("85.00", "fuel", "Gorivo")],
        },
        {
            "on": date(2025, 5, 9),
            "type": "spraying",
            "title": "Prskanje protiv žiška, maj 2025.",
            "qty": "440",
            "unit": "L",
            "costs": [("490.00", "plant_protection", "Insekticid"), ("195.00", "labor", "Prskanje")],
        },
        {
            "on": date(2025, 6, 7),
            "type": "irrigation",
            "title": "Navodnjavanje, jun 2025.",
            "qty": "104",
            "unit": "m³",
            "costs": [("520.00", "water", "Voda"), ("155.00", "electricity", "Pumpa")],
        },
        {
            "on": date(2025, 6, 26),
            "type": "spraying",
            "title": "Prskanje protiv monilije, jun 2025.",
            "qty": "430",
            "unit": "L",
            "costs": [("410.00", "plant_protection", "Fungicid"), ("190.00", "labor", "Prskanje")],
        },
        {
            "on": date(2025, 7, 20),
            "type": "irrigation",
            "title": "Navodnjavanje, jul 2025.",
            "qty": "118",
            "unit": "m³",
            "costs": [("590.00", "water", "Voda"), ("170.00", "electricity", "Pumpa")],
        },
        {
            "on": date(2025, 8, 14),
            "type": "irrigation",
            "title": "Navodnjavanje, avgust 2025.",
            "qty": "102",
            "unit": "m³",
            "costs": [("510.00", "water", "Voda"), ("150.00", "electricity", "Pumpa")],
        },
        {
            "on": date(2025, 9, 8),
            "type": "inspection",
            "title": "Pregled pred berbu 2025.",
            "description": "Plodovi u punom nalivu. Uočene rupe od žiška u redu 12, kasnije prijavljeno.",
        },
        {
            "on": date(2025, 9, 29),
            "type": "harvesting",
            "title": "Berba 2025.",
            "description": "Prva komercijalna berba. Sušenje u trećaku, predaja otkupljivaču u Svilajncu.",
            "qty": "1850",
            "unit": "kg",
            "costs": [("2140.00", "harvesting", "Berba, vreće i sušenje"), ("980.00", "labor", "Dnevnice"), ("220.00", "transport", "Prevoz")],
        },
        {
            "on": date(2025, 11, 6),
            "type": "fertilization",
            "title": "Jesenje đubrenje 2025.",
            "qty": "160",
            "unit": "kg",
            "costs": [("640.00", "fertilizers", "Kalijum sulfat"), ("140.00", "labor", "Rasturanje")],
        },
        # 2026 — tekuća sezona
        {
            "on": date(2026, 1, 28),
            "type": "pruning",
            "title": "Zimska rezidba 2026.",
            "description": "Proređivanje unutrašnje krošnje, uklanjanje vodopija.",
            "costs": [("1640.00", "labor", "Rezidba"), ("130.00", "fuel", "Gorivo")],
        },
        {
            "on": date(2026, 3, 11),
            "type": "fertilization",
            "title": "Prolećno đubrenje 2026.",
            "qty": "240",
            "unit": "kg",
            "costs": [("1440.00", "fertilizers", "NPK i KAN"), ("185.00", "labor", "Rasturanje")],
        },
        {
            "on": date(2026, 4, 8),
            "type": "spraying",
            "title": "Prskanje pred cvetanje 2026.",
            "qty": "460",
            "unit": "L",
            "costs": [("580.00", "plant_protection", "Bakar i fungicid"), ("210.00", "labor", "Prskanje"), ("90.00", "fuel", "Gorivo")],
        },
        {
            "on": date(2026, 5, 6),
            "type": "spraying",
            "title": "Prskanje protiv žiška, maj 2026.",
            "qty": "450",
            "unit": "L",
            "costs": [("505.00", "plant_protection", "Insekticid"), ("205.00", "labor", "Prskanje")],
        },
        {
            "on": date(2026, 5, 22),
            "type": "inspection",
            "title": "Pregled cvetanja i naliva",
            "description": "Cvetanje uredno. Oprašivači u redovima 3–6 u punom polenu.",
        },
        {
            "on": date(2026, 6, 4),
            "type": "irrigation",
            "title": "Navodnjavanje, jun 2026.",
            "qty": "98",
            "unit": "m³",
            "costs": [("490.00", "water", "Voda"), ("148.00", "electricity", "Pumpa")],
        },
        {
            "on": date(2026, 6, 19),
            "type": "spraying",
            "title": "Prskanje protiv monilije, jun 2026.",
            "qty": "440",
            "unit": "L",
            "costs": [("425.00", "plant_protection", "Fungicid"), ("200.00", "labor", "Prskanje")],
        },
        {
            "on": date(2026, 7, 7),
            "type": "irrigation",
            "title": "Navodnjavanje, početak jula 2026.",
            "qty": "112",
            "unit": "m³",
            "costs": [("560.00", "water", "Voda"), ("162.00", "electricity", "Pumpa")],
        },
        {
            "on": date(2026, 7, 24),
            "type": "irrigation",
            "title": "Navodnjavanje, kasni jul 2026.",
            "description": "Sušan period. Donji deo parcele zadržava manje vlage.",
            "qty": "108",
            "unit": "m³",
            "costs": [("540.00", "water", "Voda"), ("158.00", "electricity", "Pumpa")],
        },
        {
            "on": date(2026, 8, 12),
            "type": "spraying",
            "title": "Prskanje protiv pepelnice, avgust 2026.",
            "qty": "400",
            "unit": "L",
            "costs": [("340.00", "plant_protection", "Fungicid"), ("180.00", "labor", "Prskanje")],
        },
        {
            "on": date(2026, 8, 18),
            "type": "inspection",
            "title": "Pregled posle sušnog talasa",
            "description": "Uvenuće na južnom obodu, red 22. Kasnije prijavljen vodni stres.",
        },
        {
            "on": date(2026, 8, 28),
            "type": "disease_treatment",
            "title": "Lokalni tretman rakova na R14-T0038",
            "description": "Uklanjanje osušenih grančica i premaz rana. Nije potvrđena laboratorijska dijagnoza.",
            "scope": "tree",
            "tree": tree_r14,
            "row": row_14,
            "costs": [("42.00", "plant_protection", "Sredstvo za premaz"), ("35.00", "labor", "Rad na stablu")],
        },
        {
            "on": date(2026, 9, 8),
            "type": "inspection",
            "title": "Pregled plodova zbog žiška",
            "description": "Rupe na donjoj krošnji u redu 6. Prijavljen slučaj.",
            "scope": "tree",
            "tree": tree_r6,
        },
        {
            "on": date(2026, 9, 22),
            "type": "spraying",
            "title": "Kontrolno prskanje pred berbu",
            "status": ActivityStatus.PLANNED,
            "qty": "420",
            "unit": "L",
        },
        {
            "on": date(2026, 10, 12),
            "type": "harvesting",
            "title": "Berba 2026.",
            "description": "Planirana berba. Očekivanje 2,2–2,6 t suvog ploda.",
            "status": ActivityStatus.PLANNED,
        },
        {
            "on": date(2026, 11, 4),
            "type": "fertilization",
            "title": "Jesenje đubrenje 2026.",
            "status": ActivityStatus.PLANNED,
            "qty": "170",
            "unit": "kg",
        },
    ]

    for item in records:
        if item.get("scope") == "tree" and item.get("tree") is None:
            continue
        title = item["title"]
        performed_on = item["on"]
        if db.scalar(
            select(Activity.id).where(
                Activity.parcel_id == parcel.id,
                Activity.title == title,
                Activity.performed_on == performed_on,
            )
        ):
            continue

        scope = item.get("scope", "parcel")
        tree = item.get("tree")
        row = item.get("row")
        row_id = row.id if row is not None else None
        if tree is not None:
            row_id = tree.row_id or db.scalar(select(Tree.row_id).where(Tree.id == tree.id))
        activity = Activity(
            activity_type_id=types[item["type"]].id,
            title=title,
            description=item.get("description"),
            performed_on=performed_on,
            status=item.get("status", ActivityStatus.COMPLETED),
            quantity=Decimal(item["qty"]) if item.get("qty") else None,
            unit=item.get("unit"),
            line_items=_line_items(item),
            notes=item.get("description"),
            created_by_id=user.id,
            scope_type=ScopeType.TREE if scope == "tree" else ScopeType.PARCEL,
            farm_id=farm.id,
            parcel_id=parcel.id,
            row_id=row_id,
            tree_id=tree.id if tree is not None else None,
            extra_row_ids=[str(row_id)] if row_id is not None else [],
        )
        db.add(activity)
        db.flush()
        for amount, slug, description in item.get("costs", []):
            db.add(
                Cost(
                    amount=Decimal(amount),
                    currency="EUR",
                    incurred_on=performed_on,
                    description=description,
                    cost_category_id=categories[slug].id,
                    activity_id=activity.id,
                    scope_type=activity.scope_type,
                    farm_id=farm.id,
                    parcel_id=parcel.id,
                    row_id=activity.row_id,
                    tree_id=activity.tree_id,
                    created_by_id=user.id,
                )
            )
        db.flush()


def _line_items(item: dict) -> list[dict]:
    items: list[dict] = []
    if item.get("qty") and item.get("unit"):
        items.append({"quantity": item["qty"], "unit": item["unit"]})
    total = sum(Decimal(amount) for amount, _slug, _desc in item.get("costs", []))
    if total > 0:
        items.append({"quantity": str(total), "unit": "EUR"})
    return items


def _seed_health(db: Session, user: User, farm: Farm, parcel: Parcel) -> None:
    if db.scalar(select(DiseaseCase.id).where(DiseaseCase.parcel_id == parcel.id).limit(1)):
        return

    cases = [
        {
            "row": 14,
            "pos": 38,
            "title": "Sumnja na bakteriozu / rakovinu izdanaka",
            "description": "Ulegnute lezije na grančicama istočne krošnje. Terensko opažanje, nije laboratorijska potvrda.",
            "category": DiseaseCategory.DISEASE,
            "severity": DiseaseSeverity.MEDIUM,
            "status": DiseaseCaseStatus.MONITORING,
            "detected": date(2026, 8, 28),
            "notes": "Stablo ostaje u praćenju do berbe.",
            "obs": [
                (date(2026, 8, 28), "Rakovi na grančicama i rasuto žuto lišće na istočnoj strani.", "Prva beleška posle rezidbe suvih vrhova."),
                (date(2026, 9, 10), "Lezije se proširile na još dve grančice.", "Tretman nije menjan."),
                (date(2026, 9, 14), "Istočna krošnja se proređuje; novi rakovi nisu nađeni.", None),
            ],
            "photos": [
                (0, "krosnja-istok.png", (120, 92, 48), "Istočna krošnja, 28. avg"),
                (0, "lezija-grancica.png", (140, 70, 48), "Lezija na grančici, 28. avg"),
                (1, "sirenje-grana.png", (110, 78, 42), "Širenje na granama, 10. sep"),
                (2, "kontrola-krosnje.png", (96, 88, 52), "Kontrolna krošnja, 14. sep"),
            ],
        },
        {
            "row": 6,
            "pos": 22,
            "title": "Sumnja na ishranjivanje žiška",
            "description": "Izlazne rupe na plodovima donje krošnje. Visoka ozbiljnost dok se ne prebroji oštećenje pred berbu.",
            "category": DiseaseCategory.PEST,
            "severity": DiseaseSeverity.HIGH,
            "status": DiseaseCaseStatus.OPEN,
            "detected": date(2026, 9, 8),
            "obs": [
                (date(2026, 9, 8), "Više plodova sa rupama na južnoj donjoj strani.", "Označeno kao problem na mapi."),
                (date(2026, 9, 13), "Na zemlji ispod krošnje 11 ispalih plodova sa rupama.", None),
            ],
            "photos": [(0, "plodovi-rupe.png", (88, 54, 36), "Plodovi sa rupama, 8. sep")],
        },
        {
            "row": 11,
            "pos": 8,
            "title": "Bledo mlado lišće, mogući nedostatak hraniva",
            "description": "Međužilno žućenje na mladom rastu. Može biti azot, vlaga ili oboje.",
            "category": DiseaseCategory.NUTRIENT_DEFICIENCY,
            "severity": DiseaseSeverity.LOW,
            "status": DiseaseCaseStatus.MONITORING,
            "detected": date(2026, 6, 11),
            "obs": [(date(2026, 6, 11), "Bledo mlado lišće u gornjoj trećini krošnje.", "Zemlja nije previše vlažna.")],
            "photos": [(0, "bledo-lisce.png", (168, 176, 92), "Bledo lišće, 11. jun")],
        },
        {
            "row": 22,
            "pos": 40,
            "title": "Vodni stres posle julskog sušnog talasa",
            "description": "Uvenuće i uvijanje lista na južnom obodu, i pored navodnjavanja.",
            "category": DiseaseCategory.WATER_STRESS,
            "severity": DiseaseSeverity.MEDIUM,
            "status": DiseaseCaseStatus.MONITORING,
            "detected": date(2026, 7, 26),
            "obs": [
                (date(2026, 7, 26), "Listovi visoko na suncu uvenu do podneva.", "Kapaljke rade, pritisak na laterali niži nego u redu 1."),
                (date(2026, 8, 18), "Stanje bolje posle kiše, vrhovi i dalje retki.", None),
            ],
            "photos": [(0, "vodni-stres.png", (140, 128, 72), "Uvel list, 26. jul")],
        },
        {
            "row": 18,
            "pos": 30,
            "title": "Smeđi plodovi, sumnja na moniliju",
            "description": "Smeđi, osušeni plodovi ostaju na grančici. Opažanje pred berbu.",
            "category": DiseaseCategory.DISEASE,
            "severity": DiseaseSeverity.HIGH,
            "status": DiseaseCaseStatus.OPEN,
            "detected": date(2026, 9, 6),
            "obs": [(date(2026, 9, 6), "Grozdovi smeđih plodova na 4 grančice.", "Nije dirano do saveta agronoma.")],
            "photos": [(0, "monilija-plod.png", (112, 64, 40), "Smeđi plodovi, 6. sep")],
        },
        {
            "row": 4,
            "pos": 55,
            "title": "Lisne vaši na mladom rastu",
            "description": "Kolonije na vrhovima izdanaka oprašivača Nocchione.",
            "category": DiseaseCategory.PEST,
            "severity": DiseaseSeverity.MEDIUM,
            "status": DiseaseCaseStatus.OPEN,
            "detected": date(2026, 5, 18),
            "obs": [
                (date(2026, 5, 18), "Vaši na 6–8 vrhova, medna rosa na donjem lišću.", None),
                (date(2026, 6, 2), "Posle prskanja broj je manji, vrhovi se oporavljaju.", "Ostaje otvoreno do narednog pregleda."),
            ],
            "photos": [(0, "lisne-vasi.png", (72, 108, 64), "Vaši na vrhu, 18. maj")],
        },
        {
            "row": 9,
            "pos": 15,
            "title": "Pepelnica na listu",
            "description": "Beli premaz na gornjoj strani lista u sredini parcele.",
            "category": DiseaseCategory.DISEASE,
            "severity": DiseaseSeverity.LOW,
            "status": DiseaseCaseStatus.RESOLVED,
            "detected": date(2026, 7, 30),
            "resolved": date(2026, 8, 20),
            "obs": [
                (date(2026, 7, 30), "Pege pepelnice na 10-ak listova.", None),
                (date(2026, 8, 20), "Posle prskanja nove pege nisu nađene.", "Zatvoreno."),
            ],
            "photos": [(0, "pepelnica.png", (200, 200, 180), "Pepelnica, 30. jul")],
        },
        {
            "row": 3,
            "pos": 20,
            "title": "Ogrebotina kore od mehanizacije",
            "description": "Rana na deblu od kosačice, kalusirala tokom leta.",
            "category": DiseaseCategory.PHYSICAL_DAMAGE,
            "severity": DiseaseSeverity.LOW,
            "status": DiseaseCaseStatus.RESOLVED,
            "detected": date(2025, 6, 14),
            "resolved": date(2025, 9, 2),
            "obs": [(date(2025, 6, 14), "Sveža ogrebotina dugačka oko 12 cm.", "Premazana. Kosačica pomerena od reda.")],
            "photos": [(0, "ogrebotina.png", (92, 74, 58), "Rana na deblu, 14. jun 2025.")],
        },
        {
            "row": 12,
            "pos": 18,
            "title": "Žižak u berbi 2025.",
            "description": "Oštećeni plodovi u otkupu. Slučaj zatvoren posle berbe, program zaštite pojačan 2026.",
            "category": DiseaseCategory.PEST,
            "severity": DiseaseSeverity.MEDIUM,
            "status": DiseaseCaseStatus.RESOLVED,
            "detected": date(2025, 9, 30),
            "resolved": date(2025, 10, 15),
            "obs": [(date(2025, 9, 30), "U uzorku od 5 kg oko 6 % plodova sa rupom.", "Zabeleženo radi plana za 2026.")],
            "photos": [(0, "zizak-2025.png", (80, 50, 32), "Oštećen plod, berba 2025.")],
        },
        {
            "row": 1,
            "pos": 5,
            "title": "Polomljena grana posle vetra",
            "description": "Jaka košava u martu 2024. Grana odsečena, rana zarasla.",
            "category": DiseaseCategory.PHYSICAL_DAMAGE,
            "severity": DiseaseSeverity.LOW,
            "status": DiseaseCaseStatus.RESOLVED,
            "detected": date(2024, 3, 9),
            "resolved": date(2024, 6, 1),
            "obs": [(date(2024, 3, 9), "Grana prečnika 4 cm slomljena pri dnu.", None)],
            "photos": [(0, "vetar-grana.png", (86, 80, 70), "Polomljena grana, 9. mar 2024.")],
        },
        {
            "row": 16,
            "pos": 61,
            "title": "Suvi vrhovi, sumnja na bakteriozu",
            "description": "Sušenje vrhova na zapadnom kraju reda 16.",
            "category": DiseaseCategory.DISEASE,
            "severity": DiseaseSeverity.MEDIUM,
            "status": DiseaseCaseStatus.OPEN,
            "detected": date(2026, 8, 6),
            "obs": [(date(2026, 8, 6), "Tri vrha suva, kora ispucala.", "Upoređeno sa R14-T0038.")],
            "photos": [(0, "suvi-vrhovi.png", (108, 84, 50), "Suvi vrhovi, 6. avg")],
        },
        {
            "row": 7,
            "pos": 44,
            "title": "Deformisani plodovi, mogući nedostatak bora",
            "description": "Šuplji i krivi plodovi na jednom stablu Tonda di Giffoni. Samo opažanje.",
            "category": DiseaseCategory.NUTRIENT_DEFICIENCY,
            "severity": DiseaseSeverity.LOW,
            "status": DiseaseCaseStatus.MONITORING,
            "detected": date(2026, 8, 30),
            "obs": [(date(2026, 8, 30), "Nekoliko šupljih plodova u donjoj krošnji.", "Nije rađena analiza lista.")],
            "photos": [(0, "deformisan-plod.png", (150, 120, 80), "Deformisan plod, 30. avg")],
        },
    ]

    health = DiseaseService(db)
    touched: list[Tree] = []
    for spec in cases:
        tree = _tree_at(db, parcel.id, spec["row"], spec["pos"])
        if tree is None:
            continue
        case = DiseaseCase(
            farm_id=farm.id,
            parcel_id=parcel.id,
            row_id=tree.row_id,
            tree_id=tree.id,
            title=spec["title"],
            description=spec["description"],
            category=spec["category"],
            severity=spec["severity"],
            status=spec["status"],
            detected_on=spec["detected"],
            resolved_on=spec.get("resolved"),
            notes=spec.get("notes"),
            created_by_id=user.id,
        )
        db.add(case)
        db.flush()
        observations: list[DiseaseObservation] = []
        for observed_on, symptoms, notes in spec["obs"]:
            obs = DiseaseObservation(
                disease_case_id=case.id,
                observed_on=observed_on,
                symptoms=symptoms,
                notes=notes,
                created_by_id=user.id,
            )
            db.add(obs)
            observations.append(obs)
        db.flush()
        for obs_index, filename, color, caption in spec.get("photos", []):
            if obs_index >= len(observations):
                continue
            _placeholder_photo(db, farm.id, observations[obs_index].id, filename, color, caption, user.id)
        touched.append(tree)

    db.flush()
    for tree in touched:
        health.sync_tree_health(tree.id)
    db.flush()


def _placeholder_photo(
    db: Session,
    farm_id: object,
    observation_id: object,
    filename: str,
    color: tuple[int, int, int],
    caption: str,
    user_id: object,
) -> None:
    content = solid_png(320, 240, color)
    key = f"photos/{farm_id}/{uuid4().hex}.png"
    get_storage().put(key, content, "image/png")
    db.add(
        Photo(
            farm_id=farm_id,
            entity_type=AttachmentEntityType.OBSERVATION,
            entity_id=observation_id,
            storage_key=key,
            original_filename=filename,
            content_type="image/png",
            size_bytes=len(content),
            caption=caption,
            uploaded_by_id=user_id,
        )
    )


def _activity_on(db: Session, parcel_id: object, title: str, performed_on: date) -> Activity | None:
    return db.scalars(
        select(Activity).where(
            Activity.parcel_id == parcel_id,
            Activity.title == title,
            Activity.performed_on == performed_on,
        )
    ).first()


def _seed_harvests(db: Session, user: User, farm: Farm, parcel: Parcel) -> None:
    row_12 = db.scalars(select(Row).where(Row.parcel_id == parcel.id, Row.row_number == 12)).first()
    tree_sample = _tree_at(db, parcel.id, 12, 34)
    harvest_2024 = _activity_on(db, parcel.id, "Prva probna berba 2024.", date(2024, 9, 26))
    harvest_2025 = _activity_on(db, parcel.id, "Berba 2025.", date(2025, 9, 29))

    records = [
        {
            "on": date(2024, 9, 26),
            "scope": ScopeType.PARCEL,
            "gross": "180",
            "loss": "0",
            "moisture": "9.4",
            "category": HarvestQualityCategory.LOWER,
            "damaged": "4.5",
            "empty": "3.2",
            "notes": "Probna berba treće godine. Mali urod uz ivice redova.",
            "activity": harvest_2024,
        },
        {
            "on": date(2025, 9, 29),
            "scope": ScopeType.PARCEL,
            "gross": "1920",
            "loss": "70",
            "moisture": "8.9",
            "category": HarvestQualityCategory.STANDARD,
            "damaged": "2.8",
            "empty": "1.6",
            "notes": "Prva komercijalna berba. Sušenje u trećaku.",
            "activity": harvest_2025,
        },
        {
            "on": date(2026, 9, 10),
            "scope": ScopeType.PARCEL,
            "gross": "500",
            "loss": "20",
            "moisture": "8.5",
            "category": HarvestQualityCategory.STANDARD,
            "damaged": "2.1",
            "empty": "1.4",
            "caliber": "13-15 mm",
            "notes": "Prva tura. Berba posle tri suva dana.",
        },
        {
            "on": date(2026, 9, 15),
            "scope": ScopeType.PARCEL,
            "gross": "650",
            "loss": "30",
            "moisture": "8.2",
            "category": HarvestQualityCategory.PREMIUM,
            "damaged": "1.6",
            "empty": "1.1",
            "caliber": "15-17 mm",
            "notes": "Glavna tura. Krupniji plod.",
        },
        {
            "on": date(2026, 9, 20),
            "scope": ScopeType.PARCEL,
            "gross": "330",
            "loss": "10",
            "moisture": "9.4",
            "category": HarvestQualityCategory.STANDARD,
            "damaged": "2.8",
            "empty": "1.8",
            "notes": "Završna tura i pokupljanje ostalog ploda.",
        },
        {
            "on": date(2026, 9, 16),
            "scope": ScopeType.ROW,
            "row": row_12,
            "gross": "84",
            "loss": "4",
            "moisture": "8.3",
            "category": HarvestQualityCategory.STANDARD,
            "notes": "Kontrolno merenje reda 12. Nije deo prinosa parcele.",
        },
        {
            "on": date(2026, 9, 16),
            "scope": ScopeType.TREE,
            "tree": tree_sample,
            "gross": "4.4",
            "loss": "0.2",
            "moisture": "8.1",
            "category": HarvestQualityCategory.PREMIUM,
            "notes": "Kontrolno merenje jednog stabla. Nije deo prinosa parcele.",
        },
    ]

    for item in records:
        tree = item.get("tree")
        row = item.get("row")
        if item["scope"] == ScopeType.TREE and tree is None:
            continue
        if item["scope"] == ScopeType.ROW and row is None:
            continue
        harvested_on = item["on"]
        if db.scalar(
            select(HarvestEvent.id).where(
                HarvestEvent.parcel_id == parcel.id,
                HarvestEvent.harvested_on == harvested_on,
                HarvestEvent.scope_type == item["scope"],
                HarvestEvent.gross_quantity == Decimal(item["gross"]),
            )
        ):
            continue
        row_id = None
        tree_id = None
        if item["scope"] == ScopeType.ROW:
            row_id = row.id
        if item["scope"] == ScopeType.TREE and tree is not None:
            tree_id = tree.id
            row_id = tree.row_id
        activity = item.get("activity")
        db.add(
            HarvestEvent(
                harvested_on=harvested_on,
                scope_type=item["scope"],
                farm_id=farm.id,
                parcel_id=parcel.id,
                row_id=row_id,
                tree_id=tree_id,
                gross_quantity=Decimal(item["gross"]),
                loss_quantity=Decimal(item["loss"]),
                unit="kg",
                moisture_percent=Decimal(item["moisture"]) if item.get("moisture") else None,
                quality_category=item.get("category"),
                damaged_percent=Decimal(item["damaged"]) if item.get("damaged") else None,
                empty_nuts_percent=Decimal(item["empty"]) if item.get("empty") else None,
                size_or_caliber=item.get("caliber"),
                notes=item.get("notes"),
                activity_id=activity.id if activity is not None else None,
                created_by_id=user.id,
            )
        )
    db.flush()

