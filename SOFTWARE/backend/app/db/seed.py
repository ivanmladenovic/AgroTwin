from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.core.varieties import DEFAULT_VARIETIES
from app.models.activity import Activity
from app.models.cost import Cost
from app.models.disease import DiseaseCase, DiseaseObservation
from app.models.document import Document
from app.models.enums import (
    ActivityStatus,
    AttachmentEntityType,
    DiseaseCaseStatus,
    DiseaseCategory,
    DiseaseSeverity,
    HealthStatus,
    KnowledgeCategory,
    ScopeType,
    TreeStatus,
)
from app.models.farm import Farm
from app.models.parcel import Parcel
from app.models.photo import Photo
from app.models.row import Row
from app.models.tree import Tree
from app.models.user import User
from app.repositories.farm import FarmRepository
from app.repositories.parcel import ParcelRepository
from app.repositories.user import UserRepository
from app.schemas.parcel import ParcelCreate
from app.services.catalog import CatalogService
from app.services.disease import DiseaseService
from app.services.knowledge import KnowledgeService
from app.services.orchard import OrchardService
from app.knowledge.pdf import build_text_pdf
from app.storage import get_storage
from app.storage.png import solid_png

DEMO_EMAIL = "admin@agrotwin.rs"
DEMO_PASSWORD = "admin"
DEMO_NAME = "Ivan Mladenović"
DEMO_FARM_NAME = "Voćnjak Severna padina"
DEMO_PARCEL_MAIN = "Severna padina"
DEMO_PARCEL_NURSERY = "Rasadnik"
LEGACY_DEMO_EMAIL = "demo@agrotwin.com"
LEGACY_DEMO_NAMES = {"Demo Grower", "Demo proizvođač", "Milan Petrović"}
LEGACY_PARCEL_MAIN = "North Slope"
LEGACY_PARCEL_NURSERY = "Nursery Block"


def seed_demo_data(db: Session) -> None:
    users = UserRepository(db)
    farms = FarmRepository(db)
    parcels = ParcelRepository(db)

    user = users.get_by_email(DEMO_EMAIL) or users.get_by_email(LEGACY_DEMO_EMAIL)
    if user is None:
        user = User(
            email=DEMO_EMAIL,
            hashed_password=hash_password(DEMO_PASSWORD),
            full_name=DEMO_NAME,
            is_active=True,
            is_superuser=True,
        )
        users.add(user)
        db.flush()
    else:
        user.email = DEMO_EMAIL
        user.hashed_password = hash_password(DEMO_PASSWORD)
        if user.full_name in LEGACY_DEMO_NAMES or user.full_name != DEMO_NAME:
            user.full_name = DEMO_NAME
        user.is_active = True
        user.is_superuser = True

    existing_farms = farms.list_by_owner(user.id)
    farm = existing_farms[0] if existing_farms else None
    if farm is None:
        farm = Farm(
            owner_id=user.id,
            name=DEMO_FARM_NAME,
            description="Demo voćnjak lesnika za lokalni razvoj.",
            location_name="Srbija",
            area_hectares=Decimal("2.4000"),
        )
        farms.add(farm)
        db.flush()
    else:
        if farm.name in {"North Slope Hazel Farm"}:
            farm.name = DEMO_FARM_NAME
        if farm.location_name == "Continental Croatia":
            farm.location_name = "Srbija"
        if farm.description == "Demonstration hazelnut orchard used for local development.":
            farm.description = "Demo voćnjak lesnika za lokalni razvoj."

    orchard = OrchardService(db)
    generated = [parcel for parcel in parcels.list_by_farm(farm.id) if parcel.row_count]
    if not generated:
        for parcel in list(parcels.list_by_farm(farm.id)):
            has_rows = db.scalar(select(Row.id).where(Row.parcel_id == parcel.id).limit(1))
            if has_rows is None:
                db.delete(parcel)
        db.flush()

        nursery = orchard.create_parcel(
            user.id,
            ParcelCreate(
                farm_id=farm.id,
                name=DEMO_PARCEL_NURSERY,
                area_hectares=Decimal("0.1800"),
                row_count=6,
                trees_per_row=12,
                row_spacing_m=Decimal("4.50"),
                tree_spacing_m=Decimal("3.50"),
                default_variety="Tonda di Giffoni",
                varieties=DEFAULT_VARIETIES,
                planting_year=2024,
                starting_tree_number=1,
                notes="Mala demo parcela za interakciju i filtere.",
            ),
        )
        _apply_demo_variation(db, nursery.id, compact=True)

        main = orchard.create_parcel(
            user.id,
            ParcelCreate(
                farm_id=farm.id,
                name=DEMO_PARCEL_MAIN,
                area_hectares=Decimal("2.4000"),
                row_count=26,
                trees_per_row=73,
                row_spacing_m=Decimal("5.00"),
                tree_spacing_m=Decimal("3.50"),
                default_variety="Tonda di Giffoni",
                varieties=DEFAULT_VARIETIES,
                planting_year=2022,
                starting_tree_number=1,
                notes="Glavna parcela digitalnog dvojnika: 26 redova × 73 stabla.",
            ),
        )
        _apply_demo_variation(db, main.id, compact=False)

    for parcel in parcels.list_by_farm(farm.id):
        if parcel.name == LEGACY_PARCEL_MAIN:
            parcel.name = DEMO_PARCEL_MAIN
        elif parcel.name == LEGACY_PARCEL_NURSERY:
            parcel.name = DEMO_PARCEL_NURSERY
        parcel.code = orchard._unique_code(farm.id, parcel.name, exclude_id=parcel.id)
    db.flush()

    CatalogService(db).upsert_defaults()
    _seed_demo_journal(db, user, farm)
    _seed_demo_health(db, user, farm)
    _seed_demo_knowledge(db, user, farm)
    from app.db.seed_kusiljevo import seed_kusiljevo_presentation

    seed_kusiljevo_presentation(db, user, farm)
    db.commit()


