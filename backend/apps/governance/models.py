from django.db import models


RECORD_CLASSES = [
    ("FORM_VERSION", "Form versions"), ("SUBMISSION", "Submissions"),
    ("AUDIT", "Audit records"), ("PRIVATE_UPLOAD", "Private uploads"),
    ("RECEIPT", "Submission receipts"), ("EXPORT", "Exports"),
    ("EMAIL", "Email records"), ("DATA_REQUEST", "Data requests"),
    ("SUPPORT", "Support tickets"),
]


class RecordRetentionPolicy(models.Model):
    record_class = models.CharField(max_length=30, choices=RECORD_CLASSES)
    version = models.PositiveIntegerField(default=1)
    retention_days = models.PositiveIntegerField(null=True, blank=True)
    trigger_field = models.CharField(max_length=100, default="created_at")
    rationale = models.TextField(blank=True)
    authority_reference = models.CharField(max_length=500, blank=True)
    status = models.CharField(max_length=20, choices=[("DRAFT", "Draft"), ("APPROVED", "Approved"), ("ARCHIVED", "Archived")], default="DRAFT")
    prepared_by = models.ForeignKey("users.User", on_delete=models.PROTECT, related_name="retention_policies_prepared")
    approved_by = models.ForeignKey("users.User", null=True, blank=True, on_delete=models.PROTECT, related_name="retention_policies_approved")
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["record_class", "version"], name="unique_retention_policy_version")]


class LegalHold(models.Model):
    name = models.CharField(max_length=255)
    record_class = models.CharField(max_length=30, choices=RECORD_CLASSES, blank=True)
    provider_id = models.PositiveBigIntegerField(null=True, blank=True)
    reporting_period_id = models.PositiveBigIntegerField(null=True, blank=True)
    submission_id = models.PositiveBigIntegerField(null=True, blank=True)
    target_ids = models.JSONField(default=list)
    target_date_from = models.DateTimeField(null=True, blank=True)
    target_date_to = models.DateTimeField(null=True, blank=True)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField(null=True, blank=True)
    reason = models.TextField()
    authority_reference = models.CharField(max_length=500)
    status = models.CharField(max_length=20, choices=[("ACTIVE", "Active"), ("RELEASED", "Released")], default="ACTIVE")
    created_by = models.ForeignKey("users.User", on_delete=models.PROTECT, related_name="legal_holds_created")
    released_by = models.ForeignKey("users.User", null=True, blank=True, on_delete=models.PROTECT, related_name="legal_holds_released")
    created_at = models.DateTimeField(auto_now_add=True)
    released_at = models.DateTimeField(null=True, blank=True)


class DispositionRun(models.Model):
    policy = models.ForeignKey(RecordRetentionPolicy, on_delete=models.PROTECT, related_name="disposition_runs")
    dry_run = models.BooleanField(default=True)
    status = models.CharField(max_length=20, choices=[("PENDING", "Pending"), ("PREVIEWED", "Previewed"), ("APPROVED", "Approved"), ("COMPLETED", "Completed"), ("FAILED", "Failed")], default="PENDING")
    candidate_count = models.PositiveIntegerField(default=0)
    held_count = models.PositiveIntegerField(default=0)
    disposed_count = models.PositiveIntegerField(default=0)
    certificate_sha256 = models.CharField(max_length=64, blank=True)
    details = models.JSONField(default=dict)
    requested_by = models.ForeignKey("users.User", on_delete=models.PROTECT, related_name="disposition_runs_requested")
    approved_by = models.ForeignKey("users.User", null=True, blank=True, on_delete=models.PROTECT, related_name="disposition_runs_approved")
    requested_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)


class BackupRun(models.Model):
    backup_type = models.CharField(max_length=20, choices=[("FULL", "Full"), ("DIFFERENTIAL", "Differential"), ("WAL", "WAL archive"), ("FILES", "Private files")])
    status = models.CharField(max_length=20, choices=[("RUNNING", "Running"), ("SUCCEEDED", "Succeeded"), ("FAILED", "Failed"), ("VERIFIED", "Verified")])
    started_at = models.DateTimeField()
    completed_at = models.DateTimeField(null=True, blank=True)
    storage_reference = models.CharField(max_length=500)
    manifest_sha256 = models.CharField(max_length=64, blank=True)
    encrypted = models.BooleanField(default=False)
    immutable_copy = models.BooleanField(default=False)
    size_bytes = models.PositiveBigIntegerField(default=0)
    details = models.JSONField(default=dict)


class RestoreDrill(models.Model):
    backup = models.ForeignKey(BackupRun, on_delete=models.PROTECT, related_name="restore_drills")
    drill_type = models.CharField(max_length=20, choices=[("AUTOMATED", "Automated verification"), ("FULL", "Full recovery exercise")])
    status = models.CharField(max_length=20, choices=[("RUNNING", "Running"), ("PASSED", "Passed"), ("FAILED", "Failed")])
    started_at = models.DateTimeField()
    completed_at = models.DateTimeField(null=True, blank=True)
    measured_rpo_minutes = models.PositiveIntegerField(null=True, blank=True)
    measured_rto_minutes = models.PositiveIntegerField(null=True, blank=True)
    checks = models.JSONField(default=dict)
    evidence_reference = models.CharField(max_length=500, blank=True)
    signed_off_by = models.ForeignKey("users.User", null=True, blank=True, on_delete=models.PROTECT)
    signed_off_at = models.DateTimeField(null=True, blank=True)


class OperationalTaskRun(models.Model):
    task_name = models.CharField(max_length=150)
    idempotency_key = models.CharField(max_length=200, unique=True)
    status = models.CharField(max_length=20, choices=[("RUNNING", "Running"), ("SUCCEEDED", "Succeeded"), ("FAILED", "Failed"), ("SKIPPED", "Skipped")])
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    processed_count = models.PositiveIntegerField(default=0)
    details = models.JSONField(default=dict)
