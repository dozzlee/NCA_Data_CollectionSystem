from collections import defaultdict

from apps.forms_engine.models import FormField, FormGrid
from django.utils import timezone
from .validation import run_validation


ACCEPTED_NON_FILLED = {"NOT_APPLICABLE", "NOT_AVAILABLE", "NOT_REQUIRED"}
COMPLETE_STATUSES = {"PROVIDED", "SYSTEM_CALCULATED", *ACCEPTED_NON_FILLED}


def _is_value_complete(value):
    if value is None or value.value_status not in COMPLETE_STATUSES:
        return False
    if value.value_status == "PROVIDED":
        return bool(value.value.strip())
    if value.value_status in ACCEPTED_NON_FILLED:
        return bool(value.explanation.strip())
    return True


def _field_is_applicable(field, values_by_field):
    if not field.conditional_on_field_id or not field.conditional_on_value:
        return True
    parent = values_by_field.get(field.conditional_on_field_id)
    return bool(parent and parent.value == field.conditional_on_value)


def calculate_submission_readiness(submission, validation_scope="FULL"):
    template = submission.expected.form_template
    # Formula rules may materialize system-calculated values, so validation must
    # run before completeness is calculated.
    validation_run = run_validation(submission, validation_scope)
    values = list(
        submission.values.select_related(
            "field__section",
            "grid__section",
            "grid_column",
        )
    )
    values_by_field = {value.field_id: value for value in values if value.field_id}
    grid_values = {
        (value.grid_id, value.grid_row_id, value.grid_column_id): value
        for value in values
        if value.grid_id and value.grid_column_id
    }

    blockers = []
    completeness_warnings = []
    # Count every blank indicator (including optional indicators) separately
    # from transition blockers and required-field completion metrics.
    blank_indicator_count = 0
    required_total = 0
    completed_total = 0
    section_required = defaultdict(int)
    section_completed = defaultdict(int)

    fields = (
        FormField.objects.filter(section__form_template=template)
        .select_related("section", "conditional_on_field")
    )
    for field in fields:
        if not _field_is_applicable(field, values_by_field):
            continue
        # Completion measures all applicable indicators; requiredness only
        # controls whether missing data blocks submission.
        required_total += 1
        section_required[field.section.section_code] += 1
        if field.field_type == "attachment":
            current = submission.field_attachments.filter(field=field, is_current=True, scan_status="CLEAN").exists()
            if current:
                completed_total += 1
                section_completed[field.section.section_code] += 1
            else:
                if field.is_required:
                    blockers.append({"code": "REQUIRED_ATTACHMENT", "type": "ATTACHMENT", "id": field.id,
                        "section_code": field.section.section_code, "label": f"{field.label}: upload a clean Word, Excel, or PDF file"})
            continue
        value = values_by_field.get(field.id)
        if _is_value_complete(value):
            completed_total += 1
            section_completed[field.section.section_code] += 1
            continue
        blank_indicator_count += 1
        issue = {
            "code": "EXPLANATION_REQUIRED" if value and value.value_status in ACCEPTED_NON_FILLED else "MISSING_INDICATOR",
            "type": "FIELD",
            "id": field.id,
            "section_code": field.section.section_code,
            "label": field.label,
        }
        if field.field_type == "declaration":
            issue["code"] = "REQUIRED_DECLARATION"
            blockers.append(issue)
        elif value and value.value_status in ACCEPTED_NON_FILLED:
            blockers.append(issue)
        else:
            completeness_warnings.append(issue)

    grids = (
        FormGrid.objects.filter(section__form_template=template)
        .prefetch_related("columns", "fixed_rows")
        .select_related("section")
    )
    rows_by_grid = defaultdict(set)
    for value in values:
        if value.grid_id and value.grid_row_id:
            rows_by_grid[value.grid_id].add(value.grid_row_id)

    for grid in grids:
        columns = list(grid.columns.all())
        if grid.row_mode == "FIXED":
            row_ids = [str(row.id) for row in grid.fixed_rows.all()]
        else:
            row_ids = sorted(rows_by_grid.get(grid.id, set()))
            if len(row_ids) < grid.min_rows:
                completeness_warnings.append({
                    "code": "MISSING_GRID_ROWS", "type": "GRID", "id": grid.id,
                    "section_code": grid.section.section_code, "label": f"{grid.title} requires at least {grid.min_rows} row(s)",
                })
        for row_id in row_ids:
            for column in columns:
                value = grid_values.get((grid.id, row_id, column.id))
                if not _is_value_complete(value):
                    blank_indicator_count += 1
                required_total += 1
                section_required[grid.section.section_code] += 1
                value = grid_values.get((grid.id, row_id, column.id))
                if _is_value_complete(value):
                    completed_total += 1
                    section_completed[grid.section.section_code] += 1
                    continue
                completeness_warnings.append({
                    "code": "MISSING_GRID_CELL",
                    "type": "GRID_CELL",
                    "id": f"{grid.id}:{row_id}:{column.id}",
                    "section_code": grid.section.section_code,
                    "label": f"{grid.title} - {column.label}",
                })

    if template.kmz_required:
        requirements = template.kmz_requirements.filter(is_required=True).select_related("section")
        for requirement in requirements:
            required_total += 1
            section_code = requirement.section.section_code if requirement.section else ""
            section_required[section_code] += 1
            clean_upload = submission.kmz_uploads.filter(requirement=requirement, scan_status="CLEAN").exists()
            # Provider submission needs a clean file; final NCA approval separately
            # requires the regulatory review disposition to be ACCEPTED.
            if clean_upload:
                completed_total += 1
                section_completed[section_code] += 1
                continue
            blockers.append({
                "code": "REQUIRED_KMZ_UPLOAD",
                "type": "UPLOAD",
                "id": requirement.id,
                "section_code": requirement.section.section_code if requirement.section else "",
                "label": requirement.get_category_display(),
            })

    for result in validation_run.results.filter(severity="BLOCK"):
        blockers.append({"code": result.code, "type": result.target_type, "id": result.target_id, "section_code": "", "label": result.message})

    approved_overrides = submission.expected.readiness_overrides.filter(status="APPROVED", expires_at__gt=timezone.now())
    waived = {str(blocker_id) for override in approved_overrides for blocker_id in override.blocker_ids}
    non_overridable = {"REQUIRED_DECLARATION", "FORM_MAPPING_UNAVAILABLE", "IDENTITY_REQUIRED", "SECURITY_BLOCK"}
    blockers = [b for b in blockers if b["code"] in non_overridable or str(b["id"]) not in waived]
    completion_pct = round((completed_total / required_total) * 100, 2) if required_total else 100.0
    missing_types = defaultdict(int)
    for warning in completeness_warnings:
        missing_types[warning["type"]] += 1

    sections = []
    for section in template.sections.all():
        required = section_required[section.section_code]
        provided = section_completed[section.section_code]
        sections.append({
            "section_code": section.section_code,
            "title": section.title,
            "required": required,
            "provided": provided,
            "complete": provided >= required,
        })

    validation_issues = [
        {
            "id": result.id,
            "severity": result.severity,
            "target_type": result.target_type,
            "target_id": result.target_id,
            "code": result.code,
            "message": result.message,
            "details": result.details,
        }
        for result in validation_run.results.all()
    ]
    return {
        "completion_pct": completion_pct,
        "can_submit": not blockers,
        "missing_indicator_count": blank_indicator_count,
        # Compatibility field retained for existing clients; it now describes
        # requested indicators that are blank, not workflow blockers.
        "missing_required_count": len(completeness_warnings),
        "missing_by_type": dict(missing_types),
        "completeness_warnings": completeness_warnings,
        "blocking_issues": blockers,
        "validation_run_id": validation_run.id,
        "warning_count": validation_run.results.filter(severity="WARN").count(),
        "validation_issues": validation_issues,
        "sections": sections,
    }


def refresh_submission_completion(submission, validation_scope="FULL"):
    readiness = calculate_submission_readiness(submission, validation_scope)
    if float(submission.completion_pct) != readiness["completion_pct"]:
        submission.completion_pct = readiness["completion_pct"]
        submission.save(update_fields=["completion_pct"])
    return readiness
