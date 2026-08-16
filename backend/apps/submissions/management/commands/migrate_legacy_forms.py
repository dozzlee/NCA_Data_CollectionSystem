from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.forms_engine.models import FormTemplate
from apps.submissions.models import ExpectedSubmission, Submission, SubmissionValue


SAFE_STATUSES = {"NOT_STARTED", "DRAFT", "PENDING_APPROVAL"}


def build_mapping(expected, target):
    source = expected.form_template
    target_fields_by_code = {}
    for field in target.sections.prefetch_related("fields").all():
        for item in field.fields.all():
            target_fields_by_code.setdefault(item.field_code, []).append(item)
    target_grids_by_code = {}
    for section in target.sections.prefetch_related("grids__columns", "grids__fixed_rows").all():
        for grid in section.grids.all():
            target_grids_by_code.setdefault(grid.grid_code, []).append(grid)
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
            if not destination and len(target_fields_by_code.get(value.field.field_code, [])) == 1:
                destination = target_fields_by_code[value.field.field_code][0]
            if not destination:
                matches = target_fields_by_code.get(value.field.field_code, [])
                issues.append(
                    f"Ambiguous field {key[1]} ({len(matches)} destinations)" if len(matches) > 1
                    else f"Unmapped field {key[0]}.{key[1]}"
                )
            else:
                value_map.append((value, {"field": destination}))
            continue
        source_grid = value.grid
        destination_grid = target_grids.get((source_grid.section.section_code, source_grid.grid_code))
        if not destination_grid and len(target_grids_by_code.get(source_grid.grid_code, [])) == 1:
            destination_grid = target_grids_by_code[source_grid.grid_code][0]
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
        parser.add_argument("--target-template-id", type=int)

    def handle(self, *args, **options):
        queryset = ExpectedSubmission.objects.filter(workflow_status__in=SAFE_STATUSES).select_related("form_template__family")
        if options["expected_id"]:
            queryset = queryset.filter(id__in=options["expected_id"])
        reports, failures = [], []
        for expected in queryset:
            family = expected.form_template.family
            target = (
                FormTemplate.objects.filter(pk=options["target_template_id"]).first()
                if options["target_template_id"] else
                family.versions.filter(status="ACTIVE").order_by("-published_at", "-id").first() if family else None
            )
            if target and family and target.family_id != family.id:
                raise CommandError(f"Target template {target.id} is not in family {family.code}.")
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
                "due_state": source_expected.due_state, "assigned_officer": source_expected.assigned_officer,
                "recurring_assignment": source_expected.recurring_assignment,
                "manual_assignment": source_expected.manual_assignment},
        )
        if not replacement.versions.exists():
            submission = Submission.objects.create(expected=replacement, version=1)
            SubmissionValue.objects.bulk_create([
                SubmissionValue(submission=submission, value=source.value, value_status=source.value_status,
                    explanation=source.explanation, updated_by=source.updated_by, **destination)
                for source, destination in value_map
            ])
            from apps.submissions.workflow import emit_submission_event
            emit_submission_event(
                submission=submission, actor=None, event_type="FORM_VERSION_MIGRATED",
                message=f"Editable obligation migrated from {source_expected.form_template.form_code} v{source_expected.form_template.version} to v{target.version}.",
                from_status=source_expected.workflow_status, to_status=replacement.workflow_status,
                audience="BOTH", metadata={"source_expected_id": source_expected.id, "migration_report": report},
            )
        source_expected.workflow_status = "ARCHIVED"
        source_expected.replacement = replacement
        source_expected.migration_report = report
        source_expected.save(update_fields=["workflow_status", "replacement", "migration_report"])
