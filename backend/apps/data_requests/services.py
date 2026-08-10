import csv
import hashlib
import io
import os
from datetime import timedelta
from pathlib import Path
from django.conf import settings
from django.utils import timezone
from apps.forms_engine.models import FormField, GridColumn
from apps.submissions.models import Submission, SubmissionValue
from apps.exports.models import ExportLog
from apps.exports.services import CANONICAL_HEADERS, canonical_row_dicts, canonical_values
from .models import DataRequestArtifact


def eligible_submissions(scope):
    qs = Submission.objects.filter(
        expected__workflow_status="APPROVED",
        expected__form_template_id__in=scope["form_template_ids"],
        expected__period_id__in=scope["period_ids"],
    ).select_related("expected__provider", "expected__form_template", "expected__period")
    mode = scope.get("provider_scope")
    if mode == "SECTOR": qs = qs.filter(expected__provider__sector=scope.get("sector"))
    elif mode == "CATEGORY": qs = qs.filter(expected__provider__category=scope.get("provider_category"))
    elif mode == "SELECTED": qs = qs.filter(expected__provider_id__in=scope.get("provider_ids", []))
    latest = {}
    for submission in qs.order_by("expected_id", "-version"):
        latest.setdefault(submission.expected_id, submission)
    return list(latest.values())


def build_manifest(item):
    submissions = eligible_submissions(item.scope)
    if not submissions:
        raise ValueError("No approved submissions match this request.")
    form_ids = item.scope["form_template_ids"]
    field_ids = item.scope.get("field_ids", [])
    column_ids = item.scope.get("grid_column_ids", [])
    if item.scope.get("all_fields", True):
        field_ids = list(FormField.objects.filter(section__form_template_id__in=form_ids).values_list("id", flat=True))
        column_ids = list(GridColumn.objects.filter(grid__section__form_template_id__in=form_ids).values_list("id", flat=True))
    return {"submission_ids": [s.id for s in submissions], "field_ids": field_ids, "grid_column_ids": column_ids}


def canonical_rows(item):
    manifest = item.approval_manifest or {}
    submissions = Submission.objects.filter(id__in=manifest.get("submission_ids", [])).select_related(
        "expected__provider", "expected__form_template", "expected__period"
    )
    selected_fields = set(manifest.get("field_ids", []))
    selected_columns = set(manifest.get("grid_column_ids", []))
    yield from canonical_values(canonical_row_dicts(
        submissions, selected_field_ids=selected_fields, selected_column_ids=selected_columns,
        request_reference=str(item.id),
    ))


def safe_cell(value):
    text = "" if value is None else str(value)
    return "'" + text if text.startswith(("=", "+", "-", "@", "\t", "\r")) else text


def generate_artifact(item, user):
    rows = list(canonical_rows(item))
    headers = CANONICAL_HEADERS
    root = Path(settings.PRIVATE_EXPORT_ROOT)
    root.mkdir(parents=True, exist_ok=True)
    stem = f"data-request-{item.id}"
    if item.requested_format == "CSV":
        filename, mime = stem + ".csv", "text/csv"
        stream = io.StringIO(); writer = csv.writer(stream); writer.writerow(headers)
        writer.writerows([[safe_cell(v) for v in row] for row in rows]); content = b"\xef\xbb\xbf" + stream.getvalue().encode("utf-8")
    elif item.requested_format == "XLSX":
        from openpyxl import Workbook
        wb = Workbook(); details = wb.active; details.title = "Request Details"
        details.append(["Title", item.title]); details.append(["Division", item.requesting_division]); details.append(["Purpose", item.purpose])
        data = wb.create_sheet("Data"); data.append(headers)
        for row in rows: data.append([safe_cell(v) for v in row])
        out = io.BytesIO(); wb.save(out); content = out.getvalue(); filename, mime = stem + ".xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A3, landscape
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        out = io.BytesIO(); doc = SimpleDocTemplate(out, pagesize=landscape(A3), leftMargin=18, rightMargin=18)
        styles = getSampleStyleSheet(); story = [Paragraph(item.title, styles["Title"]), Paragraph(f"Division: {item.requesting_division}", styles["BodyText"]), Spacer(1, 12)]
        width = (landscape(A3)[0] - 36) / len(headers)
        table = Table([headers] + [[safe_cell(v) for v in row] for row in rows], repeatRows=1, colWidths=[width] * len(headers))
        table.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), colors.HexColor("#002d5b")), ("TEXTCOLOR", (0,0), (-1,0), colors.white), ("GRID", (0,0), (-1,-1), .25, colors.grey), ("FONTSIZE", (0,0), (-1,-1), 3.5)])); story.append(table); doc.build(story)
        content = out.getvalue(); filename, mime = stem + ".pdf", "application/pdf"
    path = root / filename; path.write_bytes(content)
    artifact, _ = DataRequestArtifact.objects.update_or_create(request=item, defaults={
        "private_path": str(path), "filename": filename, "mime_type": mime, "file_size": len(content), "row_count": len(rows),
        "sha256": hashlib.sha256(content).hexdigest(), "generated_by": user, "expires_at": timezone.now() + timedelta(days=30), "expired_at": None,
    })
    digest = hashlib.sha256(content).hexdigest()
    ExportLog.objects.create(export_type=item.requested_format, data_request_id=str(item.id), filters=item.scope,
        generated_by=user, file_reference=str(path), row_count=len(rows), mime_type=mime, file_size=len(content), sha256=digest)
    return artifact
