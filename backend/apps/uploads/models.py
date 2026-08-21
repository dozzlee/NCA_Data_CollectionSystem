from django.db import models


class SubmissionKMZUpload(models.Model):
    """
    KMZ uploads are only permitted for DC-DBS05 (Domestic Fibre) under PRD Section 11.
    This is enforced at the API level via KMZUploadRequirement.
    """
    REVIEW_STATUS_CHOICES = [
        ("PENDING", "Pending NCA Review"),
        ("ACCEPTED", "Accepted"),
        ("REJECTED", "Rejected"),
    ]

    submission = models.ForeignKey("submissions.Submission", on_delete=models.CASCADE, related_name="kmz_uploads")
    requirement = models.ForeignKey(
        "forms_engine.KMZUploadRequirement", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="uploads"
    )
    requirement_snapshot = models.JSONField(default=dict, blank=True)
    file_name = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField(help_text="File size in bytes")
    storage_path = models.CharField(max_length=500)
    uploaded_by = models.ForeignKey("users.User", on_delete=models.PROTECT, related_name="kmz_uploads")
    uploaded_at = models.DateTimeField(auto_now_add=True)
    review_status = models.CharField(max_length=15, choices=REVIEW_STATUS_CHOICES, default="PENDING")
    review_note = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(
        "users.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="kmz_reviews"
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    sha256 = models.CharField(max_length=64, blank=True)
    scan_status = models.CharField(max_length=20, choices=[("PENDING", "Pending"), ("CLEAN", "Clean"), ("INFECTED", "Infected"), ("ERROR", "Scan error")], default="PENDING")
    scan_engine = models.CharField(max_length=100, blank=True)
    scan_details = models.TextField(blank=True)
    scanned_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"KMZ: {self.file_name} ({self.submission})"

    class Meta:
        ordering = ["-uploaded_at"]


class SubmissionExcelBackup(models.Model):
    """
    Excel backup files are stored for source control ONLY.
    They are NEVER parsed, imported, analyzed, or used for validation.
    """
    SOURCE_CONTROL_STATUS_CHOICES = [
        ("STORED", "Stored"),
        ("SUPERSEDED", "Superseded by newer upload"),
    ]

    submission = models.ForeignKey("submissions.Submission", on_delete=models.CASCADE, related_name="excel_backups")
    section = models.ForeignKey(
        "forms_engine.FormSection", null=True, blank=True, on_delete=models.SET_NULL
    )
    file_name = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField(help_text="File size in bytes")
    storage_path = models.CharField(max_length=500)
    uploaded_by = models.ForeignKey("users.User", on_delete=models.PROTECT, related_name="excel_backups")
    uploaded_at = models.DateTimeField(auto_now_add=True)
    source_control_status = models.CharField(
        max_length=15, choices=SOURCE_CONTROL_STATUS_CHOICES, default="STORED"
    )
    sha256 = models.CharField(max_length=64, blank=True)
    scan_status = models.CharField(max_length=20, choices=[("PENDING", "Pending"), ("CLEAN", "Clean"), ("INFECTED", "Infected"), ("ERROR", "Scan error")], default="PENDING")
    scan_engine = models.CharField(max_length=100, blank=True)
    scan_details = models.TextField(blank=True)
    scanned_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Excel backup: {self.file_name} ({self.submission})"

    class Meta:
        ordering = ["-uploaded_at"]


class SubmissionFieldAttachment(models.Model):
    """Private document supplied for an attachment-type form indicator."""
    submission = models.ForeignKey("submissions.Submission", on_delete=models.CASCADE, related_name="field_attachments")
    field = models.ForeignKey("forms_engine.FormField", on_delete=models.PROTECT, related_name="submission_attachments")
    file_name = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField()
    mime_type = models.CharField(max_length=150)
    storage_path = models.CharField(max_length=500)
    sha256 = models.CharField(max_length=64)
    uploaded_by = models.ForeignKey("users.User", on_delete=models.PROTECT, related_name="field_attachments")
    uploaded_at = models.DateTimeField(auto_now_add=True)
    is_current = models.BooleanField(default=True)
    scan_status = models.CharField(max_length=20, choices=[("PENDING", "Pending"), ("CLEAN", "Clean"), ("INFECTED", "Infected"), ("ERROR", "Scan error")], default="PENDING")
    scan_engine = models.CharField(max_length=100, blank=True)
    scan_details = models.TextField(blank=True)
    scanned_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-uploaded_at"]
        constraints = [
            models.UniqueConstraint(fields=["submission", "field"], condition=models.Q(is_current=True), name="one_current_attachment_per_field"),
        ]
