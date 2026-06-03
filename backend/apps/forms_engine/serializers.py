from rest_framework import serializers
from .models import FormTemplate, FormSection, FormField, FormGrid, GridColumn, GridRow, SelectOption, KMZUploadRequirement


class SelectOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = SelectOption
        fields = ["value", "label", "sort_order"]


class GridRowSerializer(serializers.ModelSerializer):
    class Meta:
        model = GridRow
        fields = ["id", "row_label", "sort_order"]


class GridColumnSerializer(serializers.ModelSerializer):
    class Meta:
        model = GridColumn
        fields = ["id", "column_code", "label", "field_type", "unit", "is_required", "sort_order"]


class FormGridSerializer(serializers.ModelSerializer):
    columns = GridColumnSerializer(many=True, read_only=True)
    fixed_rows = GridRowSerializer(many=True, read_only=True)

    class Meta:
        model = FormGrid
        fields = ["id", "grid_code", "title", "row_mode", "sort_order", "instructions", "columns", "fixed_rows"]


class FormFieldSerializer(serializers.ModelSerializer):
    options = SelectOptionSerializer(many=True, read_only=True)

    class Meta:
        model = FormField
        fields = [
            "id", "field_code", "label", "field_type", "unit",
            "is_required", "help_text", "formula",
            "conditional_on_field", "conditional_on_value",
            "sort_order", "export_name", "options",
        ]


class FormSectionSerializer(serializers.ModelSerializer):
    fields = FormFieldSerializer(many=True, read_only=True)
    grids = FormGridSerializer(many=True, read_only=True)

    class Meta:
        model = FormSection
        fields = ["id", "section_code", "title", "instructions", "sort_order", "kmz_upload_required", "fields", "grids"]


class FormTemplateListSerializer(serializers.ModelSerializer):
    class Meta:
        model = FormTemplate
        fields = ["id", "form_code", "name", "provider_category", "frequency", "version", "status", "kmz_required", "excel_backup_enabled"]


class FormTemplateDetailSerializer(serializers.ModelSerializer):
    sections = FormSectionSerializer(many=True, read_only=True)

    class Meta:
        model = FormTemplate
        fields = ["id", "form_code", "name", "provider_category", "frequency", "version", "status", "kmz_required", "excel_backup_enabled", "instructions", "sections"]


class KMZRequirementSerializer(serializers.ModelSerializer):
    class Meta:
        model = KMZUploadRequirement
        fields = ["id", "form_template", "section", "category", "description", "is_required", "max_file_size_mb"]
