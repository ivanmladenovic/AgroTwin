"""Extensible canonical taxonomy for laboratory soil parameters.

Synonyms are matched layout-agnostically against OCR/text extraction.
New parameters can be added without schema changes (parameter_code is a string).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SoilParameterSpec:
    code: str
    label: str
    synonyms: tuple[str, ...]
    default_unit: str | None = None
    methods: tuple[str, ...] = ()


# Canonical codes — keep stable for planning; synonyms are local/lab-specific names.
SOIL_PARAMETER_TAXONOMY: tuple[SoilParameterSpec, ...] = (
    SoilParameterSpec(
        "PH",
        "pH",
        ("ph", "reakcija zemljista", "reakcija zemljišta", "aktivna kiselost", "ph kcl", "ph h2o", "ph h₂o"),
        methods=("KCL", "H2O", "CACL2"),
    ),
    SoilParameterSpec("HUMUS", "Humus", ("humus", "organska materija", "sadrzaj humusa", "sadržaj humusa"), "%"),
    SoilParameterSpec(
        "ORGANIC_CARBON",
        "Organski ugljenik",
        ("organski ugljenik", "organic carbon", "c-org", "c org", "toc"),
        "%",
    ),
    SoilParameterSpec("TOTAL_N", "Ukupan N", ("ukupan azot", "ukupni azot", "total n", "n-ukupni", "n ukupni"), "%"),
    SoilParameterSpec(
        "AVAILABLE_P",
        "Pristupačan P",
        ("p2o5", "p₂o₅", "fosfor", "pristupacan p", "pristupačan p", "al-p", "olsen p", "fosfor pentoksid"),
        "mg/100g",
        methods=("AL", "OLSEN"),
    ),
    SoilParameterSpec(
        "AVAILABLE_K",
        "Pristupačan K",
        ("k2o", "k₂o", "kalijum", "pristupacan k", "pristupačan k", "al-k", "kalijum oksid"),
        "mg/100g",
        methods=("AL",),
    ),
    SoilParameterSpec("CA", "Kalcijum", ("ca", "kalcijum", "calcium", "cao", "ca:", "ca)"), "mg/100g"),
    SoilParameterSpec("MG", "Magnezijum", ("mg", "magnezijum", "magnesium", "mgo", "mg:", "mg)"), "mg/100g"),
    SoilParameterSpec("S", "Sumpor", ("sumpor", "sulfat", "s-so4", "sumpor so4"), "mg/kg"),
    SoilParameterSpec("FE", "Gvožđe", ("gvozdje", "gvožđe", "iron", " fe ", "fe:", "fe)"), "mg/kg"),
    SoilParameterSpec("ZN", "Cink", ("cink", "zinc", " zn ", "zn:", "zn)"), "mg/kg"),
    SoilParameterSpec("B", "Bor", ("bor", "boron", " bor ", "b:", "b)"), "mg/kg"),
    SoilParameterSpec("MN", "Mangan", ("mangan", "manganese", " mn ", "mn:", "mn)"), "mg/kg"),
    SoilParameterSpec("CU", "Bakar", ("bakar", "copper", " cu ", "cu:", "cu)"), "mg/kg"),
    SoilParameterSpec("CEC", "CEC", ("cec", "kationiski kapacitet", "kationski kapacitet", "t-vrednost"), "cmol/kg"),
    SoilParameterSpec("TEXTURE", "Tekstura", ("tekstura", "mehanicki sastav", "mehanički sastav", "texture")),
    SoilParameterSpec("SAND", "Pesak", ("pesak", "sand", "krupan pesak", "sitni pesak"), "%"),
    SoilParameterSpec("SILT", "Prašina", ("prasina", "prašina", "silt", "ilovaca", "ilovača"), "%"),
    SoilParameterSpec("CLAY", "Glina", ("glina", "clay", "koloidna glina"), "%"),
)

TAXONOMY_BY_CODE = {item.code: item for item in SOIL_PARAMETER_TAXONOMY}
