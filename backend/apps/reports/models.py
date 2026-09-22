import uuid
from django.db import models


class ReportTemplate(models.Model):
    REPORT_TYPES = [("QUARTERLY_BULLETIN", "Quarterly Statistical Bulletin"), ("CIR", "Communications Industry Report")]
    STATUSES = [("DRAFT", "Draft"), ("ACTIVE", "Active"), ("ARCHIVED", "Archived")]

    report_type = models.CharField(max_length=30, choices=REPORT_TYPES, db_index=True)
    name = models.CharField(max_length=255)
    version = models.PositiveIntegerField()
    effective_year = models.PositiveIntegerField()
    effective_quarter = models.PositiveSmallIntegerField(null=True, blank=True)
    filename_pattern = models.CharField(max_length=255)
    source_reference = models.CharField(max_length=255)
    source_sha256 = models.CharField(max_length=64)
    immutable_blocks = models.JSONField(default=list)
    field_mappings = models.JSONField(default=list)
    calculation_mappings = models.JSONField(default=list)
    layout_definition = models.JSONField(default=dict)
    status = models.CharField(max_length=20, choices=STATUSES, default="DRAFT")
    created_by = models.ForeignKey("users.User", null=True, on_delete=models.PROTECT, related_name="report_templates_created")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["report_type", "-version"]
        constraints = [
            models.UniqueConstraint(fields=["report_type", "version"], name="unique_report_template_version"),
            models.UniqueConstraint(fields=["report_type"], condition=models.Q(status="ACTIVE"), name="unique_active_report_template"),
        ]


class ReportPublicationMetadata(models.Model):
    report_type = models.CharField(max_length=30, choices=ReportTemplate.REPORT_TYPES)
    year = models.PositiveIntegerField()
    quarter = models.PositiveSmallIntegerField(null=True, blank=True)
    volume = models.PositiveIntegerField(null=True, blank=True)
    issue = models.PositiveIntegerField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    updated_by = models.ForeignKey("users.User", null=True, on_delete=models.PROTECT)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["report_type", "year", "quarter"], name="unique_report_publication_period")]


class ReportPreparation(models.Model):
    STATUSES = [(value, value.replace("_", " ").title()) for value in ("READY", "MISSING_DATA", "MAPPING_REQUIRED", "CALCULATION_ERROR", "STALE")]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    template = models.ForeignKey(ReportTemplate, on_delete=models.PROTECT, related_name="preparations")
    report_type = models.CharField(max_length=30, choices=ReportTemplate.REPORT_TYPES)
    year = models.PositiveIntegerField()
    quarter = models.PositiveSmallIntegerField(null=True, blank=True)
    status = models.CharField(max_length=30, choices=STATUSES)
    manifest = models.JSONField(default=dict)
    source_fingerprint = models.CharField(max_length=64)
    created_by = models.ForeignKey("users.User", on_delete=models.PROTECT, related_name="report_preparations")
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        ordering = ["-created_at"]


class GeneratedReport(models.Model):
    STATUSES = [("PREPARING", "Preparing"), ("READY", "Ready"), ("FAILED", "Failed")]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    preparation = models.ForeignKey(ReportPreparation, on_delete=models.PROTECT, related_name="generated_reports")
    status = models.CharField(max_length=20, choices=STATUSES, default="PREPARING")
    filename = models.CharField(max_length=255, blank=True)
    private_path = models.CharField(max_length=500, blank=True)
    mime_type = models.CharField(max_length=100, default="application/pdf")
    file_size = models.PositiveBigIntegerField(default=0)
    sha256 = models.CharField(max_length=64, blank=True)
    source_fingerprint = models.CharField(max_length=64)
    validation_result = models.JSONField(default=dict)
    error_message = models.TextField(blank=True)
    idempotency_key = models.UUIDField(unique=True)
    generated_by = models.ForeignKey("users.User", on_delete=models.PROTECT, related_name="generated_reports")
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

