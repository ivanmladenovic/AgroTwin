from __future__ import annotations

from datetime import date
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.core.exceptions import AppError, NotFoundError
from app.models.activity import Activity
from app.models.enums import ActivityStatus, ScopeType
from app.models.soil_lab import SoilLabAnalysis
from app.repositories.activity import ActivityRepository
from app.repositories.catalog import CatalogRepository
from app.repositories.parcel import ParcelRepository
from app.repositories.soil_lab import SoilLabAnalysisRepository
from app.repositories.tree import TreeRepository
from app.schemas.soil_lab import SoilLabAnalysisRead
from app.storage import get_storage
from app.storage.documents import compress_pdf
from app.storage.images import compress_photo

MAX_FILE_BYTES = 400 * 1024 * 1024  # allow large phone/scanner dumps
MAX_STORED_BYTES = 40 * 1024 * 1024  # after compression
ALLOWED_TYPES = {
    "application/pdf": "pdf",
    "application/x-pdf": "pdf",
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}


class SoilLabAnalysisService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.activities = ActivityRepository(db)
        self.analyses = SoilLabAnalysisRepository(db)
        self.trees = TreeRepository(db)
        self.parcels = ParcelRepository(db)
        self.catalogs = CatalogRepository(db)
        self.storage = get_storage()

    def list_for_activity(self, activity_id: UUID, owner_id: UUID) -> list[SoilLabAnalysisRead]:
        activity = self._activity(activity_id, owner_id)
        return [self.to_read(item) for item in self.analyses.list_for_activity(activity.id)]

    def list_for_parcel(self, parcel_id: UUID, owner_id: UUID) -> list[SoilLabAnalysisRead]:
        parcel = self._parcel(parcel_id, owner_id)
        return [self.to_read(item) for item in self.analyses.list_for_parcel(parcel.id)]

    def get_analysis(self, analysis_id: UUID, owner_id: UUID) -> SoilLabAnalysis:
        analysis = self.analyses.get(analysis_id)
        if analysis is None:
            raise NotFoundError("Analiza zemljišta nije pronađena")
        self._parcel(analysis.parcel_id, owner_id)
        return analysis

    def create_for_parcel(
        self,
        parcel_id: UUID,
        owner_id: UUID,
        *,
        tree_id: UUID,
        sampled_on: date,
        filename: str,
        content_type: str,
        content: bytes,
        created_by_id: UUID,
    ) -> SoilLabAnalysis:
        parcel = self._parcel(parcel_id, owner_id)
        activity = self._ensure_soil_activity(parcel, sampled_on, owner_id, created_by_id)
        return self.create(
            activity.id,
            owner_id,
            tree_id=tree_id,
            sampled_on=sampled_on,
            filename=filename,
            content_type=content_type,
            content=content,
            created_by_id=created_by_id,
        )

    def create(
        self,
        activity_id: UUID,
        owner_id: UUID,
        *,
        tree_id: UUID,
        sampled_on: date,
        filename: str,
        content_type: str,
        content: bytes,
        created_by_id: UUID,
    ) -> SoilLabAnalysis:
        activity = self._activity(activity_id, owner_id)
        if activity.parcel_id is None:
            raise AppError("Analiza zemljišta zahteva parcelu", status_code=422, code="missing_parcel")
        if activity.activity_type.slug != "soil_analysis":
            raise AppError(
                "Uzorke analize dodajete na aktivnost analize zemljišta",
                status_code=422,
                code="wrong_activity_type",
            )
        if not content:
            raise AppError("Datoteka je prazna", status_code=422, code="empty_file")
        if len(content) > MAX_FILE_BYTES:
            raise AppError(
                "Datoteka je veća od 400 MB. Smanjite sken ili podelite analizu na manje fajlove.",
                status_code=422,
                code="file_too_large",
            )
        extension = _extension(filename, content_type)
        if extension == "pdf":
            content = compress_pdf(content, max_output_bytes=MAX_STORED_BYTES)
            stored_type = "application/pdf"
            if not filename.lower().endswith(".pdf"):
                filename = f"{Path(filename).stem or 'analiza'}.pdf"
        else:
            compressed = compress_photo(content, filename)
            content = compressed.content
            stored_type = compressed.content_type
            filename = compressed.filename
            extension = compressed.extension.lstrip(".")
        if len(content) > MAX_STORED_BYTES:
            raise AppError(
                "Datoteka je i posle kompresije prevelika (max 40 MB). "
                "Probajte fotografiju stranica ili manji sken.",
                status_code=422,
                code="file_too_large_after_compress",
            )
        tree_row = self.trees.get_for_parcel(activity.parcel_id, tree_id)
        if tree_row is None:
            raise AppError("Izabrana sadnica ne pripada parceli", status_code=422, code="invalid_tree")
        key = f"soil-lab/{activity.farm_id}/{activity.id}/{uuid4().hex}.{extension}"
        self.storage.put(key, content, stored_type)
        analysis = SoilLabAnalysis(
            activity_id=activity.id,
            farm_id=activity.farm_id,
            parcel_id=activity.parcel_id,
            tree_id=tree_id,
            sampled_on=sampled_on,
            storage_key=key,
            original_filename=filename,
            content_type=stored_type,
            size_bytes=len(content),
            created_by_id=created_by_id,
        )
        self.analyses.add(analysis)
        self.db.commit()
        self.db.refresh(analysis)
        return analysis

    def delete(self, analysis_id: UUID, owner_id: UUID) -> None:
        analysis = self.get_analysis(analysis_id, owner_id)
        key = analysis.storage_key
        self.analyses.delete(analysis)
        self.db.commit()
        try:
            self.storage.delete(key)
        except Exception:
            # DB row is already gone; missing disk object is fine (ephemeral Render storage).
            pass

    def file_local_path(self, analysis: SoilLabAnalysis) -> Path | None:
        return self.storage.local_path(analysis.storage_key)

    def file_bytes(self, analysis: SoilLabAnalysis) -> tuple[bytes, str]:
        try:
            content = self.storage.get(analysis.storage_key)
        except FileNotFoundError as exc:
            raise NotFoundError(
                "Fajl analize nije pronađen na serveru. Obrišite ovaj zapis i ponovo otpremite PDF."
            ) from exc
        except Exception as exc:
            raise AppError(
                "Fajl analize trenutno nije dostupan. Obrišite zapis i ponovo otpremite PDF.",
                status_code=404,
                code="soil_file_unavailable",
            ) from exc
        if not content:
            raise NotFoundError(
                "Fajl analize nije pronađen na serveru. Obrišite ovaj zapis i ponovo otpremite PDF."
            )
        return content, analysis.content_type

    def format_context_block(
        self,
        parcel_id: UUID,
        owner_id: UUID,
        *,
        include_text: bool = False,
        limit: int = 3,
    ) -> str | None:
        payload = self.context_payload(parcel_id, owner_id, limit=limit, include_text=include_text)
        analyses = payload.get("analyses") or []
        if not analyses:
            return None
        lines = [
            "LABORATORIJSKE ANALIZE ZEMLJIŠTA (otpremljene u AgroTwin, nisu chat attachment):",
        ]
        for item in analyses:
            lines.append(
                f"- {item.get('sampled_on')} · {item.get('original_filename')} · "
                f"sadnica {item.get('tree_public_id') or item.get('tree_id')}"
            )
            text = (item.get("extracted_text") or "").strip()
            if text:
                lines.append("IZVOD IZ ANALIZE:")
                lines.append(text)
        if not include_text:
            lines.append(
                "Za puni sadržaj PDF-a pozovi get_soil_lab_analyses(include_text=true)."
            )
        return "\n".join(lines)

    def context_payload(
        self,
        parcel_id: UUID,
        owner_id: UUID,
        *,
        limit: int = 3,
        include_text: bool = True,
    ) -> dict:
        self._parcel(parcel_id, owner_id)
        rows = self.analyses.list_for_parcel(parcel_id)[: max(1, min(int(limit or 3), 5))]
        analyses: list[dict] = []
        for analysis in rows:
            tree_row = self.trees.get_for_parcel(analysis.parcel_id, analysis.tree_id)
            tree = tree_row[0] if tree_row else None
            item = {
                "id": str(analysis.id),
                "sampled_on": str(analysis.sampled_on),
                "original_filename": analysis.original_filename,
                "content_type": analysis.content_type,
                "size_bytes": analysis.size_bytes,
                "tree_id": str(analysis.tree_id),
                "tree_public_id": tree.public_id if tree else None,
            }
            if include_text:
                item["extracted_text"] = self.extract_text(analysis, max_chars=7000, max_pages=6)
            analyses.append(item)
        return {"parcel_id": str(parcel_id), "count": len(analyses), "analyses": analyses}

    def extract_text(
        self,
        analysis: SoilLabAnalysis,
        *,
        max_chars: int = 7000,
        max_pages: int = 6,
    ) -> str:
        try:
            content = self.storage.get(analysis.storage_key)
        except Exception:
            return ""
        if not content:
            return ""
        content_type = (analysis.content_type or "").lower()
        if content_type.startswith("image/"):
            return _extract_image_text(content, max_chars=max_chars)
        text = _extract_pdf_text(content, max_pages=max_pages, max_chars=max_chars)
        if text.strip():
            return text
        # Scanned PDFs often have no text layer — OCR first pages when available.
        return _extract_pdf_ocr_text(content, max_pages=min(max_pages, 4), max_chars=max_chars)

    def to_read(self, analysis: SoilLabAnalysis) -> SoilLabAnalysisRead:
        tree_row = self.trees.get_for_parcel(analysis.parcel_id, analysis.tree_id)
        tree = tree_row[0] if tree_row else None
        row_number = tree_row[1] if tree_row else None
        return SoilLabAnalysisRead(
            id=analysis.id,
            created_at=analysis.created_at,
            updated_at=analysis.updated_at,
            activity_id=analysis.activity_id,
            parcel_id=analysis.parcel_id,
            tree_id=analysis.tree_id,
            tree_public_id=tree.public_id if tree else None,
            row_id=tree.row_id if tree else None,
            row_number=row_number,
            sampled_on=analysis.sampled_on,
            original_filename=analysis.original_filename,
            content_type=analysis.content_type,
            size_bytes=analysis.size_bytes,
        )

    def _ensure_soil_activity(self, parcel, sampled_on: date, owner_id: UUID, created_by_id: UUID) -> Activity:
        activity_type = self.catalogs.get_activity_type_by_slug("soil_analysis")
        if activity_type is None:
            raise AppError(
                "Tip aktivnosti analize zemljišta nije podešen",
                status_code=500,
                code="missing_activity_type",
            )
        existing = self.activities.list_for_owner(
            owner_id,
            date_from=sampled_on,
            date_to=sampled_on,
            activity_type_id=activity_type.id,
            parcel_id=parcel.id,
            limit=1,
        )
        if existing:
            return existing[0]
        activity = Activity(
            activity_type_id=activity_type.id,
            title=activity_type.name,
            description=None,
            performed_on=sampled_on,
            status=ActivityStatus.COMPLETED if sampled_on <= date.today() else ActivityStatus.PLANNED,
            quantity=None,
            unit=None,
            line_items=[],
            extra_row_ids=[],
            notes=None,
            created_by_id=created_by_id,
            farm_id=parcel.farm_id,
            parcel_id=parcel.id,
            row_id=None,
            tree_id=None,
            scope_type=ScopeType.PARCEL,
        )
        self.activities.add(activity)
        self.db.flush()
        return activity

    def _parcel(self, parcel_id: UUID, owner_id: UUID):
        parcel = self.parcels.get_for_owner(parcel_id, owner_id)
        if parcel is None:
            raise NotFoundError("Parcela nije pronađena")
        return parcel

    def _activity(self, activity_id: UUID, owner_id: UUID):
        activity = self.activities.get_for_owner(activity_id, owner_id)
        if activity is None:
            raise NotFoundError("Aktivnost nije pronađena")
        return activity


