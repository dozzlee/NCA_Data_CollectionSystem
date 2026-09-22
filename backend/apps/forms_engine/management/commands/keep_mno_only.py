import hashlib
import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.audit.services import record_audit, verify_chain
from apps.forms_engine.models import FormFamily, FormTemplate, FormWorkbookImport
from apps.providers.models import ProviderFormAssignment
from apps.submissions.form_snapshots import snapshot_submission
from apps.submissions.models import ExpectedSubmission, MonthlyReportArtifact, PeriodFormAssignment, ProviderWorkbookBaseline, Submission, SubmissionValue, ReportingPeriod
from apps.uploads.models import SubmissionKMZUpload
from apps.users.models import User


CONFIRMATION = "KEEP-MNO-ONLY"


def safe_path(root, stored):
    if not stored:
        return None
    base = Path(root).resolve()
    path = (Path(stored) if Path(stored).is_absolute() else base / stored).resolve()
    if path == base or base not in path.parents:
        raise CommandError(f"Unsafe private path: {stored}")
    return path


def target_state():
    families = FormFamily.objects.exclude(code="MNO-MONTHLY").order_by("id")
    templates = FormTemplate.objects.filter(family__in=families).order_by("id")
    expected = ExpectedSubmission.objects.filter(form_template__in=templates).order_by("id")
    submissions = Submission.objects.filter(expected__in=expected).order_by("id")
    imports = FormWorkbookImport.objects.filter(resulting_template__in=templates).order_by("id")
    baselines = ProviderWorkbookBaseline.objects.filter(form_template__in=templates).order_by("id")
    recurring = ProviderFormAssignment.objects.filter(form_family__in=families).order_by("id")
    manual = PeriodFormAssignment.objects.filter(form_template__in=templates).order_by("id")
    report = {
        "family_ids": list(families.values_list("id", flat=True)),
        "template_ids": list(templates.values_list("id", flat=True)),
        "expected_ids": list(expected.values_list("id", flat=True)),
        "submission_ids": list(submissions.values_list("id", flat=True)),
        "import_ids": list(imports.values_list("id", flat=True)),
        "baseline_ids": list(baselines.values_list("id", flat=True)),
        "recurring_assignment_ids": list(recurring.values_list("id", flat=True)),
        "manual_assignment_ids": list(manual.values_list("id", flat=True)),
    }
    report["counts"] = {key.removesuffix("_ids"): len(value) for key, value in report.items() if key.endswith("_ids")}
    report["report_hash"] = hashlib.sha256(json.dumps(report, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return report, families, templates, expected, submissions, imports, baselines, recurring, manual


class Command(BaseCommand):
    help = "Remove all form definitions except MNO-MONTHLY; dry-run by default."

    def add_arguments(self, parser):
        parser.add_argument("--commit", action="store_true")
        parser.add_argument("--confirm", default="")
        parser.add_argument("--environment", default="local")
        parser.add_argument("--report-hash", default="")

    def handle(self, *args, **options):
        report, families, templates, expected, submissions, imports, baselines, recurring, manual = target_state()
        self.stdout.write(json.dumps(report, indent=2))
        if not options["commit"]:
            self.stdout.write(self.style.WARNING("Dry run only. No records or files changed."))
            return
        if not settings.DEBUG or options["environment"].lower() not in {"local", "development", "test"}:
            raise CommandError("This cleanup is restricted to local/development/test settings.")
        if options["confirm"] != CONFIRMATION:
            raise CommandError(f"Commit requires --confirm {CONFIRMATION}")
        if options["report_hash"] and options["report_hash"] != report["report_hash"]:
            raise CommandError("The supplied dry-run hash does not match the current target set.")
        if verify_chain():
            raise CommandError("Audit chain verification failed; cleanup refused.")
        private_root = getattr(settings, "PRIVATE_UPLOAD_ROOT", Path(settings.BASE_DIR) / "private_uploads")
        paths = [safe_path(private_root, item.storage_path) for item in list(imports) + list(baselines)]
        paths = [path for path in paths if path]
        with transaction.atomic():
            for item in expected.select_related("form_template"):
                template = item.form_template
                item.form_code_snapshot = template.form_code
                item.form_name_snapshot = template.name
                item.form_version_snapshot = template.version
                item.form_frequency_snapshot = template.frequency
                item.form_sector_snapshot = template.sector
                item.form_provider_category_snapshot = template.provider_category
                item.form_source_reference_snapshot = template.source_reference
                item.form_created_at_snapshot = template.created_at
                item.workflow_status_snapshot = item.workflow_status
                item.workflow_status = "ARCHIVED"
                item.due_state = "CLOSED"
                item.save(update_fields=["form_code_snapshot", "form_name_snapshot", "form_version_snapshot", "form_frequency_snapshot", "form_sector_snapshot", "form_provider_category_snapshot", "form_source_reference_snapshot", "form_created_at_snapshot", "workflow_status_snapshot", "workflow_status", "due_state"])
            for item in submissions:
                snapshot_submission(item)
            if submissions.filter(form_schema_snapshot={}).exists() or any(item.values.filter(target_snapshot={}).exists() for item in submissions):
                raise CommandError("Snapshot verification failed; nothing was deleted.")
            SubmissionValue.objects.filter(submission__in=submissions).update(field=None, grid=None, grid_column=None)
            SubmissionKMZUpload.objects.filter(requirement__form_template__in=templates).update(requirement=None)
            MonthlyReportArtifact.objects.filter(baseline__in=baselines).update(baseline=None)
            for period in ReportingPeriod.objects.all():
                period.applicable_form_templates.remove(*templates)
            expected.update(form_template=None, recurring_assignment=None, manual_assignment=None)
            recurring.delete(); manual.delete(); baselines.delete(); imports.delete(); templates.delete(); families.delete()
            if FormTemplate.objects.exclude(form_code="MNO-MONTHLY").exists() or FormFamily.objects.exclude(code="MNO-MONTHLY").exists():
                raise CommandError("Non-MNO form definitions remain after cleanup.")
            actor = User.objects.filter(role="NCA_ADMIN", is_active=True).order_by("id").first()
            record_audit(user=actor, action="NON_MNO_FORM_CATALOG_CLEANUP", entity_type="FormCatalog", entity_id=report["report_hash"], before=report, after={"kept_form_code": "MNO-MONTHLY", "completed_at": timezone.now().isoformat()})
            transaction.on_commit(lambda: [path.unlink(missing_ok=True) for path in paths])
        self.stdout.write(self.style.SUCCESS("All non-MNO form definitions were removed; MNO-MONTHLY was preserved."))
