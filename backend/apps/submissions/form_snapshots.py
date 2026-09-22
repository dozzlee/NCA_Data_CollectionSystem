"""Immutable form/schema snapshots used after a form definition is retired."""

import hashlib
import json


SNAPSHOT_VERSION = 1


def _ordered(queryset):
    return queryset.order_by("sort_order", "id")


def build_template_snapshot(template):
    sections = []
    for section in _ordered(template.sections.all()):
        headings = [{
            "id": row.id, "heading_code": row.heading_code, "title": row.title,
            "level": row.level, "sort_order": row.sort_order, "source_row": row.source_row,
        } for row in _ordered(section.headings.all())]
        fields = []
        for field in _ordered(section.fields.all()):
            fields.append({
                "id": field.id, "field_code": field.field_code, "label": field.label,
                "field_type": field.field_type, "unit": field.unit, "heading": field.heading_id,
                "heading_code": field.heading.heading_code if field.heading_id else None,
                "is_required": field.is_required, "help_text": field.help_text,
                "formula": field.formula, "conditional_on_field": field.conditional_on_field_id,
                "conditional_on_value": field.conditional_on_value, "sort_order": field.sort_order,
                "export_name": field.export_name, "source_sheet": field.source_sheet,
                "source_row": field.source_row,
                "options": [{"id": option.id, "value": option.value, "label": option.label,
                             "sort_order": option.sort_order}
                            for option in field.options.order_by("sort_order", "id")],
            })
        grids = []
        for grid in _ordered(section.grids.all()):
            grids.append({
                "id": grid.id, "grid_code": grid.grid_code, "title": grid.title,
                "row_mode": grid.row_mode, "min_rows": grid.min_rows,
                "sort_order": grid.sort_order, "instructions": grid.instructions,
                "source_sheet": grid.source_sheet, "source_row": grid.source_row,
                "columns": [{
                    "id": column.id, "column_code": column.column_code, "label": column.label,
                    "field_type": column.field_type, "unit": column.unit,
                    "is_required": column.is_required, "sort_order": column.sort_order,
                    "source_sheet": column.source_sheet, "source_row": column.source_row,
                } for column in _ordered(grid.columns.all())],
                "fixed_rows": [{
                    "id": row.id, "row_label": row.row_label, "sort_order": row.sort_order,
                    "source_sheet": row.source_sheet, "source_rows": row.source_rows,
                } for row in _ordered(grid.fixed_rows.all())],
            })
        sections.append({
            "id": section.id, "section_code": section.section_code, "title": section.title,
            "instructions": section.instructions, "sort_order": section.sort_order,
            "kmz_upload_required": section.kmz_upload_required, "headings": headings,
            "fields": fields, "grids": grids,
            "kmz_requirements": [{
                "id": requirement.id, "category": requirement.category,
                "description": requirement.description, "is_required": requirement.is_required,
                "max_file_size_mb": requirement.max_file_size_mb,
            } for requirement in template.kmz_requirements.filter(section=section).order_by("id")],
        })
    return {
        "snapshot_version": SNAPSHOT_VERSION,
        "id": template.id, "family": template.family_id, "form_code": template.form_code,
        "name": template.name, "sector": template.sector,
        "provider_category": template.provider_category, "frequency": template.frequency,
        "version": template.version, "effective_from": str(template.effective_from),
        "status": template.status, "kmz_required": template.kmz_required,
        "excel_backup_enabled": template.excel_backup_enabled,
        "instructions": template.instructions, "source_reference": template.source_reference,
        "source_sha256": template.source_sha256, "mapping_complete": template.mapping_complete,
        "mapping_basis": template.mapping_basis, "approval_status": template.approval_status,
        "created_at": template.created_at.isoformat() if template.created_at else None,
        "sections": sections,
        "validation_rules": [{
            "id": rule.id, "field": rule.field_id, "grid": rule.grid_id,
            "rule_type": rule.rule_type, "severity": rule.severity,
            "parameters": rule.parameters, "message": rule.message,
            "version": rule.version, "is_active": rule.is_active, "sort_order": rule.sort_order,
        } for rule in template.validation_rules.order_by("sort_order", "id")],
    }


def snapshot_hash(snapshot):
    payload = json.dumps(snapshot, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_value_target_snapshot(value):
    if value.field_id:
        field = value.field
        return f"field:{field.field_code}", {
            "target_type": "FIELD", "target_id": field.id, "field_code": field.field_code,
            "label": field.label, "field_type": field.field_type, "unit": field.unit,
            "definition": field.help_text, "sort_order": field.sort_order,
            "section_code": field.section.section_code, "section_title": field.section.title,
        }
    grid, column = value.grid, value.grid_column
    return f"grid:{grid.grid_code}:{value.grid_row_id}:{column.column_code}", {
        "target_type": "GRID_CELL", "target_id": f"{grid.id}:{value.grid_row_id}:{column.id}",
        "grid_code": grid.grid_code, "grid_title": grid.title,
        "grid_row_id": value.grid_row_id, "column_code": column.column_code,
        "label": column.label, "field_type": column.field_type, "unit": column.unit,
        "sort_order": column.sort_order, "section_code": grid.section.section_code,
        "section_title": grid.section.title,
    }


def snapshot_submission(submission):
    template = submission.expected.form_template
    if template is None:
        return submission.form_schema_snapshot
    snapshot = build_template_snapshot(template)
    submission.form_schema_snapshot = snapshot
    submission.form_schema_sha256 = snapshot_hash(snapshot)
    submission.form_schema_snapshot_version = SNAPSHOT_VERSION
    submission.save(update_fields=[
        "form_schema_snapshot", "form_schema_sha256", "form_schema_snapshot_version",
    ])
    for value in submission.values.select_related(
        "field__section", "grid__section", "grid_column",
    ):
        key, target = build_value_target_snapshot(value)
        value.target_key_snapshot = key
        value.target_snapshot = target
        value.save(update_fields=["target_key_snapshot", "target_snapshot"])
    return snapshot
