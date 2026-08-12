from rest_framework import serializers
from .models import FormFamily, FormTemplate, FormSection, FormField, FormGrid, GridColumn, GridRow, SelectOption, KMZUploadRequirement, ValidationRule, FormRequirement, FormGapAssessment
from .rules import validate_rule_definition


class FormFamilySerializer(serializers.ModelSerializer):
    class Meta:
        model = FormFamily
        fields = "__all__"
        read_only_fields = ["frequency_decision_status", "frequency_decision_reference", "source_owner", "created_at"]


class ValidationRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = ValidationRule
        fields = "__all__"
        read_only_fields = ["form_template"]

    def validate(self, attrs):
        params = attrs.get("parameters", getattr(self.instance, "parameters", {}))
        rule_type = attrs.get("rule_type", getattr(self.instance, "rule_type", ""))
        form = self.context.get("form_template") or getattr(self.instance, "form_template", None)
        field = attrs.get("field", getattr(self.instance, "field", None))
        grid = attrs.get("grid", getattr(self.instance, "grid", None))
        try:
            validate_rule_definition(rule_type, params, form, field, grid)
        except Exception as exc:
            detail = getattr(exc, "message_dict", None) or getattr(exc, "messages", None) or str(exc)
            raise serializers.ValidationError(detail)
        return attrs


class FormRequirementSerializer(serializers.ModelSerializer):
    class Meta:
        model = FormRequirement
        fields = "__all__"
        read_only_fields = ["family"]


class FormGapAssessmentSerializer(serializers.ModelSerializer):
    requirement_key = serializers.CharField(source="requirement.requirement_key", read_only=True)
    requirement_type = serializers.CharField(source="requirement.requirement_type", read_only=True)
    requirement_label = serializers.CharField(source="requirement.label", read_only=True)
    requirement_description = serializers.CharField(source="requirement.description", read_only=True)
    severity = serializers.CharField(source="requirement.severity", read_only=True)
    owner_name = serializers.CharField(source="owner.name", read_only=True)
    resolved_by_name = serializers.CharField(source="resolved_by.name", read_only=True)

    class Meta:
        model = FormGapAssessment
        fields = "__all__"
        read_only_fields = ["form_template", "requirement", "assessed_by", "assessed_at", "resolved_by", "resolved_at"]


class SelectOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = SelectOption
        fields = ["id", "value", "label", "sort_order"]


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
        fields = ["id", "grid_code", "title", "row_mode", "min_rows", "sort_order", "instructions", "columns", "fixed_rows"]


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
    kmz_requirements = serializers.SerializerMethodField()

    def get_kmz_requirements(self, section):
        return [
            {
                "id": requirement.id,
                "category": requirement.category,
                "description": requirement.description,
                "is_required": requirement.is_required,
                "max_file_size_mb": requirement.max_file_size_mb,
            }
            for requirement in section.form_template.kmz_requirements.filter(section=section)
        ]

    class Meta:
        model = FormSection
        fields = [
            "id", "section_code", "title", "instructions", "sort_order",
            "kmz_upload_required", "kmz_requirements", "fields", "grids",
        ]


class FormTemplateListSerializer(serializers.ModelSerializer):
    class Meta:
        model = FormTemplate
        fields = ["id", "family", "form_code", "name", "sector", "provider_category", "frequency", "version", "status", "kmz_required", "excel_backup_enabled", "mapping_complete", "mapping_basis", "approval_status", "source_reference", "source_sha256", "approved_by", "approved_at", "published_at"]
        read_only_fields = ["status", "approval_status", "approved_by", "approved_at", "published_at"]

    def validate_source_sha256(self, value):
        if value and (len(value) != 64 or any(char not in "0123456789abcdefABCDEF" for char in value)):
            raise serializers.ValidationError("Enter a 64-character hexadecimal SHA-256 hash.")
        return value.lower()


class FormTemplateDetailSerializer(serializers.ModelSerializer):
    sections = FormSectionSerializer(many=True, read_only=True)

    class Meta:
        model = FormTemplate
        fields = ["id", "family", "form_code", "name", "sector", "provider_category", "frequency", "version", "status", "kmz_required", "excel_backup_enabled", "instructions", "source_reference", "source_sha256", "mapping_complete", "mapping_basis", "approval_status", "approved_by", "approved_at", "published_at", "sections"]


class KMZRequirementSerializer(serializers.ModelSerializer):
    class Meta:
        model = KMZUploadRequirement
        fields = ["id", "form_template", "section", "category", "description", "is_required", "max_file_size_mb"]
