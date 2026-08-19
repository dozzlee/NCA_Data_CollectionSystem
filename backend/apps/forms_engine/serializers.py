from rest_framework import serializers
from .models import FormCodeCatalog, FormFamily, FormTemplate, FormSection, FormHeading, FormField, FormGrid, GridColumn, GridRow, SelectOption, KMZUploadRequirement, ValidationRule, FormRequirement, FormGapAssessment, FormWorkbookImport
from .workbook_import import normalize_form_code
from .rules import validate_rule_definition


class FormFamilySerializer(serializers.ModelSerializer):
    class Meta:
        model = FormFamily
        fields = "__all__"
        read_only_fields = ["frequency_decision_status", "frequency_decision_reference", "source_owner", "created_at"]


class FormCodeCatalogSerializer(serializers.ModelSerializer):
    next_version = serializers.CharField(read_only=True)

    class Meta:
        model = FormCodeCatalog
        fields = [
            "id", "code", "name", "frequency", "source_filename",
            "code_status", "next_version",
        ]


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
        fields = ["id", "row_label", "sort_order", "source_sheet", "source_rows"]


class GridColumnSerializer(serializers.ModelSerializer):
    class Meta:
        model = GridColumn
        fields = ["id", "column_code", "label", "field_type", "unit", "is_required", "sort_order", "source_sheet", "source_row"]


class FormGridSerializer(serializers.ModelSerializer):
    columns = GridColumnSerializer(many=True, read_only=True)
    fixed_rows = GridRowSerializer(many=True, read_only=True)

    class Meta:
        model = FormGrid
        fields = ["id", "grid_code", "title", "row_mode", "min_rows", "sort_order", "instructions", "source_sheet", "source_row", "columns", "fixed_rows"]


class FormHeadingSerializer(serializers.ModelSerializer):
    class Meta:
        model = FormHeading
        fields = ["id", "heading_code", "title", "level", "sort_order", "source_row"]

    def validate_level(self, value):
        if value not in {1, 2, 3}:
            raise serializers.ValidationError("Heading level must be between 1 and 3.")
        return value


class FormFieldSerializer(serializers.ModelSerializer):
    options = SelectOptionSerializer(many=True, read_only=True)
    heading_code = serializers.CharField(source="heading.heading_code", read_only=True)

    class Meta:
        model = FormField
        fields = [
            "id", "field_code", "label", "field_type", "unit", "heading", "heading_code",
            "is_required", "help_text", "formula",
            "conditional_on_field", "conditional_on_value",
            "sort_order", "export_name", "source_sheet", "source_row", "options",
        ]


class FormSectionSerializer(serializers.ModelSerializer):
    headings = FormHeadingSerializer(many=True, read_only=True)
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
            "kmz_upload_required", "kmz_requirements", "headings", "fields", "grids",
        ]


class FormTemplateListSerializer(serializers.ModelSerializer):
    class Meta:
        model = FormTemplate
        fields = ["id", "family", "form_code", "name", "sector", "provider_category", "frequency", "version", "effective_from", "status", "kmz_required", "excel_backup_enabled", "mapping_complete", "mapping_basis", "approval_status", "source_reference", "source_sha256", "approved_by", "approved_at", "published_at"]
        read_only_fields = [
            "family", "name", "sector", "provider_category", "mapping_basis",
            "status", "approval_status", "approved_by", "approved_at", "published_at",
        ]

    def validate_form_code(self, value):
        try:
            return normalize_form_code(value)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc))

    def validate(self, attrs):
        code = attrs.get("form_code", getattr(self.instance, "form_code", ""))
        version = attrs.get("version", getattr(self.instance, "version", ""))
        catalog = FormCodeCatalog.objects.filter(code=code, is_active=True).first()
        if not catalog:
            raise serializers.ValidationError({"form_code": "Select an available governed form code."})
        if not self.instance and version != catalog.next_version:
            raise serializers.ValidationError({"version": f"The next available version is {catalog.next_version}. Refresh and try again."})
        family = FormFamily.objects.filter(code=code).first()
        if family and FormTemplate.objects.filter(family=family, version=version).exclude(pk=getattr(self.instance, "pk", None)).exists():
            raise serializers.ValidationError({"version": "This form family and version already exist."})
        return attrs

    def create(self, validated_data):
        code = validated_data["form_code"]
        catalog = FormCodeCatalog.objects.get(code=code, is_active=True)
        validated_data.update({
            "name": catalog.name, "sector": catalog.sector,
            "provider_category": catalog.provider_category,
        })
        family, created = FormFamily.objects.get_or_create(
            code=code,
            defaults={
                "name": catalog.name, "canonical_frequency": validated_data["frequency"],
                "frequency_decision_status": "APPROVED",
                "code_status": catalog.code_status,
            },
        )
        if not created and family.canonical_frequency and family.canonical_frequency != validated_data["frequency"]:
            raise serializers.ValidationError({"frequency": "This form family already uses a different frequency."})
        validated_data["family"] = family
        if created:
            validated_data["mapping_basis"] = "CUSTOM"
        else:
            previous = family.versions.order_by("-published_at", "-created_at", "-id").first()
            validated_data["mapping_basis"] = previous.mapping_basis if previous else "CUSTOM"
        return super().create(validated_data)

    def validate_source_sha256(self, value):
        if value and (len(value) != 64 or any(char not in "0123456789abcdefABCDEF" for char in value)):
            raise serializers.ValidationError("Enter a 64-character hexadecimal SHA-256 hash.")
        return value.lower()


class FormTemplateDetailSerializer(serializers.ModelSerializer):
    sections = FormSectionSerializer(many=True, read_only=True)

    class Meta:
        model = FormTemplate
        fields = ["id", "family", "form_code", "name", "sector", "provider_category", "frequency", "version", "effective_from", "status", "kmz_required", "excel_backup_enabled", "instructions", "source_reference", "source_sha256", "mapping_complete", "mapping_basis", "approval_status", "approved_by", "approved_at", "published_at", "sections"]


class FormWorkbookImportSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source="created_by.name", read_only=True)
    resulting_template_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = FormWorkbookImport
        fields = [
            "id", "form_code", "name", "version", "sector", "provider_category", "frequency",
            "file_name", "file_size", "sha256", "scan_status", "scan_engine", "scan_details",
            "parse_status", "parser_version", "detected_schema", "warnings", "mapping_decisions",
            "created_by", "created_by_name", "resulting_template_id", "created_at", "updated_at",
        ]
        read_only_fields = [
            "form_code", "name", "version", "sector", "provider_category",
            "file_name", "file_size", "sha256", "scan_status", "scan_engine", "scan_details",
            "parse_status", "parser_version", "warnings", "created_by", "created_at", "updated_at",
        ]

    def validate_form_code(self, value):
        try:
            return normalize_form_code(value)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc))


class KMZRequirementSerializer(serializers.ModelSerializer):
    class Meta:
        model = KMZUploadRequirement
        fields = ["id", "form_template", "section", "category", "description", "is_required", "max_file_size_mb"]
