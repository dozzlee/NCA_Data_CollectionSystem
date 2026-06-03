from django.contrib import admin
from .models import ReportingPeriod, ExpectedSubmission, Submission, SubmissionValue, ReviewAction


@admin.register(ReportingPeriod)
class ReportingPeriodAdmin(admin.ModelAdmin):
    list_display = ["name", "frequency", "year", "month", "opens_at", "due_at", "status"]
    list_filter = ["frequency", "status", "year"]
    filter_horizontal = ["applicable_form_templates", "assigned_providers"]
    actions = ["activate_period"]

    def activate_period(self, request, queryset):
        for period in queryset.filter(status="DRAFT"):
            period.activate()
        self.message_user(request, "Periods activated and expected submissions generated.")
    activate_period.short_description = "Activate period and generate expected submissions"


@admin.register(ExpectedSubmission)
class ExpectedSubmissionAdmin(admin.ModelAdmin):
    list_display = ["provider", "form_template", "period", "workflow_status", "due_state", "assigned_officer"]
    list_filter = ["workflow_status", "due_state", "form_template", "period"]
    search_fields = ["provider__registered_name"]


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ["expected", "version", "completion_pct", "submitted_by", "submitted_at"]
    list_filter = ["expected__form_template"]