def _demo_main_parcel(db: Session, farm_id: object) -> Parcel | None:
    return db.scalars(
        select(Parcel).where(
            Parcel.farm_id == farm_id,
            Parcel.name.in_((DEMO_PARCEL_MAIN, LEGACY_PARCEL_MAIN)),
        )
    ).first()


def _apply_demo_variation(db: Session, parcel_id: object, compact: bool) -> None:
    stmt = (
        select(Tree, Row.row_number)
        .join(Row, Tree.row_id == Row.id)
        .where(Tree.parcel_id == parcel_id)
    )
    for tree, row_number in db.execute(stmt):
        if row_number == 1:
            tree.planting_year = 2022 if not compact else 2024
        if row_number == 14 and tree.position_in_row == 38:
            tree.planting_year = 2025
            tree.variety = "Tonda di Giffoni"
        if compact and row_number == 2 and tree.position_in_row == 5:
            tree.planting_year = 2025
            tree.variety = "Tonda di Giffoni"

        key = row_number * 1000 + tree.position_in_row
        if key % 61 == 0:
            tree.health_status = HealthStatus.MONITORING
        elif key % 89 == 0:
            tree.health_status = HealthStatus.ISSUE
        elif key % 97 == 0:
            tree.health_status = HealthStatus.UNKNOWN

        if row_number == 3 and tree.position_in_row in {1, 2}:
            tree.status = TreeStatus.REMOVED
            tree.health_status = HealthStatus.UNKNOWN
        if row_number == 5 and tree.position_in_row == 8:
            tree.status = TreeStatus.REPLACED
            tree.planting_year = 2025

    db.flush()


