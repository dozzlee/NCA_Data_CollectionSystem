from django.contrib import admin
from .models import FormTemplate, FormSection, FormField, FormGrid, GridColumn, GridRow, KMZUploadRequirement


class FormSectionInline(admin.TabularInline):
    model = FormSection
    extra = 0
    fields = ["section_code", "title", "sort_order", "kmz_upload_required"]


class FormFieldInline(admin.TabularInline):
    model = FormField
    extra = 0
    fields = ["field_code", "label", "field_type", "unit", "is_required", "sort_order"]


class GridColumnInline(admin.TabularInline):
    model = GridColumn
    extra = 0
    fields = ["column_code", "label", "field_type", "unit", "is_required", "sort_order"]


class GridRowInline(admin.TabularInline):
    model = GridRow
    extra = 0
    fields = ["row_label", "sort_order"]


@admin.register(FormTemplate)
class FormTemplateAdmin(admin.ModelAdmin):
    list_display = ["form_code", "name", "provider_category", "frequency", "version", "status", "kmz_required"]
    list_filter = ["frequency", "status", "provider_category", "kmz_required"]


@admin.register(FormSection)
class FormSectionAdmin(admin.ModelAdmin):
    list_display = ["form_template", "section_code", "title", "sort_order", "kmz_upload_required"]
    list_filter = ["form_template", "kmz_upload_required"]
    inlines = [FormFieldInline]


@admin.register(FormGrid)
class FormGridAdmin(admin.ModelAdmin):
    list_display = ["section", "grid_code", "title", "row_mode", "sort_order"]
    inlines = [GridColumnInline, GridRowInline]


@admin.register(KMZUploadRequirement)
class KMZUploadRequirementAdmin(admin.ModelAdmin):
    list_display = ["form_template", "section", "category", "is_required", "max_file_size_mb"]
    list_filter = ["form_template", "category", "is_required"]
