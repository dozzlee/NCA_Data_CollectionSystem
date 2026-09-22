import hashlib
import json
import shutil
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

from apps.audit.services import record_audit
from apps.forms_engine.models import FormField, FormGrid
from apps.uploads.models import SubmissionExcelBackup
from apps.uploads.scanner import scan_path
from apps.users.models import User

from ...models import Submission, SubmissionEvent, SubmissionValue
from ...readiness import refresh_submission_completion
from ...workflow import clone_for_nca_correction


class Command(BaseCommand):
    help = "Create an audited replacement of an approved submission from its source workbook provenance."

    def add_arguments(self, parser):
        parser.add_argument("--submission-id", type=int, required=True)
        parser.add_argument("--workbook", required=True)
        parser.add_argument("--reviewer-email", required=True)
        parser.add_argument("--commit", action="store_true")

    def handle(self, *args, **options):
        source = Path(options["workbook"]).resolve()
        if not source.is_file() or source.suffix.lower() != ".xlsx":
            raise CommandError("A readable .xlsx workbook is required.")
        submission = Submission.objects.select_related(
            "expected__form_template", "expected__provider", "expected__period", "submitted_by"
        ).get(pk=options["submission_id"])
        if submission.regulatory_status != "APPROVED":
            raise CommandError("The selected submission is not approved.")
        if hasattr(submission, "superseded_by"):
            raise CommandError("The selected submission already has a replacement version.")
        reviewer = User.objects.filter(email__iexact=options["reviewer_email"], role="NCA_ADMIN", is_active=True).first()
        if not reviewer:
            raise CommandError("An active NCA Admin reviewer is required.")

        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        scan = scan_path(source)
        if scan["status"] != "CLEAN":
            raise CommandError(f"Workbook scan did not pass: {scan['status']}")
        # Normal mode is deliberate here: several supplied monthly workbooks
        # omit reliable worksheet dimensions, which makes openpyxl's streaming
        # reader traverse an unbounded sparse range.
        workbook = load_workbook(source, read_only=False, data_only=True)
        try:
            period = submission.expected.period
            target_columns = {}
            for sheet in workbook.worksheets:
                if sheet.sheet_state != "visible":
                    continue
                matches = []
                for row_number, cells in enumerate(sheet.iter_rows(min_row=1, max_row=12), 1):
                    for column, cell in enumerate(cells, 1):
                        value = cell.value
                        if isinstance(value, datetime):
                            value = value.date()
                        if isinstance(value, date) and value.year == period.year and value.month == period.month:
                            matches.append(column)
                if len(set(matches)) != 1:
                    raise CommandError(
                        f'{sheet.title}: expected exactly one {period.year}-{period.month:02d} column, found {len(set(matches))}.'
                    )
                target_columns[sheet.title] = matches[0]

            mapped = []
            fields = FormField.objects.filter(section__form_template=submission.expected.form_template).exclude(
                field_type__in=["formula", "attachment"]
            )
            for field in fields:
                if not field.source_sheet or not field.source_row or field.source_sheet not in target_columns:
                    raise CommandError(f"Field {field.id} has incomplete workbook provenance.")
                raw = workbook[field.source_sheet].cell(field.source_row, target_columns[field.source_sheet]).value
                mapped.append(("FIELD", field, None, None, raw))
            grids = FormGrid.objects.filter(section__form_template=submission.expected.form_template).prefetch_related(
                "columns", "fixed_rows"
            )
            for grid in grids:
                if grid.row_mode != "FIXED":
                    raise CommandError(f"Repeatable grid {grid.id} cannot be updated by stable workbook-row provenance.")
                for row in grid.fixed_rows.all():
                    for index, column in enumerate(grid.columns.all()):
                        source_rows = list(row.source_rows or [])
                        source_row = source_rows[index] if index < len(source_rows) else column.source_row
                        source_sheet = row.source_sheet or column.source_sheet or grid.source_sheet
                        if not source_sheet or not source_row or source_sheet not in target_columns:
                            raise CommandError(f"Grid cell {grid.id}/{row.id}/{column.id} has incomplete workbook provenance.")
                        raw = workbook[source_sheet].cell(source_row, target_columns[source_sheet]).value
                        mapped.append(("GRID", grid, row, column, raw))
        finally:
            workbook.close()

        def converted(raw, field_type):
            if raw in (None, ""):
                return "", "MISSING"
            if field_type in {"number", "currency", "percentage"}:
                try:
                    return format(Decimal(str(raw).replace(",", "").replace("%", "")), "f"), "PROVIDED"
                except (InvalidOperation, ValueError):
                    raise CommandError(f"Invalid numeric workbook value: {raw!r}")
            if field_type == "date":
                if isinstance(raw, datetime):
                    raw = raw.date()
                return (raw.isoformat() if isinstance(raw, date) else str(raw)), "PROVIDED"
            if field_type in {"boolean", "declaration"}:
                normalized = str(raw).strip().lower()
                if normalized in {"yes", "true", "1"}:
                    return "true", "PROVIDED"
                if normalized in {"no", "false", "0"}:
                    return "false", "PROVIDED"
                raise CommandError(f"Invalid boolean workbook value: {raw!r}")
            return str(raw), "PROVIDED"

        preview = []
        changed = 0
        populated = 0
        blank = 0
        for kind, target, row, column, raw in mapped:
            field_type = target.field_type if kind == "FIELD" else column.field_type
            value, status = converted(raw, field_type)
            lookup = {"field": target} if kind == "FIELD" else {
                "grid": target, "grid_row_id": str(row.id), "grid_column": column,
            }
            old = submission.values.filter(**lookup).values_list("value", flat=True).first() or ""
            changed += int(old != value)
            populated += int(status == "PROVIDED")
            blank += int(status == "MISSING")
            preview.append((kind, target, row, column, value, status, old))
        result = {
            "source_submission": submission.submission_reference,
            "workbook_sha256": digest,
            "mapped_targets": len(preview),
            "populated": populated,
            "blank": blank,
            "changed": changed,
            "period_columns": {sheet: get_column_letter(column) for sheet, column in target_columns.items()},
            "scan_engine": scan["engine"],
        }
        self.stdout.write(json.dumps(result, indent=2, sort_keys=True))
        if not options["commit"]:
            self.stdout.write(self.style.WARNING("Dry run only. Re-run with --commit to create the audited replacement."))
            return

        upload_root = Path(settings.PRIVATE_UPLOAD_ROOT).resolve()
        relative_path = Path("excel_backup") / str(submission.id) / f"approved-correction-{digest[:12]}-{source.name}"
        stored = (upload_root / relative_path).resolve()
        if upload_root not in stored.parents:
            raise CommandError("Resolved private path is outside PRIVATE_UPLOAD_ROOT.")
        stored.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, stored)
        with transaction.atomic():
            submission = Submission.objects.select_for_update().select_related("expected").get(pk=submission.pk)
            replacement = clone_for_nca_correction(submission)
            replacement.form_schema_snapshot = submission.form_schema_snapshot
            replacement.form_schema_sha256 = submission.form_schema_sha256
            replacement.form_schema_snapshot_version = submission.form_schema_snapshot_version
            replacement.submitted_by = submission.submitted_by
            replacement.submitted_at = timezone.now()
            replacement.reviewed_by = reviewer
            replacement.reviewed_at = timezone.now()
            replacement.regulatory_status = "APPROVED"
            replacement.last_edited_by = reviewer
            replacement.last_edited_at = timezone.now()
            replacement.revision = 1
            replacement.save(update_fields=[
                "form_schema_snapshot", "form_schema_sha256", "form_schema_snapshot_version",
                "submitted_by", "submitted_at", "reviewed_by", "reviewed_at", "regulatory_status",
                "last_edited_by", "last_edited_at", "revision",
            ])
            for kind, target, row, column, value, status, old in preview:
                lookup = {"field": target} if kind == "FIELD" else {
                    "grid": target, "grid_row_id": str(row.id), "grid_column": column,
                }
                SubmissionValue.objects.update_or_create(
                    submission=replacement, **lookup,
                    defaults={"value": value, "value_status": status, "explanation": "",
                              "value_source": "EXCEL_IMPORT", "source_reference": f"approved-workbook:{digest}",
                              "updated_by": reviewer},
                )
            refresh_submission_completion(replacement)
            backup = SubmissionExcelBackup.objects.create(
                submission=replacement, file_name=source.name, file_size=source.stat().st_size,
                storage_path=str(relative_path).replace("\\", "/"), uploaded_by=reviewer,
                sha256=digest, scan_status="CLEAN", scan_engine=scan["engine"],
                scan_details=scan["details"], scanned_at=timezone.now(),
            )
            SubmissionEvent.objects.create(
                submission=replacement, actor=reviewer, event_type="APPROVED_VALUES_REPLACED_FROM_WORKBOOK",
                from_status="APPROVED", to_status="APPROVED", audience="BOTH",
                message="NCA created an audited approved replacement using the supplied September workbook.",
                metadata={"source_submission_id": submission.id, "workbook_backup_id": backup.id,
                          "workbook_sha256": digest, "mapped_targets": len(preview), "changed_targets": changed},
            )
            record_audit(
                user=reviewer, action="APPROVED_SUBMISSION_VALUES_REPLACED_FROM_WORKBOOK",
                entity_type="Submission", entity_id=replacement.id,
                before={"source_submission_id": submission.id, "source_reference": submission.submission_reference},
                after={"replacement_reference": replacement.submission_reference, "workbook_sha256": digest,
                       "mapped_targets": len(preview), "changed_targets": changed},
            )
        self.stdout.write(self.style.SUCCESS(
            f"Created approved replacement {replacement.submission_reference}; preserved {submission.submission_reference}."
        ))
