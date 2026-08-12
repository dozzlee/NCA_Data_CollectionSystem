from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.forms_engine.models import FormTemplate
from apps.submissions.models import ExpectedSubmission, Submission, SubmissionValue


SAFE_STATUSES = {"NOT_STARTED", "DRAFT", "PENDING_APPROVAL"}


def build_mapping(expected, target):
    source = expected.form_template
    target_fields = {
        (field.section.section_code, field.field_code): field
        for field in target.sections.prefetch_related("fields").all()
        for field in field.fields.all()
    }
    target_grids = {
        (grid.section.section_code, grid.grid_code): grid
        for section in target.sections.prefetch_related("grids__columns", "grids__fixed_rows").all()
        for grid in section.grids.all()
    }
    value_map, issues = [], []
    latest = expected.versions.order_by("-version").first()
    if not latest:
        return value_map, issues
    for value in latest.values.select_related("field__section", "grid__section", "grid_column"):
        if value.field_id:
            key = (value.field.section.section_code, value.field.field_code)
            destination = target_fields.get(key)
            if not destination:
                issues.append(f"Unmapped field {key[0]}.{key[1]}")
            else:
                value_map.append((value, {"field": destination}))
            continue
        source_grid = value.grid
        destination_grid = target_grids.get((source_grid.section.section_code, source_grid.grid_code))
        if not destination_grid:
            issues.append(f"Unmapped grid {source_grid.section.section_code}.{source_grid.grid_code}")
            continue
        destination_column = destination_grid.columns.filter(column_code=value.grid_column.column_code).first()
        if not destination_column:
            issues.append(f"Unmapped grid column {source_grid.grid_code}.{value.grid_column.column_code}")
            continue
        row_id = value.grid_row_id
        if source_grid.row_mode == "FIXED":
            source_row = source_grid.fixed_rows.filter(pk=value.grid_row_id).first()
            destination_row = destination_grid.fixed_rows.filter(row_label=source_row.row_label if source_row else "").first()
            if not destination_row:
                issues.append(f"Unmapped fixed row {source_grid.grid_code}.{value.grid_row_id}")
                continue
            row_id = str(destination_row.id)
        value_map.append((value, {"grid": destination_grid, "grid_column": destination_column, "grid_row_id": row_id}))
    return value_map, issues


class Command(BaseCommand):
    help = "Dry-run or safely migrate non-official legacy obligations to the active corrected form versions."

    def add_arguments(self, parser):
        parser.add_argument("--commit", action="store_true")
        parser.add_argument("--expected-id", action="append", type=int)

    def handle(self, *args, **options):
        queryset = ExpectedSubmission.objects.filter(workflow_status__in=SAFE_STATUSES).select_related("form_template__family")
        if options["expected_id"]:
            queryset = queryset.filter(id__in=options["expected_id"])
        reports, failures = [], []
        for expected in queryset:
            family = expected.form_template.family
            target = family.versions.filter(status="ACTIVE", mapping_basis="PRD_SECTION_11").order_by("-published_at", "-id").first() if family else None
            if not target or target.id == expected.form_template_id:
                continue
            value_map, issues = build_mapping(expected, target)
            report = {"expected_id": expected.id, "from": f"{expected.form_template.form_code} v{expected.form_template.version}",
                "to": f"{target.form_code} v{target.version}", "status": expected.workflow_status,
                "mapped_values": len(value_map), "issues": issues}
            reports.append(report)
            if issues:
                failures.append(report); continue
            if options["commit"]:
                self._migrate(expected, target, value_map, report)
        for report in reports:
            self.stdout.write(str(report))
        if failures and options["commit"]:
            raise CommandError(f"Migration aborted for {len(failures)} obligation(s) with unmapped data.")
        self.stdout.write(self.style.SUCCESS(f"{'Migrated' if options['commit'] else 'Dry-run checked'} {len(reports) - len(failures)} obligation(s); {len(failures)} blocked."))

    @transaction.atomic
    def _migrate(self, source_expected, target, value_map, report):
        replacement, _ = ExpectedSubmission.objects.get_or_create(
            provider=source_expected.provider, form_template=target, period=source_expected.period,
            defaults={"workflow_status": "NOT_STARTED" if source_expected.workflow_status == "NOT_STARTED" else "DRAFT",
                "due_state": source_expected.due_state, "assigned_officer": source_expected.assigned_officer},
        )
        if value_map and not replacement.versions.exists():
            submission = Submission.objects.create(expected=replacement, version=1)
            SubmissionValue.objects.bulk_create([
                SubmissionValue(submission=submission, value=source.value, value_status=source.value_status,
                    explanation=source.explanation, updated_by=source.updated_by, **destination)
                for source, destination in value_map
            ])
        source_expected.workflow_status = "ARCHIVED"
        source_expected.replacement = replacement
        source_expected.migration_report = report
        source_expected.save(update_fields=["workflow_status", "replacement", "migration_report"])
