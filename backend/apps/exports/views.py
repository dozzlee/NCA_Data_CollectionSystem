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
        if key == "sector" and value not in {"TELECOM", "BROADCASTING"}: return None, "Invalid sector."
        query_filters[ALLOWED_FILTERS[key]] = value
    return query_filters, None


class CSVExportView(APIView):
    permission_classes = [IsNCAUser]

    def post(self, request):
        filters = request.data.get("filters", {})
        query_filters, error = validate_filters(filters)
        if error: return Response({"detail": error}, status=400)
        expected = ExpectedSubmission.objects.filter(**query_filters)
        submission_ids = []
        for item in expected.prefetch_related("versions"):
            latest = item.versions.order_by("-version").first()
            if latest: submission_ids.append(latest.id)
        from apps.submissions.models import Submission
        rows = canonical_values(canonical_row_dicts(Submission.objects.filter(id__in=submission_ids)))
        output = io.StringIO(newline=""); output.write("\ufeff")
        writer = csv.writer(output, lineterminator="\r\n"); writer.writerow(CANONICAL_HEADERS)
        count = 0
        for row in rows:
            writer.writerow([spreadsheet_safe(value) for value in row]); count += 1
        content = output.getvalue().encode("utf-8")
        digest = hashlib.sha256(content).hexdigest()
        ExportLog.objects.create(export_type="CSV", filters=filters, generated_by=request.user, row_count=count,
            mime_type="text/csv", file_size=len(content), sha256=digest)
        record_audit(user=request.user, action="EXPORT_CSV", entity_type="Export", entity_id=digest,
            after={"rows": count, "filters": filters, "sha256": digest}, ip_address=request.META.get("REMOTE_ADDR"))
        filename = f"nca_export_{timezone.now().strftime('%Y%m%d_%H%M%S')}.csv"
        response = HttpResponse(content, content_type="text/csv; charset=utf-8")
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
