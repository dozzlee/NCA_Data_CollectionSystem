from django.contrib import admin

from .models import ComplianceFlag, EmailLog, EmailTemplate


@admin.register(EmailTemplate)
class EmailTemplateAdmin(admin.ModelAdmin):
    list_display = ("template_type", "subject", "updated_at")
    search_fields = ("template_type", "subject")


@admin.register(EmailLog)
class EmailLogAdmin(admin.ModelAdmin):
    list_display = ("subject", "provider", "status", "generated_by", "generated_at")
    list_filter = ("status", "compliance_stage", "generated_at")
    search_fields = ("subject", "provider__registered_name")


@admin.register(ComplianceFlag)
class ComplianceFlagAdmin(admin.ModelAdmin):
    list_display = ("provider", "flag_type", "status", "missing_field_count", "completion_percentage", "created_at")
    list_filter = ("flag_type", "status", "created_at")
    search_fields = ("provider__registered_name", "description")
