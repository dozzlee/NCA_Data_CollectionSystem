import csv
import hashlib
import io

from django.http import HttpResponse
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.services import record_audit
from apps.submissions.models import ExpectedSubmission, WORKFLOW_STATUSES
from apps.users.permissions import IsNCAUser
from .models import ExportLog
from .services import CANONICAL_HEADERS, canonical_row_dicts, canonical_values


ALLOWED_FILTERS = {
    "workflow_status": "workflow_status", "period": "period_id", "provider": "provider_id",
    "sector": "provider__sector", "provider_category": "provider__category",
    "form": "form_template_id", "assigned_officer": "assigned_officer_id", "due_state": "due_state",
}


def spreadsheet_safe(value):
    text = "" if value is None else str(value)
    return f"'{text}" if text.startswith(("=", "+", "-", "@", "\t", "\r")) else text


def validate_filters(filters):
    if not isinstance(filters, dict):
        return None, "filters must be an object."
    unknown = sorted(set(filters) - set(ALLOWED_FILTERS))
    if unknown:
        return None, f"Unsupported filters: {', '.join(unknown)}"
    query_filters = {}
    valid_workflows = {value for value, _ in WORKFLOW_STATUSES}
    for key, value in filters.items():
        if value in ("", None):
            continue
        if key in {"period", "provider", "form", "assigned_officer"}:
            if isinstance(value, bool): return None, f"{key} must be a numeric ID."
            try: value = int(value)
            except (TypeError, ValueError): return None, f"{key} must be a numeric ID."
        if key == "workflow_status" and value not in valid_workflows: return None, "Invalid workflow_status."
        if key == "workflow_status" and value != "APPROVED":
            return None, "Operational exports contain NCA-approved submissions only."
        if key == "sector" and value not in {"TELECOM", "BROADCASTING"}: return None, "Invalid sector."
        query_filters[ALLOWED_FILTERS[key]] = value
    return query_filters, None


def approved_submissions(query_filters):
    query_filters = dict(query_filters)
    query_filters["workflow_status"] = "APPROVED"
    expected = ExpectedSubmission.objects.filter(**query_filters)
    submission_ids = []
    for item in expected.prefetch_related("versions"):
        approved = item.versions.filter(reviewed_at__isnull=False).order_by("-version").first()
        if approved:
            submission_ids.append(approved.id)
    from apps.submissions.models import Submission
    return Submission.objects.filter(id__in=submission_ids)


def record_export(*, request, export_type, filters, content, row_count, mime_type):
    digest = hashlib.sha256(content).hexdigest()
    ExportLog.objects.create(
        export_type=export_type, filters=filters, generated_by=request.user,
        row_count=row_count, mime_type=mime_type, file_size=len(content), sha256=digest,
    )
    record_audit(
        user=request.user, action=f"EXPORT_{export_type}", entity_type="Export", entity_id=digest,
        after={"rows": row_count, "filters": filters, "sha256": digest, "approved_only": True},
        ip_address=request.META.get("REMOTE_ADDR"),
    )
    return digest


class CSVExportView(APIView):
    permission_classes = [IsNCAUser]

    def post(self, request):
        filters = request.data.get("filters", {})
        query_filters, error = validate_filters(filters)
        if error: return Response({"detail": error}, status=400)
        rows = canonical_values(canonical_row_dicts(approved_submissions(query_filters)))
        output = io.StringIO(newline=""); output.write("\ufeff")
        writer = csv.writer(output, lineterminator="\r\n"); writer.writerow(CANONICAL_HEADERS)
        count = 0
        for row in rows:
            writer.writerow([spreadsheet_safe(value) for value in row]); count += 1
        content = output.getvalue().encode("utf-8")
        record_export(request=request, export_type="CSV", filters=filters, content=content,
            row_count=count, mime_type="text/csv")
        filename = f"nca_export_{timezone.now().strftime('%Y%m%d_%H%M%S')}.csv"
        response = HttpResponse(content, content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        response["X-Content-Type-Options"] = "nosniff"
        return response


class PDFExportView(APIView):
    permission_classes = [IsNCAUser]

    def post(self, request):
        filters = request.data.get("filters", {})
        query_filters, error = validate_filters(filters)
        if error:
            return Response({"detail": error}, status=400)

        from reportlab.lib import colors
        from reportlab.lib.enums import TA_LEFT
        from reportlab.lib.pagesizes import A3, landscape
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import LongTable, PageBreak, Paragraph, SimpleDocTemplate, Spacer, TableStyle

        row_dicts = list(canonical_row_dicts(approved_submissions(query_filters)))
        output = io.BytesIO()
        document = SimpleDocTemplate(
            output, pagesize=landscape(A3), leftMargin=10 * mm, rightMargin=10 * mm,
            topMargin=12 * mm, bottomMargin=12 * mm,
            title="NCA approved operational data export",
        )
        styles = getSampleStyleSheet()
        cell_style = ParagraphStyle("ExportCell", parent=styles["BodyText"], fontSize=5.5, leading=6.5, alignment=TA_LEFT)
        header_style = ParagraphStyle("ExportHeader", parent=cell_style, textColor=colors.white, fontName="Helvetica-Bold")
        columns = [
            ("provider", "registered_company_name"), ("form", "form_code"), ("version", "form_version"),
            ("period", "period_name"), ("submission", "submission_id"), ("section", "section_name"),
            ("kind", "value_kind"), ("field/grid", "field_name"), ("grid row", "grid_row_label"),
            ("grid column", "grid_column_name"), ("value", "submitted_value"), ("status", "value_status"),
            ("explanation", "explanation"), ("disposition", "non_filled_disposition"),
            ("review", "latest_review_action"), ("compliance", "open_compliance_flags"),
        ]
        story = [
            Paragraph("NCA Approved Operational Data Export", styles["Title"]),
            Spacer(1, 3 * mm),
            Paragraph(
                f"Generated {timezone.now().isoformat()} · {len(row_dicts):,} canonical rows · Approved submissions only",
                styles["BodyText"],
            ),
            Paragraph(f"Filters: {filters or 'None'}", styles["BodyText"]),
            PageBreak(),
        ]
        table_data = [[Paragraph(label, header_style) for label, _ in columns]]
        for row in row_dicts:
            table_data.append([Paragraph(str(row.get(key, "") or ""), cell_style) for _, key in columns])
        table = LongTable(table_data, repeatRows=1, hAlign="LEFT")
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#002d5b")),
            ("GRID", (0, 0), (-1, -1), 0.2, colors.HexColor("#cbd5df")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f4f7f9")]),
            ("LEFTPADDING", (0, 0), (-1, -1), 2), ("RIGHTPADDING", (0, 0), (-1, -1), 2),
            ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]))
        story.append(table)
        document.build(story)
        content = output.getvalue()
        record_export(request=request, export_type="PDF", filters=filters, content=content,
            row_count=len(row_dicts), mime_type="application/pdf")
        filename = f"nca_export_{timezone.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        response = HttpResponse(content, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        response["X-Content-Type-Options"] = "nosniff"
        return response


class ExportLogListView(APIView):
    permission_classes = [IsNCAUser]
    def get(self, request):
        logs = ExportLog.objects.select_related("generated_by").order_by("-generated_at")[:50]
        return Response([{"id": item.id, "export_type": item.export_type, "filters": item.filters,
            "generated_by": item.generated_by.name, "generated_at": item.generated_at, "row_count": item.row_count,
            "mime_type": item.mime_type, "file_size": item.file_size, "sha256": item.sha256} for item in logs])
