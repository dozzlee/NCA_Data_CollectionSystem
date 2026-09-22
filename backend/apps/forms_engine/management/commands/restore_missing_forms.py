"""Restore only form codes absent from the active local database.

This is intentionally local-only and conservative: it copies schema metadata
from the project's pre-reset SQLite snapshot and never copies submissions or
provider data.
"""
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import connections, transaction
from django.db.utils import OperationalError

from apps.forms_engine.models import (
    FormCodeCatalog, FormFamily, FormTemplate, FormSection, FormHeading,
    FormField, SelectOption, FormGrid, GridColumn, GridRow, ValidationRule,
    FormRequirement, FormGapAssessment, KMZUploadRequirement,
)
from apps.users.models import User


RESTORE_CODES = ("DC-DBS05", "DC-SUB03", "TOWER-MAIN-ANNUAL")


class Command(BaseCommand):
    help = "Restore missing local form schemas from db.sqlite3 (dry-run unless --commit)."

    def add_arguments(self, parser):
        parser.add_argument("--commit", action="store_true", help="Persist the selective schema restoration.")

    def handle(self, *args, **options):
        source_path = Path(__file__).resolve().parents[4] / "db.sqlite3"
        if not source_path.exists():
            raise CommandError(f"Source snapshot not found: {source_path}")
        source_config = connections.databases["default"].copy()
        source_config.update({"ENGINE": "django.db.backends.sqlite3", "NAME": str(source_path)})
        connections.databases["restore_source"] = source_config
        try:
            FormTemplate.objects.using("restore_source").exists()
        except OperationalError as exc:
            raise CommandError(f"Source snapshot is unreadable: {exc}") from exc
        missing = [code for code in RESTORE_CODES if not FormFamily.objects.filter(code=code).exists()]
        self.stdout.write(f"Missing form codes: {', '.join(missing) or 'none'}")
        if not options["commit"]:
            self.stdout.write("Dry run only. Re-run with --commit to restore schema metadata.")
            return
        with transaction.atomic():
            for code in missing:
                self._restore_code(code)
        self.stdout.write(self.style.SUCCESS(f"Restored {len(missing)} form code(s); no submissions were copied."))

    def _source(self, model, **kwargs):
        return model.objects.using("restore_source").get(**kwargs)

    def _restore_code(self, code):
        source_family = self._source(FormFamily, code=code)
        family = FormFamily.objects.create(
            code=source_family.code, name=source_family.name,
            canonical_frequency="SEMI_ANNUAL" if source_family.canonical_frequency == "ANNUAL" else source_family.canonical_frequency,
            frequency_decision_status=source_family.frequency_decision_status,
            frequency_decision_reference=source_family.frequency_decision_reference,
            source_owner=source_family.source_owner, code_status=source_family.code_status,
        )
        catalog = FormCodeCatalog.objects.using("restore_source").filter(code=code).first()
        if catalog and not FormCodeCatalog.objects.filter(code=code).exists():
            FormCodeCatalog.objects.create(
                code=catalog.code, name=catalog.name, sector=catalog.sector,
                provider_category=catalog.provider_category,
                frequency="SEMI_ANNUAL" if catalog.frequency == "ANNUAL" else catalog.frequency,
                source_filename=catalog.source_filename, code_status=catalog.code_status,
                is_active=catalog.is_active, sort_order=catalog.sort_order,
            )
        source_template = FormTemplate.objects.using("restore_source").filter(family_id=source_family.id).order_by("-created_at", "-id").first()
        if not source_template:
            raise CommandError(f"No source template exists for {code}.")
        template = FormTemplate.objects.create(
            family=family, form_code=code, name=source_template.name, sector=source_template.sector,
            provider_category=source_template.provider_category,
            frequency="SEMI_ANNUAL" if source_template.frequency == "ANNUAL" else source_template.frequency,
            version=source_template.version, effective_from=source_template.effective_from,
            status="DRAFT", kmz_required=source_template.kmz_required,
            excel_backup_enabled=source_template.excel_backup_enabled, instructions=source_template.instructions,
            source_reference=source_template.source_reference, source_sha256=source_template.source_sha256,
            mapping_complete=source_template.mapping_complete, mapping_basis=source_template.mapping_basis,
            approval_status="DRAFT",
        )
        section_map, heading_map, field_map, grid_map = {}, {}, {}, {}
        source_sections = FormSection.objects.using("restore_source").filter(form_template_id=source_template.id).order_by("sort_order", "id")
        for old in source_sections:
            new = FormSection.objects.create(form_template=template, section_code=old.section_code, title=old.title,
                instructions=old.instructions, sort_order=old.sort_order, kmz_upload_required=old.kmz_upload_required)
            section_map[old.id] = new
            for heading in FormHeading.objects.using("restore_source").filter(section_id=old.id).order_by("sort_order", "id"):
                heading_map[heading.id] = FormHeading.objects.create(section=new, heading_code=heading.heading_code,
                    title=heading.title, level=heading.level, sort_order=heading.sort_order, source_row=heading.source_row)
            for grid in FormGrid.objects.using("restore_source").filter(section_id=old.id).order_by("sort_order", "id"):
                grid_map[grid.id] = FormGrid.objects.create(section=new, grid_code=grid.grid_code, title=grid.title,
                    row_mode=grid.row_mode, sort_order=grid.sort_order, instructions=grid.instructions,
                    min_rows=grid.min_rows, source_sheet=grid.source_sheet, source_row=grid.source_row)
        for old in FormField.objects.using("restore_source").filter(section_id__in=section_map).order_by("id"):
            field_map[old.id] = FormField.objects.create(section=section_map[old.section_id], heading=heading_map.get(old.heading_id),
                field_code=old.field_code, label=old.label, field_type=old.field_type, unit=old.unit,
                is_required=old.is_required, help_text=old.help_text, formula=old.formula,
                conditional_on_value=old.conditional_on_value, sort_order=old.sort_order, export_name=old.export_name,
                source_sheet=old.source_sheet, source_row=old.source_row)
        for old in SelectOption.objects.using("restore_source").filter(field_id__in=field_map):
            SelectOption.objects.create(field=field_map[old.field_id], value=old.value, label=old.label, sort_order=old.sort_order)
        for old in GridColumn.objects.using("restore_source").filter(grid_id__in=grid_map):
            GridColumn.objects.create(grid=grid_map[old.grid_id], column_code=old.column_code, label=old.label,
                field_type=old.field_type, unit=old.unit, is_required=old.is_required, sort_order=old.sort_order,
                source_sheet=old.source_sheet, source_row=old.source_row)
        for old in GridRow.objects.using("restore_source").filter(grid_id__in=grid_map):
            GridRow.objects.create(grid=grid_map.get(old.grid_id), row_label=old.row_label, sort_order=old.sort_order,
                source_sheet=old.source_sheet, source_rows=old.source_rows)
        for old in FormRequirement.objects.using("restore_source").filter(family_id=source_family.id):
            req = FormRequirement.objects.create(family=family, requirement_key=old.requirement_key,
                requirement_type=old.requirement_type, label=old.label, description=old.description,
                severity=old.severity, criteria=old.criteria, source_reference=old.source_reference, sort_order=old.sort_order)
            old_assessments = FormGapAssessment.objects.using("restore_source").filter(requirement_id=old.id, form_template_id=source_template.id)
            for assessment in old_assessments:
                FormGapAssessment.objects.create(form_template=template, requirement=req, status=assessment.status,
                    evidence=assessment.evidence, resolution_note=assessment.resolution_note)
        for old in KMZUploadRequirement.objects.using("restore_source").filter(form_template_id=source_template.id):
            KMZUploadRequirement.objects.create(form_template=template, section=section_map.get(old.section_id),
                category=old.category, description=old.description, is_required=old.is_required, max_file_size_mb=old.max_file_size_mb)
        for old in ValidationRule.objects.using("restore_source").filter(form_template_id=source_template.id):
            ValidationRule.objects.create(form_template=template, field=field_map.get(old.field_id), grid=grid_map.get(old.grid_id),
                rule_type=old.rule_type, severity=old.severity, parameters=old.parameters, message=old.message,
                version=old.version, is_active=old.is_active, sort_order=old.sort_order)
        # Resolve self-referential conditional fields after all fields exist.
        for old in FormField.objects.using("restore_source").filter(section_id__in=section_map).exclude(conditional_on_field_id=None):
            target = field_map.get(old.id)
            parent = field_map.get(old.conditional_on_field_id)
            if target and parent:
                target.conditional_on_field = parent
                target.save(update_fields=["conditional_on_field"])
