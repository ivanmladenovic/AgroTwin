from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.core.exceptions import AppError, NotFoundError
from app.models.activity import Activity
from app.models.enums import ActivityStatus, ScopeType, SoilLabExtractionStatus, SoilLabVerificationStatus
from app.models.soil_lab import SoilLabAnalysis, SoilLabResult
from app.repositories.activity import ActivityRepository
from app.repositories.catalog import CatalogRepository
from app.repositories.parcel import ParcelRepository
from app.repositories.soil_lab import SoilLabAnalysisRepository
from app.repositories.tree import TreeRepository
from app.schemas.soil_lab import (
    SoilLabAnalysisRead,
    SoilLabResultCreate,
    SoilLabResultRead,
    SoilLabResultUpdate,
    SoilLabVerifyRequest,
)
from app.soil.lab_extract import extract_lab_parameters_from_text
from app.storage import get_storage
from app.storage.documents import compress_pdf
from app.storage.images import compress_photo

logger = logging.getLogger(__name__)

MAX_FILE_BYTES = 400 * 1024 * 1024  # allow large phone/scanner dumps
MAX_STORED_BYTES = 40 * 1024 * 1024  # after compression
HIGH_CONFIDENCE = Decimal("0.80")
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
        return [self.to_read(item, include_results=True) for item in self.analyses.list_for_activity(activity.id)]

    def list_for_parcel(self, parcel_id: UUID, owner_id: UUID) -> list[SoilLabAnalysisRead]:
        parcel = self._parcel(parcel_id, owner_id)
        return [self.to_read(item, include_results=True) for item in self.analyses.list_for_parcel(parcel.id)]

    def get_analysis(self, analysis_id: UUID, owner_id: UUID) -> SoilLabAnalysis:
        analysis = self.analyses.get(analysis_id)
        if analysis is None:
            raise NotFoundError("Analiza zemljišta nije pronađena")
        self._parcel(analysis.parcel_id, owner_id)
        return analysis

    def get_detail(self, analysis_id: UUID, owner_id: UUID) -> SoilLabAnalysisRead:
        return self.to_read(self.get_analysis(analysis_id, owner_id), include_results=True)

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
        reading: dict | None = None,
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
            extraction_status=SoilLabExtractionStatus.PENDING,
            verification_status=SoilLabVerificationStatus.NEEDS_REVIEW,
            created_by_id=created_by_id,
        )
        self.analyses.add(analysis)
        self.db.flush()
        if reading is not None:
            self.apply_reading(analysis, reading)
        else:
            self.run_structured_extraction(analysis, commit=False)
        self.db.commit()
        self.db.expire_all()
        refreshed = self.analyses.get(analysis.id)
        return refreshed or analysis

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
                f"- Laboratorijska analiza · {item.get('sampled_on')} · {item.get('original_filename')} · "
                f"sadnica {item.get('tree_public_id') or item.get('tree_id')} · "
                f"status {item.get('verification_status') or 'needs_review'}"
            )
            params = item.get("parameters") or []
            if params:
                lines.append("STRUKTURIRANI PARAMETRI:")
                for param in params:
                    unit = f" {param.get('unit')}" if param.get("unit") else ""
                    method = f" ({param.get('method')})" if param.get("method") else ""
                    lines.append(
                        f"  · {param.get('original_parameter_name')} [{param.get('parameter_code')}]"
                        f" = {param.get('value')}{unit}{method}"
                    )
            text = (item.get("extracted_text") or "").strip()
            if text and len(text) <= 800:
                lines.append("IZVOD IZ ANALIZE:")
                lines.append(text)
            elif include_text:
                lines.append(
                    "NAPOMENA: parametri ove analize nisu pročitani. "
                    "Ne izmišljajte brojeve i ne pretvarajte prazno u nulu."
                )
        if not include_text and any(item.get("parameters") for item in analyses):
            lines.append(
                "Ovo su sačuvani parametri laboratorijske analize. "
                "Ne tražite od korisnika da ponovo pošalje isti dokument."
            )
        elif not include_text:
            lines.append(
                "Nema sačuvanih parametara. Ako korisnik pita za analizu, "
                "reci da izveštaj još nije pročitan, bez izmišljenih brojeva."
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
                "verification_status": analysis.verification_status.value if analysis.verification_status else None,
                "laboratory_name": analysis.laboratory_name,
                "source_kind": "laboratory",
                "parameters": [
                    {
                        "parameter_code": result.parameter_code,
                        "original_parameter_name": result.original_parameter_name,
                        "value": result.value,
                        "unit": result.unit,
                        "method": result.method,
                        "verification_status": result.verification_status.value,
                    }
                    for result in (analysis.results or [])
                ],
            }
            if include_text:
                item["extracted_text"] = analysis.extracted_text or self.extract_text(
                    analysis, max_chars=7000, max_pages=6
                )
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
            return analysis.extracted_text or ""
        text = _extract_pdf_text(content, max_pages=max_pages, max_chars=max_chars)
        return text

    def run_structured_extraction(
        self,
        analysis: SoilLabAnalysis,
        *,
        commit: bool = True,
        replace_existing: bool = True,
    ) -> SoilLabAnalysis:
        """PDF/image → model reading of the key parameters. No OCR."""
        analysis.extraction_status = SoilLabExtractionStatus.RUNNING
        analysis.extraction_error = None
        self.db.flush()
        try:
            content, _mime = self.file_bytes(analysis)
            from app.ai import get_ai_provider
            from app.soil.lab_vision import read_lab_document

            reading = read_lab_document(get_ai_provider(), content, analysis.content_type)
            if not reading.get("parameters"):
                reading = _reading_from_text_layer(content, analysis.content_type) or reading
            self.apply_reading(analysis, reading, replace_existing=replace_existing)
        except Exception as exc:
            logger.exception("Soil lab model reading failed for %s", analysis.id)
            analysis.extraction_status = SoilLabExtractionStatus.FAILED
            analysis.extraction_error = str(exc)[:500]
            analysis.verification_status = SoilLabVerificationStatus.NEEDS_REVIEW
        if commit:
            self.db.commit()
            self.db.expire_all()
            refreshed = self.analyses.get(analysis.id)
            return refreshed or analysis
        self.db.flush()
        return analysis

    def apply_reading(
        self,
        analysis: SoilLabAnalysis,
        reading: dict,
        *,
        replace_existing: bool = True,
    ) -> None:
        """Store a model reading. Does not mark the analysis as verified."""
        if replace_existing and analysis.results:
            for existing in list(analysis.results):
                self.db.delete(existing)
            self.db.flush()
            analysis.results.clear()
        summary = (reading.get("summary") or "").strip() or None
        analysis.extracted_text = summary
        laboratory = (reading.get("laboratory_name") or "").strip() or None
        if laboratory and not analysis.laboratory_name:
            analysis.laboratory_name = laboratory[:255]
        for item in reading.get("parameters") or []:
            if not isinstance(item, dict) or not item.get("value") or not item.get("code"):
                continue
            result = SoilLabResult(
                analysis_id=analysis.id,
                parameter_code=str(item["code"])[:64],
                original_parameter_name=str(item.get("name") or item["code"])[:512],
                value=str(item["value"])[:128],
                unit=(str(item["unit"])[:64] if item.get("unit") else None),
                method=(str(item["method"])[:128] if item.get("method") else None),
                extraction_confidence=Decimal("0.70"),
                raw_text="model",
                verification_status=SoilLabVerificationStatus.NEEDS_REVIEW,
            )
            self.analyses.add_result(result)
        error = (reading.get("error") or "").strip()
        if reading.get("parameters") or summary:
            analysis.extraction_status = SoilLabExtractionStatus.SUCCEEDED
            analysis.extraction_error = None
        else:
            analysis.extraction_status = SoilLabExtractionStatus.FAILED
            analysis.extraction_error = (error or "Model nije pročitao parametre.")[:500]
        if analysis.verification_status == SoilLabVerificationStatus.VERIFIED:
            analysis.verification_status = SoilLabVerificationStatus.NEEDS_REVIEW
        elif analysis.verification_status == SoilLabVerificationStatus.SKIPPED:
            analysis.verification_status = SoilLabVerificationStatus.NEEDS_REVIEW
        self.db.flush()

    def reextract(self, analysis_id: UUID, owner_id: UUID) -> SoilLabAnalysisRead:
        analysis = self.get_analysis(analysis_id, owner_id)
        analysis = self.run_structured_extraction(analysis, commit=True, replace_existing=True)
        return self.to_read(analysis, include_results=True)

    def verify(self, analysis_id: UUID, owner_id: UUID, payload: SoilLabVerifyRequest | None = None) -> SoilLabAnalysisRead:
        analysis = self.get_analysis(analysis_id, owner_id)
        if payload:
            if payload.analysis_date is not None:
                analysis.analysis_date = payload.analysis_date
            if payload.laboratory_name is not None:
                analysis.laboratory_name = payload.laboratory_name.strip() or None
            if payload.sample_depth_from_cm is not None:
                analysis.sample_depth_from_cm = payload.sample_depth_from_cm
            if payload.sample_depth_to_cm is not None:
                analysis.sample_depth_to_cm = payload.sample_depth_to_cm
        for result in analysis.results:
            if result.verification_status != SoilLabVerificationStatus.SKIPPED:
                result.verification_status = SoilLabVerificationStatus.VERIFIED
        analysis.verification_status = SoilLabVerificationStatus.VERIFIED
        self.db.commit()
        self.db.expire_all()
        return self.to_read(self.get_analysis(analysis_id, owner_id), include_results=True)

    def skip_verification(self, analysis_id: UUID, owner_id: UUID) -> SoilLabAnalysisRead:
        analysis = self.get_analysis(analysis_id, owner_id)
        analysis.verification_status = SoilLabVerificationStatus.SKIPPED
        self.db.commit()
        self.db.expire_all()
        return self.to_read(self.get_analysis(analysis_id, owner_id), include_results=True)

    def update_result(
        self,
        analysis_id: UUID,
        result_id: UUID,
        owner_id: UUID,
        payload: SoilLabResultUpdate,
    ) -> SoilLabAnalysisRead:
        analysis = self.get_analysis(analysis_id, owner_id)
        result = self._result_for_analysis(analysis, result_id)
        data = payload.model_dump(exclude_unset=True)
        for key, value in data.items():
            if key == "original_parameter_name" and value is not None:
                setattr(result, key, str(value).strip()[:512])
            elif key == "value" and value is not None:
                setattr(result, key, str(value).strip()[:128])
            elif key == "parameter_code" and value is not None:
                setattr(result, key, str(value).strip().upper()[:64])
            else:
                setattr(result, key, value)
        # Manual edits are trusted candidates but still require analysis-level confirm.
        if result.verification_status != SoilLabVerificationStatus.SKIPPED:
            result.verification_status = SoilLabVerificationStatus.EXTRACTED
        if analysis.verification_status == SoilLabVerificationStatus.VERIFIED:
            analysis.verification_status = SoilLabVerificationStatus.NEEDS_REVIEW
        self.db.commit()
        self.db.expire_all()
        return self.to_read(self.get_analysis(analysis_id, owner_id), include_results=True)

    def add_manual_result(
        self,
        analysis_id: UUID,
        owner_id: UUID,
        payload: SoilLabResultCreate,
    ) -> SoilLabAnalysisRead:
        analysis = self.get_analysis(analysis_id, owner_id)
        result = SoilLabResult(
            analysis_id=analysis.id,
            parameter_code=payload.parameter_code.strip().upper()[:64],
            original_parameter_name=payload.original_parameter_name.strip()[:512],
            value=payload.value.strip()[:128],
            unit=(payload.unit or None),
            method=(payload.method or None),
            depth_from_cm=payload.depth_from_cm,
            depth_to_cm=payload.depth_to_cm,
            notes=payload.notes,
            extraction_confidence=None,
            verification_status=SoilLabVerificationStatus.EXTRACTED,
        )
        self.analyses.add_result(result)
        if analysis.verification_status == SoilLabVerificationStatus.VERIFIED:
            analysis.verification_status = SoilLabVerificationStatus.NEEDS_REVIEW
        self.db.commit()
        self.db.expire_all()
        return self.to_read(self.get_analysis(analysis_id, owner_id), include_results=True)

    def delete_result(self, analysis_id: UUID, result_id: UUID, owner_id: UUID) -> SoilLabAnalysisRead:
        analysis = self.get_analysis(analysis_id, owner_id)
        result = self._result_for_analysis(analysis, result_id)
        self.analyses.delete_result(result)
        if analysis.verification_status == SoilLabVerificationStatus.VERIFIED:
            analysis.verification_status = SoilLabVerificationStatus.NEEDS_REVIEW
        self.db.commit()
        self.db.expire_all()
        return self.to_read(self.get_analysis(analysis_id, owner_id), include_results=True)

    def to_read(self, analysis: SoilLabAnalysis, *, include_results: bool = False) -> SoilLabAnalysisRead:
        tree_row = self.trees.get_for_parcel(analysis.parcel_id, analysis.tree_id)
        tree = tree_row[0] if tree_row else None
        row_number = tree_row[1] if tree_row else None
        results = list(analysis.results or [])
        result_reads = [_result_to_read(item) for item in results] if include_results else []
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
            analysis_date=analysis.analysis_date,
            laboratory_name=analysis.laboratory_name,
            sample_depth_from_cm=analysis.sample_depth_from_cm,
            sample_depth_to_cm=analysis.sample_depth_to_cm,
            original_filename=analysis.original_filename,
            content_type=analysis.content_type,
            size_bytes=analysis.size_bytes,
            extraction_status=analysis.extraction_status,
            verification_status=analysis.verification_status,
            extraction_error=analysis.extraction_error,
            result_count=len(results),
            results=result_reads,
            source_kind="laboratory",
        )

    def _result_for_analysis(self, analysis: SoilLabAnalysis, result_id: UUID) -> SoilLabResult:
        for result in analysis.results or []:
            if result.id == result_id:
                return result
        raise NotFoundError("Parametar analize nije pronađen")

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


