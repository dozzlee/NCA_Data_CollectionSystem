import csv
import io
from django.http import HttpResponse
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from apps.users.permissions import IsNCAUser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.models import AuditEvent
from apps.submissions.models import ExpectedSubmission, SubmissionValue
from .models import ExportLog


class CSVExportView(APIView):
    permission_classes = [IsNCAUser]

    def post(self, request):
        filters = request.data.get("filters", {})
        qs = ExpectedSubmission.objects.select_related(
            "provider", "form_template", "period"
        ).filter(**{k: v for k, v in filters.items() if v})

        output = io.StringIO()
        writer = csv.writer(output)

        # Header — long/narrow format per PRD Section 13
        writer.writerow([
            "provider_id", "registered_company_name", "trade_name", "provider_category", "licence_type",
            "form_code", "form_name", "form_version", "reporting_frequency",
            "reporting_year", "reporting_month", "period_name", "due_date",
            "expected_submission_id", "submission_id", "submission_version",
            "workflow_status", "due_state", "submitted_by", "submitted_at",
            "reviewed_by", "reviewed_at",
            "section_code", "section_name", "field_code", "field_name",
            "field_type", "unit", "grid_name", "grid_row_label", "grid_column_name",
            "submitted_value", "value_status", "explanation",
            "export_generated_by", "export_generated_at",
        ])

        generated_at = timezone.now().isoformat()
        generated_by = request.user.email
        rows_written = 0

        for exp in qs:
            submission = exp.versions.order_by("-version").first()
            if not submission:
                continue

            values = SubmissionValue.objects.filter(submission=submission).select_related(
                "field__section", "grid", "grid_column"
            )
            for val in values:
                f = val.field
                if not f:
                    continue
                writer.writerow([
                    str(exp.provider.provider_id), exp.provider.registered_name,
                    exp.provider.trade_name, exp.provider.category, exp.provider.licence_type,
                    exp.form_template.form_code, exp.form_template.name,
                    exp.form_template.version, exp.form_template.frequency,
                    exp.period.year, exp.period.month or "",
                    exp.period.name, exp.period.due_at.date().isoformat(),
                    exp.id, submission.id, submission.version,
                    exp.workflow_status, exp.due_state,
                    submission.submitted_by.email if submission.submitted_by else "",
                    submission.submitted_at.isoformat() if submission.submitted_at else "",
                    submission.reviewed_by.email if submission.reviewed_by else "",
                    submission.reviewed_at.isoformat() if submission.reviewed_at else "",
                    f.section.section_code, f.section.title,
                    f.field_code, f.label, f.field_type, f.unit,
                    val.grid.title if val.grid else "",
                    val.grid_row_id,
                    val.grid_column.label if val.grid_column else "",
                    val.value, val.value_status, val.explanation,
                    generated_by, generated_at,
                ])
                rows_written += 1

        ExportLog.objects.create(
            export_type="CSV", filters=filters,
            generated_by=request.user, row_count=rows_written,
        )
        AuditEvent.objects.create(
            user=request.user, user_email=request.user.email, role=request.user.role,
            organization=request.user.organization.name if request.user.organization else "",
            action="EXPORT_CSV", entity_type="Export", entity_id="",
            after_value={"rows": rows_written, "filters": filters},
        )

        response = HttpResponse(output.getvalue(), content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="nca_export_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'
        return response


class ExportLogListView(APIView):
    permission_classes = [IsNCAUser]

    def get(self, request):
        logs = ExportLog.objects.select_related("generated_by").order_by("-generated_at")[:50]
        return Response([{
            "id": l.id, "export_type": l.export_type, "filters": l.filters,
            "generated_by": l.generated_by.name, "generated_at": l.generated_at,
            "row_count": l.row_count,
        } for l in logs])
