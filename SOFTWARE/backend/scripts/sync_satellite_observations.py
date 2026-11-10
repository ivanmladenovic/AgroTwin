#!/usr/bin/env python3
"""Daily satellite sync job.

Schedule with cron, e.g.:
  15 4 * * * cd /path/to/SOFTWARE/backend && .venv/bin/python scripts/sync_satellite_observations.py

Does not run on page load. Processes a parcel only when a new valid Sentinel-2
product is available and skips duplicates (parcel_id + provider + product_id).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.session import SessionLocal  # noqa: E402
from app.repositories.parcel import ParcelRepository  # noqa: E402
from app.services.satellite import SatelliteService  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("sync_satellite")


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync Sentinel-2 observations for AgroTwin parcels")
    parser.add_argument("--parcel-id", type=str, default=None, help="Process a single parcel UUID")
    parser.add_argument("--json", action="store_true", help="Print results as JSON")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        service = SatelliteService(db)
        if args.parcel_id:
            parcel = ParcelRepository(db).get_by_id(UUID(args.parcel_id))
            if parcel is None:
                logger.error("Parcel not found: %s", args.parcel_id)
                return 1
            results = [service.process_parcel(parcel)]
        else:
            results = service.process_all_parcels()
        payload = [item.model_dump(mode="json") for item in results]
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            for item in results:
                logger.info(
                    "parcel=%s status=%s duplicate=%s message=%s",
                    item.parcel_id,
                    item.status,
                    item.skipped_duplicate,
                    item.message,
                )
            logger.info("Processed %s parcel(s)", len(results))
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
