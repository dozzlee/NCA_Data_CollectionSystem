import hashlib
import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.audit.services import record_audit, verify_chain
from apps.data_requests.models import DataRequest, DataRequestEvent
from apps.forms_engine.models import FormFamily, FormTemplate, FormWorkbookImport
from apps.providers.models import ProviderFormAssignment
from apps.submissions.form_snapshots import snapshot_submission
from apps.submissions.models import (
    ExpectedSubmission, MonthlyReportArtifact, PeriodFormAssignment,
    ProviderWorkbookBaseline, ReportingPeriod, Submission, SubmissionValue,
)
from apps.uploads.models import SubmissionKMZUpload
from apps.users.models import User


CONFIRMATION = "CLEAR-ALL-FORM-DEFINITIONS"
ACTIVE_REQUEST_STATUSES = {"SUBMITTED", "UNDER_REVIEW", "CHANGES_REQUESTED"}


def _safe_private_path(root, stored_path):
    if not stored_path:
        return None
    root = Path(root).resolve()
    candidate = Path(stored_path)
    resolved = (candidate if candidate.is_absolute() else root / candidate).resolve()
    if resolved == root or root not in resolved.parents:
        raise CommandError(f"Unsafe private path outside {root}: {stored_path}")
    return resolved


def _state():
    families = FormFamily.objects.order_by("id")
    templates = FormTemplate.objects.order_by("id")
    imports = FormWorkbookImport.objects.order_by("id")
    expected = ExpectedSubmission.objects.filter(form_template__isnull=False).order_by("id")
    submissions = Submission.objects.filter(expected__form_template__isnull=False).order_by("id")
    baselines = ProviderWorkbookBaseline.objects.order_by("id")
    report = {
        "family_ids": list(families.values_list("id", flat=True)),
        "template_ids": list(templates.values_list("id", flat=True)),
        "workbook_import_ids": list(imports.values_list("id", flat=True)),
        "expected_submission_ids": list(expected.values_list("id", flat=True)),
        "submission_ids": list(submissions.values_list("id", flat=True)),
        "recurring_assignment_ids": list(ProviderFormAssignment.objects.values_list("id", flat=True).order_by("id")),
        "manual_assignment_ids": list(PeriodFormAssignment.objects.values_list("id", flat=True).order_by("id")),
        "baseline_ids": list(baselines.values_list("id", flat=True)),
    }
    report["counts"] = {key.removesuffix("_ids"): len(value) for key, value in report.items() if key.endswith("_ids")}
    canonical = json.dumps(report, sort_keys=True, separators=(",", ":"))
    report["report_hash"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return report, imports, expected, submissions, baselines


class Command(BaseCommand):
    help = "Snapshot historical submissions and permanently clear every form definition. Dry-run by default."

    def add_arguments(self, parser):
        parser.add_argument("--commit", action="store_true")
        parser.add_argument("--confirm", default="")
        parser.add_argument("--report-hash", default="")
        parser.add_argument("--backup-evidence", default="")
        parser.add_argument("--allow-production", action="store_true")
        parser.add_argument("--environment", default="")

    def handle(self, *args, **options):
        report, imports, expected_rows, submissions, baselines = _state()
        self.stdout.write(json.dumps(report, indent=2, default=str))
        if not options["commit"]:
            self.stdout.write(self.style.WARNING("Dry run only. No records or files changed."))
            return
        if options["confirm"] != CONFIRMATION:
            raise CommandError(f"Commit requires --confirm {CONFIRMATION}")
        if options["report_hash"] != report["report_hash"]:
            raise CommandError("The supplied report hash does not match the current target set. Run the dry run again.")
        backup = Path(options["backup_evidence"]).resolve() if options["backup_evidence"] else None
        if not backup or not backup.exists():
            raise CommandError("--backup-evidence must name an existing backup/evidence file.")
        environment = (options["environment"] or "").strip().lower()
        if not settings.DEBUG:
            if not options["allow_production"] or environment != "production":
                raise CommandError("Production reset requires --allow-production --environment production.")
        elif environment not in {"local", "development", "test"}:
            raise CommandError("Local reset requires --environment local, development or test.")
        if verify_chain():
            raise CommandError("Audit chain verification failed; reset refused.")

        private_root = getattr(settings, "PRIVATE_UPLOAD_ROOT", Path(settings.BASE_DIR) / "private_uploads")
        paths = []
        for row in imports:
            path = _safe_private_path(private_root, row.storage_path)
            if path: paths.append(path)
        for row in baselines:
            path = _safe_private_path(private_root, row.storage_path)
            if path: paths.append(path)

        with transaction.atomic():
            for expected in expected_rows.select_related("form_template"):
                template = expected.form_template
                expected.form_code_snapshot = template.form_code
                expected.form_name_snapshot = template.name
                expected.form_version_snapshot = template.version
                expected.form_frequency_snapshot = template.frequency
                expected.form_sector_snapshot = template.sector
                expected.form_provider_category_snapshot = template.provider_category
                expected.form_source_reference_snapshot = template.source_reference
                expected.form_created_at_snapshot = template.created_at
                expected.workflow_status_snapshot = expected.workflow_status
                expected.workflow_status = "ARCHIVED"
                expected.due_state = "CLOSED"
                expected.save(update_fields=[
                    "form_code_snapshot", "form_name_snapshot", "form_version_snapshot",
                    "form_frequency_snapshot", "form_sector_snapshot",
                    "form_provider_category_snapshot", "form_source_reference_snapshot",
                    "form_created_at_snapshot", "workflow_status", "due_state",
                    "workflow_status_snapshot",
                ])

            for submission in submissions.select_related("expected__form_template"):
                snapshot_submission(submission)

            missing_schema = submissions.filter(form_schema_snapshot={}).count()
            missing_targets = sum(
                row.values.filter(target_snapshot={}).count() for row in submissions
            )
            if missing_schema or missing_targets:
                raise CommandError(
                    f"Snapshot verification failed: {missing_schema} submissions and {missing_targets} values incomplete."
                )

            for upload in SubmissionKMZUpload.objects.filter(requirement__form_template__in=FormTemplate.objects.all()).select_related("requirement"):
                requirement = upload.requirement
                upload.requirement_snapshot = {
                    "id": requirement.id, "category": requirement.category,
                    "description": requirement.description, "is_required": requirement.is_required,
                    "max_file_size_mb": requirement.max_file_size_mb,
                }
                upload.save(update_fields=["requirement_snapshot"])

            for artifact in MonthlyReportArtifact.objects.filter(baseline__isnull=False).select_related("baseline"):
                baseline = artifact.baseline
                artifact.baseline_snapshot = {
                    "id": baseline.id, "provider_id": baseline.provider_id,
                    "form_template_id": baseline.form_template_id, "version": baseline.version,
                    "file_name": baseline.file_name, "sha256": baseline.sha256,
                }
                artifact.save(update_fields=["baseline_snapshot"])

            for request in DataRequest.objects.all():
                scope_ids = set((request.scope or {}).get("form_template_ids", []))
                if not scope_ids.intersection(report["template_ids"]):
                    continue
                old_status = request.status
                if request.status in ACTIVE_REQUEST_STATUSES:
                    request.status = "CHANGES_REQUESTED"
                    request.decision_note = "The selected forms were retired. Select newly created forms and resubmit."
                elif request.status in {"APPROVED", "PREPARING"}:
                    request.status = "GENERATION_FAILED"
                    request.decision_note = "Generation stopped because the selected form definitions were retired."
                else:
                    continue
                request.save(update_fields=["status", "decision_note", "updated_at"])
                DataRequestEvent.objects.create(
                    request=request, event_type="FORM_CATALOG_RESET", from_status=old_status,
                    to_status=request.status, message=request.decision_note,
                    metadata={"retired_template_ids": sorted(scope_ids.intersection(report["template_ids"]))},
                )

            for period in ReportingPeriod.objects.all():
                period.applicable_form_templates.clear()
            expected_rows.update(form_template=None, recurring_assignment=None, manual_assignment=None)
            MonthlyReportArtifact.objects.filter(baseline__isnull=False).update(baseline=None)
            SubmissionKMZUpload.objects.filter(requirement__isnull=False).update(requirement=None)
            # Detach the three mutually-dependent target FKs in one SQL update. Letting
            # Django's deletion collector null them separately creates an invalid
            # intermediate row on databases that check constraints immediately.
            SubmissionValue.objects.filter(submission_id__in=report["submission_ids"]).update(
                field=None, grid=None, grid_column=None,
            )
            PeriodFormAssignment.objects.all().delete()
            ProviderFormAssignment.objects.all().delete()
            baselines.delete()
            imports.delete()
            FormTemplate.objects.all().delete()
            FormFamily.objects.all().delete()

            if FormTemplate.objects.exists() or FormFamily.objects.exists():
                raise CommandError("Post-delete verification failed: form definitions remain.")
            actor = User.objects.filter(role="NCA_ADMIN", is_active=True).order_by("id").first()
            record_audit(
                user=actor, action="FORM_CATALOG_COMPLETELY_RESET",
                entity_type="FormCatalog", entity_id=report["report_hash"],
                before=report, after={
                    "families": 0, "templates": 0, "completed_at": timezone.now().isoformat(),
                    "backup_evidence": str(backup),
                },
            )
            transaction.on_commit(lambda: [path.unlink(missing_ok=True) for path in paths])

        self.stdout.write(self.style.SUCCESS("All form definitions were cleared; historical submissions use immutable snapshots."))