def _seed_demo_journal(db: Session, user: User, farm: Farm) -> None:
    existing = db.scalar(select(Activity.id).where(Activity.farm_id == farm.id).limit(1))
    if existing is not None:
        return

    parcel = _demo_main_parcel(db, farm.id)
    if parcel is None:
        return

    row_14 = db.scalars(select(Row).where(Row.parcel_id == parcel.id, Row.row_number == 14)).first()
    if row_14 is None:
        return

    tree = db.scalars(
        select(Tree).where(Tree.row_id == row_14.id, Tree.position_in_row == 38)
    ).first()
    if tree is None:
        return

    catalogs = CatalogService(db)
    types = {item.slug: item for item in catalogs.catalogs.list_activity_types()}
    categories = {item.slug: item for item in catalogs.catalogs.list_cost_categories()}

    spraying = Activity(
        activity_type_id=types["spraying"].id,
        title="Prskanje",
        description="Prskanje cele parcele",
        performed_on=date(2026, 9, 15),
        status=ActivityStatus.COMPLETED,
        quantity=Decimal("400"),
        unit="L",
        notes="Prolaz zaštite bilja po celoj krošnji.",
        created_by_id=user.id,
        scope_type=ScopeType.PARCEL,
        farm_id=farm.id,
        parcel_id=parcel.id,
    )
    fertilization = Activity(
        activity_type_id=types["fertilization"].id,
        title="Đubrenje Reda 14",
        description="Đubrenje Reda 14",
        performed_on=date(2026, 9, 10),
        status=ActivityStatus.COMPLETED,
        quantity=Decimal("80"),
        unit="kg",
        created_by_id=user.id,
        scope_type=ScopeType.ROW,
        farm_id=farm.id,
        parcel_id=parcel.id,
        row_id=row_14.id,
    )
    irrigation = Activity(
        activity_type_id=types["irrigation"].id,
        title="Navodnjavanje",
        description="Kap po kap na Severnoj padini",
        performed_on=date(2026, 9, 3),
        status=ActivityStatus.COMPLETED,
        quantity=Decimal("18"),
        unit="m3",
        created_by_id=user.id,
        scope_type=ScopeType.PARCEL,
        farm_id=farm.id,
        parcel_id=parcel.id,
    )
    treatment = Activity(
        activity_type_id=types["disease_treatment"].id,
        title=f"Tretman bolesti stabla {tree.public_id}",
        description="Lokalni tretman posle pregleda",
        performed_on=date(2026, 8, 28),
        status=ActivityStatus.COMPLETED,
        created_by_id=user.id,
        scope_type=ScopeType.TREE,
        farm_id=farm.id,
        parcel_id=parcel.id,
        row_id=row_14.id,
        tree_id=tree.id,
    )
    inspection = Activity(
        activity_type_id=types["inspection"].id,
        title=f"Pregled stabla {tree.public_id}",
        description="Vizuelni pregled krošnje i debla",
        performed_on=date(2026, 9, 14),
        status=ActivityStatus.COMPLETED,
        created_by_id=user.id,
        scope_type=ScopeType.TREE,
        farm_id=farm.id,
        parcel_id=parcel.id,
        row_id=row_14.id,
        tree_id=tree.id,
    )
    pruning = Activity(
        activity_type_id=types["pruning"].id,
        title=f"Rezidba stabla {tree.public_id}",
        description=f"Rezidba stabla {tree.public_id}",
        performed_on=date(2026, 8, 20),
        status=ActivityStatus.COMPLETED,
        created_by_id=user.id,
        scope_type=ScopeType.TREE,
        farm_id=farm.id,
        parcel_id=parcel.id,
        row_id=row_14.id,
        tree_id=tree.id,
    )
    db.add_all([spraying, fertilization, irrigation, treatment, inspection, pruning])
    db.flush()

    db.add_all(
        [
            Cost(
                amount=Decimal("120.00"),
                currency="EUR",
                incurred_on=date(2026, 9, 15),
                description="Sredstvo za zaštitu bilja",
                cost_category_id=categories["plant_protection"].id,
                activity_id=spraying.id,
                scope_type=ScopeType.PARCEL,
                farm_id=farm.id,
                parcel_id=parcel.id,
                created_by_id=user.id,
            ),
            Cost(
                amount=Decimal("80.00"),
                currency="EUR",
                incurred_on=date(2026, 9, 15),
                description="Rad",
                cost_category_id=categories["labor"].id,
                activity_id=spraying.id,
                scope_type=ScopeType.PARCEL,
                farm_id=farm.id,
                parcel_id=parcel.id,
                created_by_id=user.id,
            ),
            Cost(
                amount=Decimal("30.00"),
                currency="EUR",
                incurred_on=date(2026, 9, 15),
                description="Gorivo",
                cost_category_id=categories["fuel"].id,
                activity_id=spraying.id,
                scope_type=ScopeType.PARCEL,
                farm_id=farm.id,
                parcel_id=parcel.id,
                created_by_id=user.id,
            ),
            Cost(
                amount=Decimal("35.00"),
                currency="EUR",
                incurred_on=date(2026, 9, 10),
                description="Đubrivo za Red 14",
                cost_category_id=categories["fertilizers"].id,
                activity_id=fertilization.id,
                scope_type=ScopeType.ROW,
                farm_id=farm.id,
                parcel_id=parcel.id,
                row_id=row_14.id,
                created_by_id=user.id,
            ),
            Cost(
                amount=Decimal("12.00"),
                currency="EUR",
                incurred_on=date(2026, 9, 3),
                description="Voda za navodnjavanje",
                cost_category_id=categories["water"].id,
                activity_id=irrigation.id,
                scope_type=ScopeType.PARCEL,
                farm_id=farm.id,
                parcel_id=parcel.id,
                created_by_id=user.id,
            ),
            Cost(
                amount=Decimal("18.00"),
                currency="EUR",
                incurred_on=date(2026, 8, 28),
                description="Sredstvo za lokalni tretman",
                cost_category_id=categories["plant_protection"].id,
                activity_id=treatment.id,
                scope_type=ScopeType.TREE,
                farm_id=farm.id,
                parcel_id=parcel.id,
                row_id=row_14.id,
                tree_id=tree.id,
                created_by_id=user.id,
            ),
            Cost(
                amount=Decimal("22.00"),
                currency="EUR",
                incurred_on=date(2026, 8, 20),
                description="Rad na rezidbi",
                cost_category_id=categories["labor"].id,
                activity_id=pruning.id,
                scope_type=ScopeType.TREE,
                farm_id=farm.id,
                parcel_id=parcel.id,
                row_id=row_14.id,
                tree_id=tree.id,
                created_by_id=user.id,
            ),
        ]
    )
    db.flush()


