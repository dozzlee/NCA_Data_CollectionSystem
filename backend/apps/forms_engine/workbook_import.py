import re
from datetime import date, datetime
from pathlib import Path

from django.db import transaction
from openpyxl import load_workbook
from openpyxl.utils.cell import range_boundaries

from .models import (
    FormFamily, FormTemplate, FormSection, FormField, FormGrid,
    GridColumn, GridRow, SelectOption,
)


PARSER_VERSION = "xlsx-schema-v1"
FIXED_ROW_HEADERS = {"region", "category", "country", "operator", "brand", "service", "item", "location"}


def normalize_code(value, *, fallback="ITEM", max_length=100):
    code = re.sub(r"[^A-Z0-9]+", "_", str(value or "").strip().upper()).strip("_") or fallback
    return code[:max_length]


def normalize_form_code(value):
    code = re.sub(r"[^A-Z0-9-]+", "-", str(value or "").strip().upper()).strip("-")
    if not code or not re.fullmatch(r"[A-Z0-9]+(?:-[A-Z0-9]+)*", code):
        raise ValueError("Form code must contain uppercase letters, numbers and hyphens only.")
    return code


def _field_type(cell):
    value = cell.value
    if isinstance(value, str) and value.startswith("="):
        return "formula"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (date, datetime)):
        return "date"
    if isinstance(value, (int, float)):
        number_format = str(cell.number_format or "")
        return "percentage" if "%" in number_format else "number"
    return "text"


def _unit(label):
    match = re.search(r"\(([^()]{1,30})\)\s*$", str(label or ""))
    return match.group(1).strip() if match else ""


def _unique_code(label, used, prefix):
    base = normalize_code(label, fallback=prefix)
    candidate, index = base, 2
    while candidate in used:
        candidate = f"{base}_{index}"[:100]
        index += 1
    used.add(candidate)
    return candidate


def parse_workbook(path):
    warnings = []
    try:
        workbook = load_workbook(path, read_only=False, data_only=False, keep_links=True)
    except Exception as exc:
        raise ValueError(f"The workbook could not be read: {exc}") from exc

    if getattr(workbook, "_external_links", None):
        warnings.append({
            "code": "EXTERNAL_LINKS_REMOVED",
            "severity": "BLOCKING",
            "message": "The workbook contains external links. Remove them before confirming the generated template.",
        })

    sections = []
    visible_sheets = [sheet for sheet in workbook.worksheets if sheet.sheet_state == "visible"]
    if not visible_sheets:
        raise ValueError("The workbook has no visible worksheets.")

    for sheet_index, sheet in enumerate(visible_sheets, start=1):
        section = {
            "section_code": _unique_code(sheet.title, set(), f"SECTION_{sheet_index}"),
            "title": sheet.title,
            "instructions": "Generated from the workbook schema. Verify every field and table before publication.",
            "fields": [], "grids": [],
        }
        covered = set()
        grid_codes = set()
        for table in sheet.tables.values():
            min_col, min_row, max_col, max_row = range_boundaries(table.ref)
            headers = [sheet.cell(min_row, col).value for col in range(min_col, max_col + 1)]
            if not any(headers):
                continue
            grid = {
                "grid_code": _unique_code(table.displayName or table.name, grid_codes, "TABLE"),
                "title": table.displayName or table.name,
                "row_mode": "REPEATABLE", "min_rows": 0, "instructions": "",
                "columns": [], "fixed_rows": [],
            }
            column_codes = set()
            for offset, header in enumerate(headers):
                label = str(header or f"Column {offset + 1}").strip()
                sample = next((sheet.cell(row, min_col + offset) for row in range(min_row + 1, max_row + 1) if sheet.cell(row, min_col + offset).value not in (None, "")), sheet.cell(min_row, min_col + offset))
                grid["columns"].append({
                    "column_code": _unique_code(label, column_codes, f"COLUMN_{offset + 1}"),
                    "label": label, "field_type": _field_type(sample), "unit": _unit(label), "is_required": True,
                })
            first_header = str(headers[0] or "").strip().lower()
            if first_header in FIXED_ROW_HEADERS:
                labels = [str(sheet.cell(row, min_col).value).strip() for row in range(min_row + 1, max_row + 1) if sheet.cell(row, min_col).value not in (None, "")]
                if labels and len(set(labels)) == len(labels):
                    grid["row_mode"] = "FIXED"
                    grid["fixed_rows"] = labels
                    grid["min_rows"] = len(labels)
            section["grids"].append(grid)
            covered.update((row, col) for row in range(min_row, max_row + 1) for col in range(min_col, max_col + 1))

        field_codes = set()
        max_row, max_col = min(sheet.max_row, 2000), min(sheet.max_column, 100)
        for row in range(1, max_row + 1):
            populated = [(col, sheet.cell(row, col)) for col in range(1, max_col + 1) if sheet.cell(row, col).value not in (None, "") and (row, col) not in covered]
            if not populated:
                continue
            label_col, label_cell = populated[0]
            if not isinstance(label_cell.value, str) or str(label_cell.value).startswith("="):
                continue
            label = str(label_cell.value).strip()
            if len(label) > 255:
                warnings.append({"code": f"LONG_LABEL_{sheet_index}_{row}", "severity": "WARNING", "message": f"{sheet.title} row {row} has a label longer than 255 characters and was truncated."})
                label = label[:255]
            value_cell = sheet.cell(row, label_col + 1) if label_col < max_col else label_cell
            if label_cell.font.bold and value_cell.value in (None, ""):
                continue
            field_type = _field_type(value_cell)
            formula = str(value_cell.value)[1:] if field_type == "formula" else ""
            section["fields"].append({
                "field_code": _unique_code(label, field_codes, f"FIELD_{row}"),
                "label": label, "field_type": field_type, "unit": _unit(label),
                "is_required": True, "help_text": "", "formula": formula, "options": [],
            })
        if not section["fields"] and not section["grids"]:
            warnings.append({"code": f"EMPTY_SHEET_{sheet_index}", "severity": "WARNING", "message": f"{sheet.title} contains no detectable form fields or tables."})
        sections.append(section)

    if not any(section["fields"] or section["grids"] for section in sections):
        raise ValueError("No form fields or workbook tables could be detected.")
    return {"sections": sections}, warnings


