import shutil
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.users.models import User
from apps.submissions.models import (
    ExpectedSubmission, ProviderWorkbookBaseline, ReportingPeriod, Submission, SubmissionValue,
)
from apps.submissions.monthly_reports import generate_monthly_report


class Command(BaseCommand):
    help = "Generate a non-persistent verification workbook through the production report service."

    def add_arguments(self, parser):
        parser.add_argument("--baseline", type=int, required=True)
        parser.add_argument("--year", type=int, required=True)
        parser.add_argument("--month", type=int, required=True)
        parser.add_argument("--output", required=True)
        parser.add_argument("--actor", default="admin@nca.org.gh")

    def handle(self, *args, **options):
        baseline = ProviderWorkbookBaseline.objects.select_related("provider", "form_template").filter(
            pk=options["baseline"], status="ACTIVE",
        ).first()
        if not baseline:
            raise CommandError("Active baseline not found.")
        actor = User.objects.filter(email__iexact=options["actor"]).first()
        if not actor:
            raise CommandError("Verification actor not found.")
        output = Path(options["output"])
        if output.suffix.lower() != ".xlsx":
            raise CommandError("Verification output must be .xlsx.")
        output.parent.mkdir(parents=True, exist_ok=True)

        with transaction.atomic():
            period = ReportingPeriod.objects.create(
                name=f"Workbook verification {options['year']}-{options['month']:02d}",
                frequency="MONTHLY", year=options["year"], month=options["month"],
                opens_at=timezone.now(), due_at=timezone.now(), status="ACTIVE", created_by=actor,
            )
            expected = ExpectedSubmission.objects.create(
                provider=baseline.provider, form_template=baseline.form_template, period=period,
                workflow_status="SUBMITTED", due_state="CLOSED",
            )
            submission = Submission.objects.create(
                expected=expected, version=1, submitted_by=actor, submitted_at=timezone.now(),
            )
            for index, mapping in enumerate(
                baseline.indicator_mappings.filter(value_kind="INPUT").select_related("field", "grid", "grid_row", "grid_column"),
                start=1,
            ):
                if mapping.field_id:
                    SubmissionValue.objects.create(
                        submission=submission, field=mapping.field, value=str(index), value_status="PROVIDED", updated_by=actor,
                    )
                elif mapping.grid_id:
                    SubmissionValue.objects.create(
                        submission=submission, grid=mapping.grid, grid_row_id=str(mapping.grid_row_id),
                        grid_column=mapping.grid_column, value=str(index), value_status="PROVIDED", updated_by=actor,
                    )
            artifact = generate_monthly_report(submission.id, actor)
            shutil.copy2(artifact.private_path, output)
            transaction.set_rollback(True)
        self.stdout.write(self.style.SUCCESS(f"Verified workbook generated at {output}"))
