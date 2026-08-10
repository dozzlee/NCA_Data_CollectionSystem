"""Canonical long/narrow export rows shared by operational and governed exports."""
from apps.submissions.models import Submission


CANONICAL_HEADERS = [
    "request_reference", "provider_id", "registered_company_name", "trade_name",
    "provider_sector", "provider_category", "licence_type", "form_code", "form_name",
    "form_version", "reporting_frequency", "reporting_year", "reporting_month", "period_name",
    "effective_due_at", "expected_submission_id", "submission_id", "submission_version",
    "workflow_status", "due_state", "assigned_officer", "submitted_by", "submitted_at",
    "reviewed_by", "reviewed_at", "section_code", "section_name", "value_kind", "field_code",
    "field_name", "field_type", "unit", "grid_code", "grid_name", "grid_row_label",
    "grid_column_code", "grid_column_name", "submitted_value", "value_status", "explanation",
    "non_filled_disposition", "disposition_note", "disposition_reviewer", "disposition_at",
    "latest_review_action", "latest_review_comment", "open_compliance_flags",
]


def canonical_row_dicts(submissions, *, selected_field_ids=None, selected_column_ids=None, request_reference=""):
    selected_fields = set(selected_field_ids) if selected_field_ids is not None else None
    selected_columns = set(selected_column_ids) if selected_column_ids is not None else None
    submissions = submissions.select_related(
        "expected__provider", "expected__form_template", "expected__period",
        "expected__assigned_officer", "submitted_by", "reviewed_by",
    ).prefetch_related("values__field__section", "values__grid__section", "values__grid_column", "values__non_filled_disposition", "review_actions", "expected__compliance_flags")
    for submission in submissions:
        expected = submission.expected
        provider, form, period = expected.provider, expected.form_template, expected.period
        review = submission.review_actions.order_by("-created_at", "-id").first()
        flags = ", ".join(expected.compliance_flags.exclude(status="RESOLVED").values_list("flag_type", flat=True))
        for value in submission.values.all():
            if value.field_id:
                if selected_fields is not None and value.field_id not in selected_fields:
                    continue
                section = value.field.section
                kind, code, label, value_type, unit = "SCALAR", value.field.field_code, value.field.label, value.field.field_type, value.field.unit
                grid_code = grid_name = row_label = column_code = column_name = ""
            elif value.grid_column_id:
                if selected_columns is not None and value.grid_column_id not in selected_columns:
                    continue
                section = value.grid.section
                kind, code, label, value_type, unit = "GRID", "", "", value.grid_column.field_type, value.grid_column.unit
                grid_code, grid_name, row_label = value.grid.grid_code, value.grid.title, value.grid_row_id
                column_code, column_name = value.grid_column.column_code, value.grid_column.label
            else:
                continue
            disposition = getattr(value, "non_filled_disposition", None)
            yield {
                "request_reference": request_reference,
                "provider_id": str(provider.provider_id), "registered_company_name": provider.registered_name,
                "trade_name": provider.trade_name, "provider_sector": provider.sector,
                "provider_category": provider.category, "licence_type": provider.licence_type,
                "form_code": form.form_code, "form_name": form.name, "form_version": form.version,
                "reporting_frequency": form.frequency, "reporting_year": period.year,
                "reporting_month": period.month or "", "period_name": period.name,
                "effective_due_at": expected.effective_due_at.isoformat(),
                "expected_submission_id": expected.id, "submission_id": submission.id,
                "submission_version": submission.version, "workflow_status": expected.workflow_status,
                "due_state": expected.due_state,
                "assigned_officer": expected.assigned_officer.email if expected.assigned_officer else "",
                "submitted_by": submission.submitted_by.email if submission.submitted_by else "",
                "submitted_at": submission.submitted_at.isoformat() if submission.submitted_at else "",
                "reviewed_by": submission.reviewed_by.email if submission.reviewed_by else "",
                "reviewed_at": submission.reviewed_at.isoformat() if submission.reviewed_at else "",
                "section_code": section.section_code, "section_name": section.title, "value_kind": kind,
                "field_code": code, "field_name": label, "field_type": value_type, "unit": unit,
                "grid_code": grid_code, "grid_name": grid_name, "grid_row_label": row_label,
                "grid_column_code": column_code, "grid_column_name": column_name,
                "submitted_value": value.value, "value_status": value.value_status,
                "explanation": value.explanation,
                "non_filled_disposition": disposition.decision if disposition else "",
                "disposition_note": disposition.note if disposition else "",
                "disposition_reviewer": disposition.reviewed_by.email if disposition else "",
                "disposition_at": disposition.reviewed_at.isoformat() if disposition else "",
                "latest_review_action": review.action if review else "",
                "latest_review_comment": review.comment if review else "",
                "open_compliance_flags": flags,
            }


def canonical_values(rows):
    for row in rows:
        yield [row.get(header, "") for header in CANONICAL_HEADERS]