def validate_schema(schema):
    sections = schema.get("sections") if isinstance(schema, dict) else None
    if not isinstance(sections, list) or not sections:
        raise ValueError("At least one section is required.")
    section_codes = set()
    for section in sections:
        code = normalize_code(section.get("section_code"), fallback="SECTION", max_length=50)
        if code in section_codes:
            raise ValueError(f"Duplicate section code: {code}.")
        section_codes.add(code)
        section["section_code"] = code
        if not str(section.get("title", "")).strip():
            raise ValueError(f"Section {code} requires a title.")
        field_codes, grid_codes = set(), set()
        for field in section.get("fields", []):
            field["field_code"] = _unique_code(field.get("field_code") or field.get("label"), field_codes, "FIELD")
            if field.get("field_type") not in dict(FormField._meta.get_field("field_type").choices):
                raise ValueError(f"Unsupported field type in {field['field_code']}.")
        for grid in section.get("grids", []):
            grid["grid_code"] = _unique_code(grid.get("grid_code") or grid.get("title"), grid_codes, "GRID")
            if not grid.get("columns"):
                raise ValueError(f"Grid {grid['grid_code']} requires at least one column.")
    return schema


@transaction.atomic
def create_template_from_import(workbook_import, user):
    if workbook_import.resulting_template_id:
        return workbook_import.resulting_template
    code = normalize_form_code(workbook_import.form_code)
    schema = validate_schema(workbook_import.detected_schema)
    family, created = FormFamily.objects.get_or_create(
        code=code,
        defaults={
            "name": workbook_import.name, "canonical_frequency": workbook_import.frequency,
            "frequency_decision_status": "APPROVED", "frequency_decision_reference": f"Workbook import {workbook_import.id}",
            "source_owner": user.name or user.email,
        },
    )
    if not created and family.canonical_frequency and family.canonical_frequency != workbook_import.frequency:
        raise ValueError("The form family already uses a different canonical frequency.")
    if FormTemplate.objects.filter(family=family, version=workbook_import.version).exists():
        raise ValueError("This form family and version already exist.")
    form = FormTemplate.objects.create(
        family=family, form_code=code, name=workbook_import.name, version=workbook_import.version,
        sector=workbook_import.sector, provider_category=workbook_import.provider_category,
        frequency=workbook_import.frequency, effective_from=date.today(), status="DRAFT",
        source_reference=f"Workbook: {workbook_import.file_name}", source_sha256=workbook_import.sha256,
        mapping_complete=True, mapping_basis="SOURCE_FORM", prepared_by=user,
    )
    for section_order, section_data in enumerate(schema["sections"], start=1):
        section = FormSection.objects.create(
            form_template=form, section_code=section_data["section_code"], title=str(section_data["title"])[:255],
            instructions=section_data.get("instructions", ""), sort_order=section_order,
        )
        for field_order, field_data in enumerate(section_data.get("fields", []), start=1):
            field = FormField.objects.create(
                section=section, field_code=field_data["field_code"], label=str(field_data.get("label") or field_data["field_code"])[:255],
                field_type=field_data.get("field_type", "text"), unit=str(field_data.get("unit", ""))[:50],
                is_required=bool(field_data.get("is_required", True)), help_text=field_data.get("help_text", ""),
                formula=field_data.get("formula", ""), sort_order=field_order,
            )
            SelectOption.objects.bulk_create([
                SelectOption(field=field, value=str(option)[:100], label=str(option)[:255], sort_order=index)
                for index, option in enumerate(field_data.get("options", []), start=1)
            ])
        for grid_order, grid_data in enumerate(section_data.get("grids", []), start=1):
            grid = FormGrid.objects.create(
                section=section, grid_code=grid_data["grid_code"], title=str(grid_data.get("title") or grid_data["grid_code"])[:255],
                row_mode=grid_data.get("row_mode", "REPEATABLE"), min_rows=max(0, int(grid_data.get("min_rows", 0))),
                instructions=grid_data.get("instructions", ""), sort_order=grid_order,
            )
            GridColumn.objects.bulk_create([
                GridColumn(
                    grid=grid, column_code=normalize_code(column.get("column_code") or column.get("label"), fallback=f"COLUMN_{index}"),
                    label=str(column.get("label") or f"Column {index}")[:255], field_type=column.get("field_type", "text"),
                    unit=str(column.get("unit", ""))[:50], is_required=bool(column.get("is_required", True)), sort_order=index,
                ) for index, column in enumerate(grid_data.get("columns", []), start=1)
            ])
            GridRow.objects.bulk_create([
                GridRow(grid=grid, row_label=str(label)[:255], sort_order=index)
                for index, label in enumerate(grid_data.get("fixed_rows", []), start=1)
            ])
    workbook_import.resulting_template = form
    workbook_import.parse_status = "CONFIRMED"
    workbook_import.detected_schema = schema
    workbook_import.save(update_fields=["resulting_template", "parse_status", "detected_schema", "updated_at"])
    return form
