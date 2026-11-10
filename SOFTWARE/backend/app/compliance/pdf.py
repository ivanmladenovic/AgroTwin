from __future__ import annotations

import io
from functools import lru_cache
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.compliance.definitions import DISCLAIMER, GENERATED_VIA
from app.compliance.labels import pdf_labels
from app.compliance.formatting import format_datetime, format_display_value
from app.schemas.compliance import ComplianceReportResult

_ASSETS = Path(__file__).resolve().parent / "assets"
_FONTS = Path(__file__).resolve().parent / "fonts"
_LOGO_PATH = _ASSETS / "agrotwin-logo.png"
_FONT_REGULAR = "AgroTwinSans"
_FONT_BOLD = "AgroTwinSans-Bold"

BRAND_GREEN = colors.HexColor("#1F6B4A")
HEADER_BG = colors.HexColor("#E8F2EC")
GRID = colors.HexColor("#C5D5CC")
MUTED = colors.HexColor("#4B5563")


@lru_cache(maxsize=1)
def _register_fonts() -> tuple[str, str]:
    regular = _FONTS / "DejaVuSans.ttf"
    bold = _FONTS / "DejaVuSans-Bold.ttf"
    if not regular.exists() or not bold.exists():
        # Fallback — Latin-1 only; prefer bundled DejaVu in production.
        return "Helvetica", "Helvetica-Bold"
    if _FONT_REGULAR not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(_FONT_REGULAR, str(regular)))
        pdfmetrics.registerFont(TTFont(_FONT_BOLD, str(bold)))
    return _FONT_REGULAR, _FONT_BOLD


def render_report_pdf(
    result: ComplianceReportResult, *, landscape_mode: bool = True, locale: str = "sr"
) -> bytes:
    labels = pdf_labels(locale)
    generated_via = labels["generated_via"]
    disclaimer_text = result.meta.disclaimer or labels["disclaimer"] or DISCLAIMER
    font_regular, font_bold = _register_fonts()
    buffer = io.BytesIO()
    pagesize = landscape(A4) if landscape_mode else A4
    doc = SimpleDocTemplate(
        buffer,
        pagesize=pagesize,
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        topMargin=14 * mm,
        bottomMargin=18 * mm,
        title=result.meta.title,
        author="AgroTwin",
    )
    styles = getSampleStyleSheet()
    brand_style = ParagraphStyle(
        "Brand",
        parent=styles["Normal"],
        fontName=font_bold,
        fontSize=14,
        leading=17,
        textColor=BRAND_GREEN,
        alignment=TA_LEFT,
    )
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Normal"],
        fontName=font_bold,
        fontSize=12,
        leading=15,
        spaceAfter=2,
        textColor=colors.HexColor("#111827"),
        alignment=TA_LEFT,
    )
    meta_style = ParagraphStyle(
        "ReportMeta",
        parent=styles["Normal"],
        fontName=font_regular,
        fontSize=8,
        leading=11,
        textColor=MUTED,
    )
    cell_style = ParagraphStyle(
        "Cell",
        parent=styles["Normal"],
        fontName=font_regular,
        fontSize=7,
        leading=9,
        textColor=colors.HexColor("#1F2937"),
    )
    header_cell_style = ParagraphStyle(
        "HeaderCell",
        parent=cell_style,
        fontName=font_bold,
        textColor=colors.HexColor("#14532D"),
    )
    disclaimer_style = ParagraphStyle(
        "Disclaimer",
        parent=styles["Normal"],
        fontName=font_regular,
        fontSize=7,
        leading=9,
        textColor=MUTED,
        alignment=TA_CENTER,
    )
    via_style = ParagraphStyle(
        "GeneratedVia",
        parent=styles["Normal"],
        fontName=font_regular,
        fontSize=7.5,
        leading=10,
        textColor=BRAND_GREEN,
        alignment=TA_LEFT,
    )

    meta = result.meta
    period = "—"
    if meta.period_from or meta.period_to:
        from app.compliance.formatting import format_date

        period = f"{format_date(meta.period_from) or '…'} — {format_date(meta.period_to) or '…'}"

    header_cells: list[Any] = []
    if _LOGO_PATH.exists():
        logo = Image(str(_LOGO_PATH), width=12 * mm, height=12 * mm)
        logo.hAlign = "LEFT"
        header_cells.append(logo)
    else:
        header_cells.append(Paragraph("AgroTwin", brand_style))

    header_text = Table(
        [
            [Paragraph("AgroTwin", brand_style)],
            [Paragraph(generated_via or GENERATED_VIA, via_style)],
        ],
        colWidths=[120 * mm],
    )
    header_text.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    header_cells.append(header_text)

    brand_row = Table([header_cells], colWidths=[14 * mm, pagesize[0] - 38 * mm])
    brand_row.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )

    story: list[Any] = [
        brand_row,
        Spacer(1, 4),
        Paragraph(_escape(meta.title), title_style),
        Paragraph(
            f"<b>{_escape(labels['farm'])}</b> {_escape(meta.farm_name)}<br/>"
            f"<b>{_escape(labels['period'])}</b> {_escape(period)}<br/>"
            f"<b>{_escape(labels['generated'])}</b> {_escape(format_datetime(meta.generated_at))}",
            meta_style,
        ),
        Spacer(1, 4),
        Paragraph(_escape(disclaimer_text), disclaimer_style),
        Spacer(1, 8),
    ]

    headers = [Paragraph(_escape(str(col)), header_cell_style) for col in result.columns]
    data: list[list[Any]] = [headers]
    for row in result.rows:
        data.append(
            [Paragraph(_escape(format_display_value(row.get(col))), cell_style) for col in result.columns]
        )

    if len(data) == 1:
        empty = [Paragraph("Nema zapisa za izabrane filtere.", cell_style)] + [""] * (
            max(len(result.columns) - 1, 0)
        )
        data.append(empty)

    col_count = max(1, len(result.columns))
    usable = pagesize[0] - 24 * mm
    col_width = usable / col_count
    table = Table(data, colWidths=[col_width] * col_count, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
                ("GRID", (0, 0), (-1, -1), 0.3, GRID),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("FONTNAME", (0, 0), (-1, -1), font_regular),
            ]
        )
    )
    story.append(table)

    if result.issues:
        story.append(Spacer(1, 10))
        story.append(
            Paragraph(
                "Napomene o kompletnosti podataka (iz sačuvane evidencije)",
                ParagraphStyle(
                    "IssuesHeading",
                    parent=title_style,
                    fontSize=10,
                    spaceBefore=2,
                ),
            )
        )
        for issue in result.issues[:100]:
            field = f" ({issue.field})" if issue.field else ""
            story.append(
                Paragraph(
                    f"[{_escape(issue.severity)}] {_escape(issue.message)}{_escape(field)}",
                    meta_style,
                )
            )

    def _footer(canvas, _doc):
        canvas.saveState()
        canvas.setStrokeColor(GRID)
        canvas.setLineWidth(0.4)
        canvas.line(12 * mm, 12 * mm, pagesize[0] - 12 * mm, 12 * mm)
        canvas.setFont(font_regular, 7)
        canvas.setFillColor(MUTED)
        canvas.drawString(12 * mm, 7 * mm, "AgroTwin · generisano kroz AgroTwin platformu")
        canvas.drawRightString(pagesize[0] - 12 * mm, 7 * mm, f"Strana {canvas.getPageNumber()}")
        canvas.restoreState()

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buffer.getvalue()


def _escape(value: Any) -> str:
    text = "" if value is None else str(value)
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
