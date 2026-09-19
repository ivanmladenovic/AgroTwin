from pathlib import Path
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.db.seed import DEMO_EMAIL
from app.db.session import SessionLocal
from app.knowledge.taxonomy import MANUALS, match_manual
from app.models.enums import KnowledgeCategory
from app.models.user import User
from app.services.knowledge import KnowledgeService
from sqlalchemy import select

DEFAULT_DIR = BACKEND_ROOT.parent / "Prirucnici"


def main() -> None:
    args = [item for item in sys.argv[1:] if not item.startswith("--")]
    force = "--force" in sys.argv
    reindex = "--reindex" in sys.argv
    source = Path(args[0]) if args else DEFAULT_DIR
    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.email == DEMO_EMAIL))
        if user is None:
            raise SystemExit("Demo korisnik nije pronađen. Pokrenite seed.")
        service = KnowledgeService(db)
        if reindex:
            documents = service.reindex_agriser(user.id)
            for document in documents:
                print(
                    f"Reindex: {document.title} status={document.status.value} "
                    f"pages={document.page_count} chunks={document.chunk_count}"
                )
            return
        if not source.exists():
            raise SystemExit(f"Folder priručnika nije pronađen: {source}")
        pdfs = sorted(source.glob("*.pdf"))
        if not pdfs:
            raise SystemExit(f"Nema PDF datoteka u {source}")
        for pdf in pdfs:
            content = pdf.read_bytes()
            manual = match_manual(pdf.name, pdf.stem)
            title = manual.title if manual else pdf.stem
            category = KnowledgeCategory(manual.category) if manual else KnowledgeCategory.OTHER
            print(f"Ingest: {pdf.name} ({len(content)} bytes) → {title}")
            document = service.ingest_or_skip(
                user.id,
                filename=pdf.name,
                content=content,
                title=title,
                category=category,
                uploaded_by_id=user.id,
                source_kind="agriser_manual",
                force=force,
            )
            print(
                f"  status={document.status.value} pages={document.page_count} "
                f"chunks={document.chunk_count} images={document.image_count} "
                f"ocr={document.ocr_version or '-'} hash={document.content_sha256[:12] if document.content_sha256 else '-'}"
            )
            if document.error_message:
                print(f"  error={document.error_message}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
