#!/usr/bin/env python3
"""Scheduled parcel intelligence job.

Suggested cron (daily):
  30 5 * * * cd /path/to/SOFTWARE/backend && .venv/bin/python scripts/run_parcel_intelligence.py

1) Processes pending ParcelAnalysisEvent rows
2) Enqueues SCHEDULED events and analyzes parcels with change detection
   (skips AI when nothing meaningful changed / min interval not elapsed)
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.session import SessionLocal  # noqa: E402
from app.services.intelligence import IntelligenceService  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("parcel_intelligence")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pending-only", action="store_true")
    parser.add_argument("--scheduled-only", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        service = IntelligenceService(db)
        runs = []
        if not args.scheduled_only:
            runs.extend(service.process_pending())
        if not args.pending_only:
            runs.extend(service.process_scheduled())
        payload = [
            {
                "parcel_id": str(run.parcel_id),
                "status": run.status.value,
                "ai_called": run.ai_called,
                "skip_reason": run.skip_reason,
            }
            for run in runs
        ]
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            for item in payload:
                logger.info("%s", item)
            logger.info("Finished %s run(s)", len(payload))
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
