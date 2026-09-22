from django.db import migrations


def reconcile_statuses(apps, schema_editor):
    Submission = apps.get_model("submissions", "Submission")
    for submission in Submission.objects.select_related("expected").prefetch_related("timeline_events"):
        events = set(submission.timeline_events.values_list("event_type", flat=True))
        if "SUBMISSION_APPROVED" in events:
            status = "APPROVED"
        elif "SUBMISSION_REJECTED" in events:
            status = "REJECTED"
        elif "CORRECTION_REQUESTED" in events:
            status = "RETURNED_FOR_CORRECTION"
        elif "SUBMISSION_REVIEW_STARTED" in events:
            status = "UNDER_REVIEW"
        elif "OFFICIALLY_SUBMITTED" in events or submission.submitted_at:
            status = "SUBMITTED"
        else:
            latest_id = Submission.objects.filter(expected_id=submission.expected_id).order_by("-version", "-id").values_list("id", flat=True).first()
            legacy = submission.expected.workflow_status if submission.id == latest_id else ""
            status = {
                "APPROVED": "APPROVED",
                "REJECTED": "REJECTED",
                "UNDER_REVIEW": "UNDER_REVIEW",
                "SUBMITTED": "SUBMITTED",
                "RESUBMITTED": "SUBMITTED",
            }.get(legacy, "DRAFT")
        if submission.regulatory_status != status:
            submission.regulatory_status = status
            submission.save(update_fields=["regulatory_status"])


class Migration(migrations.Migration):
    dependencies = [("submissions", "0013_provider_and_regulatory_workflows")]
    operations = [migrations.RunPython(reconcile_statuses, migrations.RunPython.noop)]
