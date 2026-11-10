from __future__ import annotations

from typing import Literal

AppLocale = Literal["sr", "en"]

PDF_LABELS: dict[AppLocale, dict[str, str]] = {
    "sr": {
        "generated_via": "Generisano kroz AgroTwin platformu",
        "farm": "Gazdinstvo:",
        "period": "Period:",
        "generated": "Generisano:",
        "disclaimer": (
            "Izveštaj usaglašenosti AgroTwin. Pripremljen isključivo iz evidencije sačuvane u AgroTwin. "
            "Ovaj dokument ne sertifikuje gazdinstvo i ne garantuje usklađenost sa GLOBALG.A.P. "
            "niti bilo kojim drugim standardom."
        ),
    },
    "en": {
        "generated_via": "Generated via the AgroTwin platform",
        "farm": "Farm:",
        "period": "Period:",
        "generated": "Generated:",
        "disclaimer": (
            "AgroTwin compliance report. Prepared solely from records stored in AgroTwin. "
            "This document does not certify the farm or guarantee compliance with GLOBALG.A.P. "
            "or any other standard."
        ),
    },
}


def pdf_labels(locale: str = "sr") -> dict[str, str]:
    return PDF_LABELS["en" if locale == "en" else "sr"]
