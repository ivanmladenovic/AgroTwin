"""Controlled Agriser taxonomy, synonyms and query routing.

This is metadata for retrieval. It does not invent agronomic facts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re

PARSER_VERSION = "agrotwin-kb-1.0"
OCR_VERSION = "tesseract"
DEFAULT_LANGUAGE = "sr"
CROP = "Leska"
PUBLISHER = "Agriser"

INSUFFICIENT_EVIDENCE_MESSAGE = (
    "Na osnovu dostupnih Agriser priručnika ne mogu pouzdano da utvrdim odgovor. "
    "Preporučujem da se proveri sa stručnim agronomom."
)
OUT_OF_SCOPE_MESSAGE = "To nije informacija koja se nalazi u dostupnoj AgroTwin bazi znanja."
PRODUCT_GUESS_MESSAGE = (
    "U dostupnim Agriser priručnicima nisam pronašao dovoljno pouzdanu informaciju za ovu preporuku. "
    "Preporučujem da se proveri sa stručnim agronomom."
)

SYNONYMS: dict[str, tuple[str, ...]] = {
    "đubrenje": ("gnojidba", "fertilizacija", "prihrana", "dubrenje", "djubrenje"),
    "đubrivo": ("gnojivo", "fertilizer", "dubrivo", "djubrivo"),
    "leska": ("lešnik", "lesnik", "leška", "hazelnut", "corylus"),
    "bolest": ("oboljenje", "oboljenja", "bolesti"),
    "štetočina": ("stetocina", "štetni insekt", "insekt"),
    "rezidba": ("orezivanje", "orezivanje", "obrezivanje", "rezanje"),
    "navodnjavanje": ("zalivanje", "zalijevanje", "irigacija", "irrigation"),
    "kalijum": ("kalij", "potassium", "k2o", "k+"),
    "azot": ("dušik", "dusik", "nitrogen"),
    "bor": ("boron",),
    "fosfor": ("phosphorus", "p2o5", "fosfat"),
    "mraz": ("frost", "izmrzavanje", "smrzavanje"),
    "grad": ("hail", "gradobit", "od grada"),
    "zabarivanje": ("zamočvarenje", "zamocvarenje", "waterlogging", "stajaća voda"),
    "sadnja": ("sadjenje", "sađenje", "sadjenje", "planting"),
    "rastojanje": ("razmak", "spacing", "rastojanja"),
    "zemljište": ("zemljiste", "tlo", "soil"),
}


@dataclass(frozen=True)
class TopicSpec:
    key: str
    labels: tuple[str, ...]
    keywords: tuple[str, ...]


@dataclass(frozen=True)
class DomainSpec:
    key: str
    document_key: str
    topics: tuple[TopicSpec, ...]


@dataclass(frozen=True)
class ManualSpec:
    key: str
    title: str
    filename_contains: tuple[str, ...]
    category: str
    domain: str
    sections: tuple[str, ...]


MANUALS: tuple[ManualSpec, ...] = (
    ManualSpec(
        key="nutrition",
        title="Priručnik - Ishrana leske",
        filename_contains=("ishrana",),
        category="nutrition_guide",
        domain="nutrition",
        sections=(
            "Osnovna hraniva i njihova uloga u uzgoju leske",
            "Makroelementi",
            "Mikroelementi",
            "Đubrenje",
            "Pre sadnje",
            "Nakon sadnje",
            "Načini primene đubriva",
            "Analize zemljišta",
        ),
    ),
    ManualSpec(
        key="cultivation",
        title="Priručnik - Uzgajanje leske",
        filename_contains=("uzgajanje",),
        category="other",
        domain="cultivation",
        sections=(
            "Analiza zemljišta i klime",
            "Zasnovanje voćnjaka",
            "Priprema zemljišta",
            "Mehanizovane operacije",
            "Đubrenje pre sadnje",
            "Planiranje sadnje i sadnja",
            "Izbor položaja zasada i sorte",
            "Kvalitet sadnica i čuvanje do sadnje",
            "Određivanje rastojanja i sadnja",
            "Dodatne investicije pri podizanju zasada",
            "Održavanje voćnjaka",
            "Rezidba",
            "Održavanje zemljišta",
            "Navodnjavanje",
        ),
    ),
    ManualSpec(
        key="protection",
        title="Priručnik - Zaštita leske",
        filename_contains=("zastita", "zaštita"),
        category="plant_protection",
        domain="plant_protection",
        sections=(
            "Štetne vrste insekata i bolesti",
            "Insekti i grinje",
            "Gljivična oboljenja",
            "Bakterijska oboljenja",
            "Virusna oboljenja",
            "Fiziološki poremećaj",
            "Štete nastale uticajem ekstremnih vremenskih uslova",
            "Mraz",
            "Grad",
            "Zabarivanje",
            "Dobra praksa",
            "Kalendar zaštite",
            "Za stabla u rodu",
            "Za mlada stabla",
        ),
    ),
)

DOMAINS: tuple[DomainSpec, ...] = (
    DomainSpec(
        "nutrition",
        "nutrition",
        (
            TopicSpec("macroelements", ("Makroelementi",), ("azot", "fosfor", "kalijum", "kalcijum", "magnezijum", "sumpor", "makro")),
            TopicSpec("microelements", ("Mikroelementi",), ("bor", "cink", "gvožđe", "mangan", "bakar", "molibden", "mikro")),
            TopicSpec("fertilization", ("Đubrenje", "Pre sadnje", "Nakon sadnje"), ("đubren", "prihran", "pre sadnje", "nakon sadnje", "primena đubr")),
            TopicSpec("soil_analysis", ("Analize zemljišta",), ("analiza zemljišta", "ph", "agrohemijsk")),
        ),
    ),
    DomainSpec(
        "cultivation",
        "cultivation",
        (
            TopicSpec("soil", ("Analiza zemljišta i klime",), ("zemljišt", "tlo", "klima")),
            TopicSpec("orchard_establishment", ("Zasnovanje voćnjaka",), ("zasnivan", "podizanj", "zasad")),
            TopicSpec("soil_preparation", ("Priprema zemljišta",), ("priprem", "oranje", "podrivanje")),
            TopicSpec("mechanization", ("Mehanizovane operacije",), ("mehaniz", "traktor")),
            TopicSpec("preplant_fertilization", ("Đubrenje pre sadnje",), ("đubrenje pre", "pre sadnje")),
            TopicSpec("planting", ("Planiranje sadnje i sadnja", "Određivanje rastojanja i sadnja"), ("sadnj", "sadnic")),
            TopicSpec("cultivar", ("Izbor položaja zasada i sorte",), ("sort", "kultivar", "tonda")),
            TopicSpec("seedlings", ("Kvalitet sadnica i čuvanje do sadnje",), ("sadnic", "čuvanje")),
            TopicSpec("spacing", ("Određivanje rastojanja i sadnja",), ("rastojan", "razmak", "sklop")),
            TopicSpec("orchard_investment", ("Dodatne investicije pri podizanju zasada",), ("investic", "trošak podiz")),
        ),
    ),
    DomainSpec(
        "orchard_maintenance",
        "cultivation",
        (
            TopicSpec("pruning", ("Rezidba",), ("rezidb", "oreziv", "obrez")),
            TopicSpec("soil_management", ("Održavanje zemljišta",), ("održavanje zemljišta", "malč", "trava")),
            TopicSpec("irrigation", ("Navodnjavanje",), ("navodnjav", "zaliv", "irigac", "kap po kap")),
        ),
    ),
    DomainSpec(
        "plant_protection",
        "protection",
        (
            TopicSpec("insects", ("Insekti i grinje",), ("insekt", "žižak", "stetoc", "štetoč")),
            TopicSpec("mites", ("Insekti i grinje",), ("grinj", "mite")),
            TopicSpec("fungal_diseases", ("Gljivična oboljenja",), ("gljiv", "monilia", "pepelnica", "antraknoz")),
            TopicSpec("bacterial_diseases", ("Bakterijska oboljenja",), ("bakter",)),
            TopicSpec("viral_diseases", ("Virusna oboljenja",), ("virus",)),
            TopicSpec("physiological_disorders", ("Fiziološki poremećaj",), ("fiziološk", "poremećaj")),
        ),
    ),
    DomainSpec(
        "environmental_damage",
        "protection",
        (
            TopicSpec("frost", ("Mraz", "Štete od mraza, grada i zabarivanja"), ("mraz", "izmrz", "frost", "prolecni mraz", "prolećni mraz")),
            TopicSpec("hail", ("Grad", "Štete od mraza, grada i zabarivanja"), ("gradobit", "hail", "od grada", "štete od grada", "gradom")),
            TopicSpec("waterlogging", ("Zabarivanje", "Štete od mraza, grada i zabarivanja"), ("zabariv", "zamočvar", "stajać")),
        ),
    ),
    DomainSpec(
        "good_practice",
        "protection",
        (TopicSpec("good_practice", ("Dobra praksa", "Dobra proizvodna praksa", "Tehnologija tretmana"), ("dobra praksa", "dobra proizvodna", "higijena zasada", "tehnologija tretmana")),),
    ),
    DomainSpec(
        "protection_calendar",
        "protection",
        (
            TopicSpec("productive_trees", ("Za stabla u rodu", "Kalendar zaštite", "Kalendar zaštite leske", "Zaštita zasada u rodu"), ("kalendar", "stabla u rodu", "zasada u rodu", "orijentaci", "pragovima")),
            TopicSpec("young_trees", ("Za mlada stabla", "Kalendar zaštite", "Zaštita mladih zasada"), ("mlada stabla", "mlado stablo", "mladih zasada", "kalendar")),
        ),
    ),
)

OUT_OF_SCOPE_TERMS = (
    "francusk",
    "glavni grad",
    "paris",
    "fudbal",
    "bitcoin",
    "programiran",
    "javascript",
)
COMMERCIAL_TERMS = ("cena", "cijena", "price", "kupov", "prodaj", "katalog proizvoda")
AGRONOMY_HINTS = (
    "lesk",
    "lešnik",
    "lesnik",
    "đubr",
    "dubr",
    "prihran",
    "azot",
    "kalij",
    "bor",
    "fosfor",
    "rezid",
    "sadnj",
    "navodn",
    "mraz",
    "bolest",
    "insekt",
    "gljiv",
    "zemlji",
    "zaštit",
    "zastit",
    "ishran",
    "uzgaj",
    "rastojan",
    "kalendar",
    "zabariv",
    "mikro",
    "makro",
    "hraniv",
)


@dataclass
class QueryRoute:
    question: str
    out_of_scope: bool = False
    commercial: bool = False
    document_keys: list[str] = field(default_factory=list)
    domains: list[str] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)
    sections: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)


def fold(text: str) -> str:
    table = str.maketrans(
        {
            "Č": "c",
            "č": "c",
            "Ć": "c",
            "ć": "c",
            "Š": "s",
            "š": "s",
            "Ž": "z",
            "ž": "z",
            "Đ": "dj",
            "đ": "dj",
        }
    )
    return (text or "").translate(table).lower()


def expand_query_terms(question: str) -> list[str]:
    folded = fold(question)
    terms = {folded}
    for canonical, variants in SYNONYMS.items():
        if fold(canonical) in folded or any(fold(item) in folded for item in variants):
            terms.add(fold(canonical))
            terms.update(fold(item) for item in variants)
    return [item for item in terms if item]


def classify_query(question: str) -> QueryRoute:
    text = question.strip()
    folded = fold(text)
    route = QueryRoute(question=text, keywords=expand_query_terms(text))
    if any(term in folded for term in OUT_OF_SCOPE_TERMS) and not any(hint in folded for hint in AGRONOMY_HINTS):
        route.out_of_scope = True
        return route
    if any(term in folded for term in COMMERCIAL_TERMS) and not any(hint in folded for hint in AGRONOMY_HINTS):
        route.commercial = True
        return route

    scored: list[tuple[int, DomainSpec, TopicSpec]] = []
    for domain in DOMAINS:
        for topic in domain.topics:
            hits = sum(1 for keyword in topic.keywords if _keyword_hit(fold(keyword), folded))
            if hits:
                scored.append((hits, domain, topic))
    scored.sort(key=lambda item: item[0], reverse=True)
    for hits, domain, topic in scored:
        if domain.key not in route.domains:
            route.domains.append(domain.key)
        if domain.document_key not in route.document_keys:
            route.document_keys.append(domain.document_key)
        if topic.key not in route.topics:
            route.topics.append(topic.key)
        for label in topic.labels:
            if label not in route.sections:
                route.sections.append(label)

    if "ishran" in folded or "nedostat" in folded or "hraniv" in folded:
        _ensure_document(route, "nutrition")
    if "uzgaj" in folded or "sadnj" in folded or "rezid" in folded or "navodn" in folded:
        _ensure_document(route, "cultivation")
    if "zastit" in folded or "bolest" in folded or "insekt" in folded or "mraz" in folded:
        _ensure_document(route, "protection")
    if "otpornost" in folded or "zdravlj" in folded:
        _ensure_document(route, "nutrition")
        _ensure_document(route, "protection")
        if "nutrition" not in route.domains:
            route.domains.append("nutrition")
        if "plant_protection" not in route.domains:
            route.domains.append("plant_protection")
    if not route.document_keys and any(hint in folded for hint in AGRONOMY_HINTS):
        route.document_keys = [item.key for item in MANUALS]
    return route


def _keyword_hit(needle: str, folded: str) -> bool:
    if not needle:
        return False
    if len(needle) <= 2:
        return re.search(rf"(?<![a-z0-9]){re.escape(needle)}(?![a-z0-9])", folded) is not None
    return needle in folded


def _ensure_document(route: QueryRoute, key: str) -> None:
    if key not in route.document_keys:
        route.document_keys.append(key)


def match_manual(filename: str, title: str) -> ManualSpec | None:
    blob = fold(f"{filename} {title}")
    for manual in MANUALS:
        if any(fold(token) in blob for token in manual.filename_contains):
            return manual
    return None


def heading_catalog() -> list[tuple[str, str, str, str]]:
    """(heading, document_key, domain, topic) for structure assignment."""
    rows: list[tuple[str, str, str, str]] = []
    for domain in DOMAINS:
        for topic in domain.topics:
            for label in topic.labels:
                rows.append((label, domain.document_key, domain.key, topic.key))
    return rows
