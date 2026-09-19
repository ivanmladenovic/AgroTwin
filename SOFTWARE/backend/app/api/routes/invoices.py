from datetime import date
from uuid import UUID

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import FileResponse, Response

from app.api.deps import CurrentUser, DBSession
from app.models.enums import InvoiceCategory, InvoiceKind
from app.schemas.invoice import InvoiceRead
from app.services.invoice import InvoiceService

router = APIRouter(prefix="/invoices", tags=["invoices"])


@router.get("", response_model=list[InvoiceRead])
def list_invoices(
    current_user: CurrentUser,
    db: DBSession,
    category: InvoiceCategory | None = None,
) -> list[InvoiceRead]:
    return InvoiceService(db).list_invoices(current_user.id, category)


@router.post("", response_model=InvoiceRead, status_code=201)
async def create_invoice(
    current_user: CurrentUser,
    db: DBSession,
    file: UploadFile = File(...),
    title: str = Form(...),
    category: InvoiceCategory = Form(...),
    kind: InvoiceKind | None = Form(default=None),
    vendor: str | None = Form(default=None),
    amount: str | None = Form(default=None),
    issued_on: date = Form(...),
    notes: str | None = Form(default=None),
) -> InvoiceRead:
    content = await file.read()
    service = InvoiceService(db)
    invoice = service.create(
        current_user.id,
        filename=file.filename or "racun",
        content_type=file.content_type or "application/octet-stream",
        content=content,
        title=title,
        category=category,
        kind=kind,
        vendor=vendor,
        amount=amount,
        issued_on=issued_on,
        notes=notes,
        created_by_id=current_user.id,
    )
    return service.to_read(invoice)


@router.get("/{invoice_id}", response_model=InvoiceRead)
def get_invoice(invoice_id: UUID, current_user: CurrentUser, db: DBSession) -> InvoiceRead:
    service = InvoiceService(db)
    return service.to_read(service.get_invoice(invoice_id, current_user.id))


@router.get("/{invoice_id}/file")
def get_invoice_file(invoice_id: UUID, current_user: CurrentUser, db: DBSession) -> Response:
    service = InvoiceService(db)
    invoice = service.get_invoice(invoice_id, current_user.id)
    local = service.file_local_path(invoice)
    if local is not None and local.exists():
        return FileResponse(local, media_type=invoice.content_type, filename=invoice.original_filename)
    content, content_type = service.file_bytes(invoice)
    return Response(
        content=content,
        media_type=content_type,
        headers={"Content-Disposition": f'attachment; filename="{invoice.original_filename}"'},
    )


@router.delete("/{invoice_id}", status_code=204)
def delete_invoice(invoice_id: UUID, current_user: CurrentUser, db: DBSession) -> None:
    InvoiceService(db).delete(invoice_id, current_user.id)