def _result_to_read(result: SoilLabResult) -> SoilLabResultRead:
    confidence = result.extraction_confidence
    high = confidence is not None and confidence >= HIGH_CONFIDENCE
    return SoilLabResultRead(
        id=result.id,
        created_at=result.created_at,
        updated_at=result.updated_at,
        analysis_id=result.analysis_id,
        parameter_code=result.parameter_code,
        original_parameter_name=result.original_parameter_name,
        value=result.value,
        unit=result.unit,
        method=result.method,
        depth_from_cm=result.depth_from_cm,
        depth_to_cm=result.depth_to_cm,
        extraction_confidence=result.extraction_confidence,
        source_page=result.source_page,
        raw_text=result.raw_text,
        verification_status=result.verification_status,
        notes=result.notes,
        high_confidence=high,
    )


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


def _reading_from_text_layer(content: bytes, content_type: str | None) -> dict | None:
    """Digital PDFs with a real text layer. Scanned pages are left to the model."""
    mime = (content_type or "").lower()
    if mime.startswith("image/"):
        return None
    text = _extract_pdf_text(content, max_pages=6, max_chars=12000)
    if len(text.strip()) < 80:
        return None
    outcome = extract_lab_parameters_from_text(text)
    if not outcome.parameters:
        return None
    return {
        "laboratory_name": outcome.laboratory_name,
        "sampled_on": None,
        "summary": None,
        "parameters": [
            {
                "code": item.parameter_code,
                "name": item.original_parameter_name,
                "value": item.value,
                "unit": item.unit,
                "method": item.method,
            }
            for item in outcome.parameters
        ],
        "error": None,
    }


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
        from app.knowledge.ocr import ocr_png, tesseract_available
    except Exception:
        return ""
    if not tesseract_available():
        logger.warning("Soil-lab PDF has no text layer and Tesseract is not installed")
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