def _extension(filename: str, content_type: str) -> str:
    mapped = ALLOWED_TYPES.get((content_type or "").lower())
    if mapped:
        return mapped
    suffix = Path(filename).suffix.lower().lstrip(".")
    if suffix in {"pdf", "jpg", "jpeg", "png", "webp"}:
        return "jpg" if suffix == "jpeg" else suffix
    raise AppError(
        "Prihvataju se PDF, JPG, PNG ili WEBP datoteke",
        status_code=422,
        code="invalid_file",
    )


def _extract_pdf_text(content: bytes, *, max_pages: int, max_chars: int) -> str:
    try:
        from app.knowledge.pdf import extract_pdf_pages

        pages = extract_pdf_pages(content)[:max_pages]
    except Exception:
        return ""
    chunks = [text.strip() for _, text in pages if (text or "").strip()]
    joined = "\n\n".join(chunks).strip()
    if len(joined) > max_chars:
        return joined[:max_chars] + "…"
    return joined


def _extract_pdf_ocr_text(content: bytes, *, max_pages: int, max_chars: int) -> str:
    """OCR only the first pages of a scanned PDF (avoids full-document parse)."""
    try:
        import fitz
        from app.knowledge.ocr import ocr_png
    except Exception:
        return ""
    try:
        document = fitz.open(stream=content, filetype="pdf")
    except Exception:
        return ""
    chunks: list[str] = []
    try:
        scale = 120 / 72
        matrix = fitz.Matrix(scale, scale)
        for index, page in enumerate(document):
            if index >= max_pages:
                break
            try:
                pixmap = page.get_pixmap(matrix=matrix, alpha=False)
                text = (ocr_png(pixmap.tobytes("png")) or "").strip()
            except Exception:
                continue
            if text:
                chunks.append(text)
    finally:
        document.close()
    joined = "\n\n".join(chunks).strip()
    if len(joined) > max_chars:
        return joined[:max_chars] + "…"
    return joined


def _extract_image_text(content: bytes, *, max_chars: int) -> str:
    try:
        from app.knowledge.ocr import ocr_png
        from PIL import Image
        from io import BytesIO

        with Image.open(BytesIO(content)) as image:
            buffer = BytesIO()
            image.convert("RGB").save(buffer, format="PNG")
            text = (ocr_png(buffer.getvalue()) or "").strip()
    except Exception:
        return ""
    if len(text) > max_chars:
        return text[:max_chars] + "…"
    return text
