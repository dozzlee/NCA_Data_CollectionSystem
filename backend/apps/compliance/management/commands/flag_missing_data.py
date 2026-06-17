from django.core.management.base import BaseCommand

from apps.compliance.models import ComplianceFlag
from apps.forms_engine.models import FormField
from apps.submissions.models import ExpectedSubmission, SubmissionValue


ACCEPTED_VALUE_STATUSES = {
    "PROVIDED",
    "NOT_APPLICABLE",
    "NOT_AVAILABLE",
    "NOT_REQUIRED",
    "SYSTEM_CALCULATED",
}


class Command(BaseCommand):
    help = "Automatically flag submissions with missing required data for compliance review"

    def handle(self, *args, **options):
        expected_submissions = ExpectedSubmission.objects.select_related(
            "provider",
            "form_template",
            "period",
        ).filter(
            workflow_status__in=[
                "NOT_STARTED",
                "DRAFT",
                "PENDING_APPROVAL",
                "SUBMITTED",
                "UNDER_REVIEW",
                "CORRECTION_REQUESTED",
                "RESUBMITTED",
            ]
        )

        created_count = 0
        updated_count = 0
        cleared_count = 0

        for expected in expected_submissions:
            created, updated, cleared = self.flag_missing_required_data(expected)
            created_count += created
            updated_count += updated
            cleared_count += cleared

            created, updated, cleared = self.flag_overdue_submission(expected)
            created_count += created
            updated_count += updated
            cleared_count += cleared

        self.stdout.write(
            self.style.SUCCESS(
                f"✓ Compliance flags created: {created_count}; updated: {updated_count}; cleared: {cleared_count}"
            )
        )

    def flag_missing_required_data(self, expected):
        latest_submission = expected.versions.order_by("-version").first()
        if not latest_submission:
            return (0, 0, 0)

        required_fields = FormField.objects.filter(
            section__form_template=expected.form_template,
            is_required=True,
        )
        total_required = required_fields.count()
        if total_required == 0:
            deleted, _ = ComplianceFlag.objects.filter(
                expected_submission=expected,
                flag_type="MISSING_DATA",
            ).delete()
            return (0, 0, deleted)

        provided_field_ids = set(
            SubmissionValue.objects.filter(
                submission=latest_submission,
                field__isnull=False,
                value_status__in=ACCEPTED_VALUE_STATUSES,
            )
            .exclude(value="")
            .values_list("field_id", flat=True)
        )
        missing_count = required_fields.exclude(id__in=provided_field_ids).count()
        completion_pct = int(((total_required - missing_count) / total_required) * 100)

        if missing_count == 0:
            deleted, _ = ComplianceFlag.objects.filter(
                expected_submission=expected,
                flag_type="MISSING_DATA",
            ).delete()
            return (0, 0, deleted)

        flag, created = ComplianceFlag.objects.update_or_create(
            expected_submission=expected,
            flag_type="MISSING_DATA",
            defaults={
                "provider": expected.provider,
                "description": f"{missing_count} required field(s) are missing from this submission.",
                "missing_field_count": missing_count,
                "completion_percentage": completion_pct,
                "status": "ACKNOWLEDGED" if expected.workflow_status in {"SUBMITTED", "UNDER_REVIEW"} else "OPEN",
            },
        )
        return (1, 0, 0) if created else (0, 1, 0)

    def flag_overdue_submission(self, expected):
        terminal_or_submitted = {
            "SUBMITTED",
            "UNDER_REVIEW",
            "RESUBMITTED",
            "APPROVED",
            "ARCHIVED",
        }
        if expected.due_state == "OVERDUE" and expected.workflow_status not in terminal_or_submitted:
            flag, created = ComplianceFlag.objects.update_or_create(
                expected_submission=expected,
                flag_type="OVERDUE",
                defaults={
                    "provider": expected.provider,
                    "description": "This submission is overdue and requires immediate attention.",
                    "status": "OPEN",
                },
            )
            return (1, 0, 0) if created else (0, 1, 0)

        deleted, _ = ComplianceFlag.objects.filter(
            expected_submission=expected,
            flag_type="OVERDUE",
        ).delete()
        return (0, 0, deleted)
