from __future__ import annotations

import csv
import io

from app.schemas.compliance import ComplianceReportResult


def render_report_csv(result: ComplianceReportResult) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(result.columns)
    if not result.rows:
        writer.writerow(["Nema zapisa za izabrane filtere"] + [""] * max(0, len(result.columns) - 1))
    else:
        for row in result.rows:
            writer.writerow([row.get(col, "") for col in result.columns])
    if result.issues:
        writer.writerow([])
        writer.writerow(["ozbiljnost", "kod", "poruka", "polje"])
        for issue in result.issues:
            writer.writerow([issue.severity, issue.code, issue.message, issue.field or ""])
    return output.getvalue()
