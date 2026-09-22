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
    Private original Excel evidence. A linked SubmissionExcelImport may parse a
    clean copy for an explicitly previewed and confirmed value import.
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


class ExcelImportMappingProfile(models.Model):
    """Reusable mappings for one provider/form and one exact workbook layout."""

    provider = models.ForeignKey("providers.ProviderProfile", on_delete=models.CASCADE, related_name="excel_import_profiles")
    form_template = models.ForeignKey("forms_engine.FormTemplate", on_delete=models.CASCADE, related_name="excel_import_profiles")
    layout_fingerprint = models.CharField(max_length=64)
    version = models.PositiveIntegerField(default=1)
    mappings = models.JSONField(default=dict)
    created_by = models.ForeignKey("users.User", on_delete=models.PROTECT, related_name="excel_import_profiles_created")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-version", "-id"]
        constraints = [models.UniqueConstraint(
            fields=["provider", "form_template", "layout_fingerprint", "version"],
            name="unique_excel_import_mapping_profile_version",
        )]


class SubmissionExcelImport(models.Model):
    STATUS_CHOICES = [
        ("SCANNING", "Scanning"), ("PARSING", "Parsing"), ("READY", "Ready for review"),
        ("IMPORTING", "Importing"), ("IMPORTED", "Imported"), ("FAILED", "Failed"),
    ]

    submission = models.ForeignKey("submissions.Submission", on_delete=models.CASCADE, related_name="excel_imports")
    backup = models.OneToOneField(SubmissionExcelBackup, on_delete=models.PROTECT, related_name="excel_import")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="SCANNING")
    parser_version = models.CharField(max_length=80, default="submission-xlsx-v1")
    matcher_version = models.CharField(max_length=80, default="deterministic-v1")
    layout_fingerprint = models.CharField(max_length=64, blank=True)
    source_revision = models.PositiveIntegerField(default=0)
    summary = models.JSONField(default=dict)
    errors = models.JSONField(default=list)
    imported_manifest = models.JSONField(default=dict)
    mapping_profile = models.ForeignKey(
        ExcelImportMappingProfile, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="imports",
    )
    uploaded_by = models.ForeignKey("users.User", on_delete=models.PROTECT, related_name="excel_imports_uploaded")
    confirmed_by = models.ForeignKey(
        "users.User", null=True, blank=True, on_delete=models.PROTECT,
        related_name="excel_imports_confirmed",
    )
    confirmed_at = models.DateTimeField(null=True, blank=True)
    confirmation_key = models.UUIDField(null=True, blank=True, unique=True)
    resulting_revision = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]


class SubmissionExcelImportMatch(models.Model):
    STATUS_CHOICES = [
        ("MATCHED", "Matched"), ("UNMATCHED", "Unmatched"),
        ("AMBIGUOUS", "Ambiguous"), ("DUPLICATE", "Duplicate"),
        ("INVALID", "Invalid"), ("SKIPPED", "Skipped"),
    ]

    excel_import = models.ForeignKey(SubmissionExcelImport, on_delete=models.CASCADE, related_name="matches")
    source_locator = models.CharField(max_length=500)
    source_sheet = models.CharField(max_length=255)
    source_row = models.PositiveIntegerField()
    source_column = models.CharField(max_length=20, blank=True)
    indicator_code = models.CharField(max_length=255, blank=True)
    indicator_name = models.CharField(max_length=500)
    definition = models.TextField(blank=True)
    source_data_type = models.CharField(max_length=100, blank=True)
    raw_value = models.JSONField(null=True, blank=True)
    converted_value = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    score = models.DecimalField(max_digits=5, decimal_places=4, default=0)
    evidence = models.JSONField(default=dict)
    target_type = models.CharField(max_length=20, blank=True)
    target_key = models.CharField(max_length=500, blank=True)
    field = models.ForeignKey("forms_engine.FormField", null=True, blank=True, on_delete=models.SET_NULL)
    grid = models.ForeignKey("forms_engine.FormGrid", null=True, blank=True, on_delete=models.SET_NULL)
    grid_row_id = models.CharField(max_length=100, blank=True)
    grid_column = models.ForeignKey("forms_engine.GridColumn", null=True, blank=True, on_delete=models.SET_NULL)
    current_value = models.TextField(blank=True)
    will_overwrite = models.BooleanField(default=False)
    user_confirmed = models.BooleanField(default=False)
    decision_note = models.TextField(blank=True)

    class Meta:
        ordering = ["source_sheet", "source_row", "source_column", "id"]
        constraints = [models.UniqueConstraint(fields=["excel_import", "source_locator"], name="unique_excel_import_source_locator")]


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
