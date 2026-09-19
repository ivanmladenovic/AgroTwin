from pathlib import Path
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.db.seed import seed_demo_data
from app.db.session import SessionLocal


def main() -> None:
    db = SessionLocal()
    try:
        seed_demo_data(db)
        print("Seed complete: demo orchard, activities, costs, knowledge and AI are ready.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
