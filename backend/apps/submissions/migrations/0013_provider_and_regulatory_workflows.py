import re
from django.db import migrations, models


def _period_token(period):
    if period.frequency == "MONTHLY":
        return f"{period.year}-{period.month:02d}"
    if period.frequency == "QUARTERLY":
        return f"{period.year}-Q{period.quarter}"
    if period.frequency == "ANNUAL":
        return str(period.year)
    return f"{period.year}-SA-{period.id}"


def backfill_workflow_separation(apps, schema_editor):
    ExpectedSubmission = apps.get_model("submissions", "ExpectedSubmission")
    Submission = apps.get_model("submissions", "Submission")

    provider_statuses = {
        "NOT_STARTED": "IN_PROGRESS",
        "DRAFT": "IN_PROGRESS",
        "PENDING_APPROVAL": "AWAITING_APPROVAL",
        "PROVIDER_RESUBMITTED": "AWAITING_APPROVAL",
        "PROVIDER_CHANGES_REQUESTED": "CORRECTIONS_REQUIRED",
        "CORRECTION_REQUESTED": "AWAITING_APPROVAL",
    }
    for expected in ExpectedSubmission.objects.select_related("provider", "form_template", "period"):
        expected.provider_status = provider_statuses.get(expected.workflow_status, "CLOSED")
        form_code_value = (
            expected.form_template.form_code if expected.form_template_id
            else expected.form_code_snapshot
        ) or "FORM"
        form_code = re.sub(r"[^A-Z0-9-]+", "-", form_code_value.upper()).strip("-")
        provider_code = expected.provider.provider_code or f"P{expected.provider_id}"
        expected.form_reference = (
            f"FORM-{form_code}-{provider_code}-{_period_token(expected.period)}-F{expected.id}"
        )
        expected.save(update_fields=["provider_status", "form_reference"])

    for submission in Submission.objects.select_related("expected").prefetch_related("timeline_events"):
        event_types = set(submission.timeline_events.values_list("event_type", flat=True))
        if "SUBMISSION_APPROVED" in event_types:
            status = "APPROVED"
        elif "SUBMISSION_REJECTED" in event_types:
            status = "REJECTED"
        elif "CORRECTION_REQUESTED" in event_types:
            status = "RETURNED_FOR_CORRECTION"
        elif "SUBMISSION_REVIEW_STARTED" in event_types:
            status = "UNDER_REVIEW"
        elif "OFFICIALLY_SUBMITTED" in event_types or submission.submitted_at:
            status = "SUBMITTED"
        else:
            status = "DRAFT"
        submission.regulatory_status = status
        submission.save(update_fields=["regulatory_status"])


class Migration(migrations.Migration):
    dependencies = [("submissions", "0012_submissionvalue_source_reference_and_more")]

    operations = [
        migrations.AddField(
            model_name="expectedsubmission",
            name="provider_status",
            field=models.CharField(
                choices=[
                    ("IN_PROGRESS", "In Progress"),
                    ("AWAITING_APPROVAL", "Awaiting Approval"),
                    ("CORRECTIONS_REQUIRED", "Corrections Required"),
                    ("CLOSED", "Closed"),
                ],
                db_index=True,
                default="IN_PROGRESS",
                max_length=30,
            ),
        ),
        migrations.AddField(
            model_name="expectedsubmission",
            name="form_reference",
            field=models.CharField(editable=False, max_length=180, null=True, unique=True),
        ),
        migrations.AddField(
            model_name="submission",
            name="regulatory_status",
            field=models.CharField(
                choices=[
                    ("DRAFT", "Draft"),
                    ("SUBMITTED", "Submitted"),
                    ("UNDER_REVIEW", "Under Review"),
                    ("RETURNED_FOR_CORRECTION", "Returned for Correction"),
                    ("APPROVED", "Approved"),
                    ("REJECTED", "Rejected"),
                ],
                db_index=True,
                default="DRAFT",
                max_length=30,
            ),
        ),
        migrations.RunPython(backfill_workflow_separation, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="expectedsubmission",
            name="form_reference",
            field=models.CharField(editable=False, max_length=180, unique=True),
        ),
    ]