def _seed_demo_health(db: Session, user: User, farm: Farm) -> None:
    parcel = _demo_main_parcel(db, farm.id)
    if parcel is None:
        return
    row_14 = db.scalars(select(Row).where(Row.parcel_id == parcel.id, Row.row_number == 14)).first()
    if row_14 is None:
        return

    def tree_at(position: int) -> Tree | None:
        return db.scalars(select(Tree).where(Tree.row_id == row_14.id, Tree.position_in_row == position)).first()

    blight_tree = tree_at(38)
    weevil_tree = tree_at(1)
    nutrient_tree = tree_at(10)
    damage_tree = tree_at(20)
    if blight_tree is None or weevil_tree is None or nutrient_tree is None or damage_tree is None:
        return

    observation_count = db.scalar(
        select(func.count())
        .select_from(DiseaseObservation)
        .join(DiseaseCase, DiseaseObservation.disease_case_id == DiseaseCase.id)
        .where(DiseaseCase.farm_id == farm.id)
    )
    if observation_count:
        return

    existing = db.scalars(select(DiseaseCase).where(DiseaseCase.farm_id == farm.id)).all()
    blight = next(
        (item for item in existing if any(word in (item.title or "").lower() for word in ("blight", "rakovina"))),
        None,
    )
    if blight is None:
        blight = DiseaseCase(
            farm_id=farm.id,
            parcel_id=parcel.id,
            row_id=row_14.id,
            tree_id=blight_tree.id,
            title="Sumnja na rakovinu lesnika",
            description="Tokom pregleda uočene su lezije slične rakovima. Ovo je opažanje, a ne potvrđena dijagnoza.",
            category=DiseaseCategory.DISEASE,
            severity=DiseaseSeverity.MEDIUM,
            status=DiseaseCaseStatus.MONITORING,
            detected_on=date(2026, 8, 28),
            notes="Držite ovo stablo u skupu za praćenje do berbe.",
            created_by_id=user.id,
        )
        db.add(blight)
        db.flush()
    else:
        blight.row_id = row_14.id
        blight.tree_id = blight_tree.id
        blight.title = "Sumnja na rakovinu lesnika"
        blight.description = (
            "Tokom pregleda uočene su lezije slične rakovima. Ovo je opažanje, a ne potvrđena dijagnoza."
        )
        blight.category = DiseaseCategory.DISEASE
        blight.severity = DiseaseSeverity.MEDIUM
        blight.status = DiseaseCaseStatus.MONITORING
        blight.created_by_id = user.id
        db.flush()

    weevil = DiseaseCase(
        farm_id=farm.id,
        parcel_id=parcel.id,
        row_id=row_14.id,
        tree_id=weevil_tree.id,
        title="Sumnja na ishranjivanje žiška na plodovima",
        description="Rupe na razvijajućim plodovima u donjoj krošnji. Zabeleženo kao opažanje štetočine do potvrde.",
        category=DiseaseCategory.PEST,
        severity=DiseaseSeverity.HIGH,
        status=DiseaseCaseStatus.OPEN,
        detected_on=date(2026, 9, 8),
        created_by_id=user.id,
    )
    nutrient = DiseaseCase(
        farm_id=farm.id,
        parcel_id=parcel.id,
        row_id=row_14.id,
        tree_id=nutrient_tree.id,
        title="Bledo lišće, mogući nedostatak hraniva",
        description="Međužilno žućenje na mlađem lišću. Samo opažanje.",
        category=DiseaseCategory.NUTRIENT_DEFICIENCY,
        severity=DiseaseSeverity.LOW,
        status=DiseaseCaseStatus.MONITORING,
        detected_on=date(2026, 9, 5),
        created_by_id=user.id,
    )
    damage = DiseaseCase(
        farm_id=farm.id,
        parcel_id=parcel.id,
        row_id=row_14.id,
        tree_id=damage_tree.id,
        title="Ogrebotina kore od mehanizacije",
        description="Fizička rana na deblu, sada kalusirana.",
        category=DiseaseCategory.PHYSICAL_DAMAGE,
        severity=DiseaseSeverity.LOW,
        status=DiseaseCaseStatus.RESOLVED,
        detected_on=date(2026, 7, 12),
        resolved_on=date(2026, 8, 30),
        created_by_id=user.id,
    )
    db.add_all([weevil, nutrient, damage])
    db.flush()

    blight_first = DiseaseObservation(
        disease_case_id=blight.id,
        observed_on=date(2026, 8, 28),
        symptoms="Rakovi na grančicama i rasuto žuto lišće na istočnoj strani.",
        notes="Prva terenska beleška. Nije laboratorijska potvrda.",
        created_by_id=user.id,
    )
    blight_second = DiseaseObservation(
        disease_case_id=blight.id,
        observed_on=date(2026, 9, 10),
        symptoms="Izgleda da su se lezije proširile na još dve grane.",
        notes="I dalje se prati. Tretman još nije menjan.",
        created_by_id=user.id,
    )
    blight_third = DiseaseObservation(
        disease_case_id=blight.id,
        observed_on=date(2026, 9, 14),
        symptoms="Istočna krošnja se i dalje proređuje; danas nisu nađeni novi rakovi.",
        created_by_id=user.id,
    )
    weevil_obs = DiseaseObservation(
        disease_case_id=weevil.id,
        observed_on=date(2026, 9, 8),
        symptoms="Više plodova sa izlaznim rupama na donjoj južnoj strani.",
        notes="Opažanje visoke ozbiljnosti, pa je stablo na mapi označeno kao problem.",
        created_by_id=user.id,
    )
    nutrient_obs = DiseaseObservation(
        disease_case_id=nutrient.id,
        observed_on=date(2026, 9, 5),
        symptoms="Bledo mlado lišće, mogući nedostatak azota.",
        created_by_id=user.id,
    )
    damage_obs = DiseaseObservation(
        disease_case_id=damage.id,
        observed_on=date(2026, 7, 12),
        symptoms="Sveža ogrebotina kore dugačka oko 12 cm.",
        created_by_id=user.id,
    )
    db.add_all([blight_first, blight_second, blight_third, weevil_obs, nutrient_obs, damage_obs])
    db.flush()

    _placeholder_photo(db, farm.id, blight_first.id, "canopy-east.png", (120, 92, 48), "Istočna krošnja, 28. avg", user.id)
    _placeholder_photo(db, farm.id, blight_first.id, "twig-canker.png", (140, 70, 48), "Lezija na grančici, 28. avg", user.id)
    _placeholder_photo(db, farm.id, blight_second.id, "branch-spread.png", (110, 78, 42), "Širenje na granama, 10. sep", user.id)
    _placeholder_photo(db, farm.id, blight_third.id, "follow-up.png", (96, 88, 52), "Kontrolna krošnja, 14. sep", user.id)
    _placeholder_photo(db, farm.id, weevil_obs.id, "nut-holes.png", (88, 54, 36), "Plodovi sa rupama, 8. sep", user.id)
    _placeholder_photo(db, farm.id, nutrient_obs.id, "pale-leaves.png", (168, 176, 92), "Bledo lišće, 5. sep", user.id)
    _placeholder_photo(db, farm.id, damage_obs.id, "bark-scrape.png", (92, 74, 58), "Rana na deblu, 12. jul", user.id)

    health = DiseaseService(db)
    for item in (blight_tree, weevil_tree, nutrient_tree, damage_tree):
        health.sync_tree_health(item.id)
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


def _seed_demo_knowledge(db: Session, user: User, farm: Farm) -> None:
    existing = db.scalar(select(Document.id).where(Document.farm_id == farm.id).limit(1))
    if existing is not None:
        return
    service = KnowledgeService(db)
    manuals = [
        (
            "Terenske beleške za lesnik posle nekoliko kišnih dana",
            KnowledgeCategory.OTHER,
            [
                (
                    "Pregled posle kiše",
                    "Posle nekoliko kišnih dana, prođite voćnjak kada zemlja prima čizmu bez razmazivanja. "
                    "Proverite niske delove zbog stajaće vode i stabla kojima je vrat još mokar. Pogledajte mlado lišće zbog "
                    "žućenja koje se pojavilo tek posle kiše, i plodove na zemlji. Ne prskajte sredstva za zaštitu "
                    "bilja po mokrom lišću; sačekajte da se krošnja osuši. Ovaj vodič ne nabraja proizvode ni doze.",
                ),
                (
                    "Šta zabeležiti",
                    "Zabeležite koji redovi zadržavaju vodu, koja stabla su bacila plodove i da li rakovi izgledaju mokro ili se šire. "
                    "Uporedite Red 14 i druge duge redove jer su na padini. Opažanja upišite u AgroTwin "
                    "umesto da na terenu nagađate dijagnozu.",
                ),
            ],
        ),
        (
            "Terenske beleške o bolestima i štetočinama lesnika",
            KnowledgeCategory.PLANT_PROTECTION,
            [
                (
                    "Rakovi na izdancima",
                    "Rakovina lesnika i druge bolesti sa rakovima mogu se pokazati kao ulegnute lezije na grančicama, suvi izdanci "
                    "i proređivanje jedne strane krošnje. Fotografija lezije nije laboratorijska potvrda. "
                    "Obeležite stablo, napravite datirane fotografije i pitajte savetnika pre rezanja ili tretmana.",
                ),
                (
                    "Insekti koji se hrane plodovima",
                    "Žižak lesnika i slične štetočine mogu ostaviti izlazne rupe na razvijajućim plodovima. Prebrojte oštećene plodove na "
                    "donjoj krošnji i na zemlji. Ne pretpostavljajte da je svaki plod sa rupom oštećenje od žiška. Držite ovo kao "
                    "opažanje dok savetnik ne potvrdi štetočinu.",
                ),
            ],
        ),
        (
            "Politika ishrane i zaštite bilja",
            KnowledgeCategory.NUTRITION_GUIDE,
            [
                (
                    "Bledo lišće",
                    "Međužilno žućenje na mladom lišću može biti problem hraniva, zamočvarenje ili oboje. Posle kiše "
                    "prvo proverite vlažnost zemljišta. Bled list sam po sebi nije dijagnoza nedostatka azota.",
                ),
                (
                    "Sredstva za zaštitu bilja",
                    "AgroTwin ne sme da izmišlja nazive proizvoda, doze ni norme primene. Ako se razgovara o tretmanu, "
                    "proizvođač treba da koristi samo registrovane etikete za ovaj voćnjak i lokalna pravila. Ako ovaj priručnik "
                    "ne sadrži proizvod, recite da baza znanja nije dovoljna.",
                ),
            ],
        ),
    ]
    for title, category, sections in manuals:
        pdf = build_text_pdf(title, sections)
        service.create_and_ingest(
            user.id,
            filename=f"{title.lower().replace(' ', '-')}.pdf",
            content_type="application/pdf",
            content=pdf,
            title=title,
            category=category,
            description="Demo priručnik za lokalne RAG testove.",
            uploaded_by_id=user.id,
        )

