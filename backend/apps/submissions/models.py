import uuid
from django.db import models
from django.utils import timezone


WORKFLOW_STATUSES = [
    ("NOT_STARTED", "Not Started"),
    ("DRAFT", "Draft"),
    ("PENDING_APPROVAL", "Pending Provider Approval"),
    ("PROVIDER_CHANGES_REQUESTED", "Provider Changes Requested"),
    ("PROVIDER_RESUBMITTED", "Resubmitted to Provider Approver"),
    ("SUBMITTED", "Submitted"),
    ("UNDER_REVIEW", "Under NCA Review"),
    ("CORRECTION_REQUESTED", "Correction Requested"),
    ("RESUBMITTED", "Resubmitted"),
    ("APPROVED", "Approved"),
    ("REJECTED", "Rejected"),
    ("ARCHIVED", "Archived"),
]

DUE_STATES = [
    ("NOT_OPEN", "Not Open"),
    ("OPEN", "Open"),
    ("DUE_SOON", "Due Soon"),
    ("DUE_TODAY", "Due Today"),
    ("OVERDUE", "Overdue"),
    ("CLOSED", "Closed"),
]

FIELD_STATUSES = [
    ("MISSING", "Missing"),
    ("PROVIDED", "Provided"),
    ("OPTIONAL_NOT_PROVIDED", "Optional Not Provided"),
    ("NOT_APPLICABLE", "Not Applicable"),
    ("NOT_AVAILABLE", "Not Available"),
    ("NOT_REQUIRED", "Not Required for Provider"),
    ("PENDING_CLARIFICATION", "Pending Clarification"),
    ("WAITING_CORRECTION", "Waiting for Correction"),
    ("SYSTEM_CALCULATED", "System Calculated"),
]


class ReportingPeriod(models.Model):
    FREQUENCY_CHOICES = [
        ("MONTHLY", "Monthly"),
        ("SEMI_ANNUAL", "Semi-Annual"),
        ("ANNUAL", "Annual"),
    ]
    PERIOD_STATUS_CHOICES = [
        ("DRAFT", "Draft"),
        ("ACTIVE", "Active"),
        ("CLOSED", "Closed"),
    ]

    name = models.CharField(max_length=255)
    frequency = models.CharField(max_length=15, choices=FREQUENCY_CHOICES)
    year = models.PositiveIntegerField()
    month = models.PositiveIntegerField(null=True, blank=True)  # 1–12, monthly only
    opens_at = models.DateTimeField()
    due_at = models.DateTimeField()
    status = models.CharField(max_length=10, choices=PERIOD_STATUS_CHOICES, default="DRAFT")
    applicable_form_templates = models.ManyToManyField("forms_engine.FormTemplate", blank=True)
    assigned_providers = models.ManyToManyField("providers.ProviderProfile", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey("users.User", on_delete=models.PROTECT, related_name="periods_created")

    def __str__(self):
        return self.name

    def activate(self):
        """Generate ExpectedSubmission records for all assigned provider-form pairs."""
        invalid = []
        for form in self.applicable_form_templates.filter(frequency=self.frequency).select_related("family"):
            if form.status != "ACTIVE": invalid.append(f"{form.form_code} v{form.version}: only the active verified version can be assigned to a new period")
            elif not form.mapping_complete or form.approval_status != "APPROVED": invalid.append(f"{form.form_code}: mapping is not approved")
            elif not form.family_id: invalid.append(f"{form.form_code}: form family is missing")
            elif form.family.frequency_decision_status != "APPROVED": invalid.append(f"{form.form_code}: canonical frequency decision is pending")
            elif form.family.canonical_frequency != self.frequency: invalid.append(f"{form.form_code}: canonical frequency does not match the period")
        if invalid:
            raise ValueError("Period activation blocked. " + "; ".join(invalid))
        from apps.providers.models import ProviderFormAssignment
        for provider in self.assigned_providers.all():
            assignments = ProviderFormAssignment.objects.filter(
                provider=provider,
                form_family__canonical_frequency=self.frequency,
                effective_from__lte=self.due_at.date(),
            ).filter(models.Q(effective_to__isnull=True) | models.Q(effective_to__gte=self.opens_at.date()))
            if not assignments.exists():
                raise ValueError(f"No confirmed official form assignment exists for {provider.registered_name}.")
            required_family_ids = set(assignments.filter(obligation__in=["REQUIRED", "OPTIONAL"]).values_list("form_family_id", flat=True))
            forms = self.applicable_form_templates.filter(family_id__in=required_family_ids, frequency=self.frequency)
            present_family_ids = set(forms.values_list("family_id", flat=True))
            missing = required_family_ids - present_family_ids
            if missing:
                codes = ", ".join(ProviderFormAssignment.objects.filter(provider=provider, form_family_id__in=missing).values_list("form_family__code", flat=True))
                raise ValueError(f"The period is missing officially assigned form templates for {provider.registered_name}: {codes}.")
            for form in forms:
                ExpectedSubmission.objects.get_or_create(
                    provider=provider,
                    form_template=form,
                    period=self,
                    defaults={"workflow_status": "NOT_STARTED"},
                )
        self.status = "ACTIVE"
        self.save()

    class Meta:
        ordering = ["-year", "-month"]


class ReminderPolicy(models.Model):
    period = models.ForeignKey(ReportingPeriod, on_delete=models.CASCADE, related_name="reminder_policies")
    version = models.PositiveIntegerField(default=1)
    name = models.CharField(max_length=255)
    rules = models.JSONField(default=list, help_text="Approved offsets/channels/recipient roles")
    status = models.CharField(max_length=20, choices=[("DRAFT", "Draft"), ("APPROVED", "Approved"), ("ARCHIVED", "Archived")], default="DRAFT")
    prepared_by = models.ForeignKey("users.User", null=True, on_delete=models.SET_NULL, related_name="reminder_policies_prepared")
    approved_by = models.ForeignKey("users.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="reminder_policies_approved")
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["period", "version"], name="unique_period_reminder_version")]


class ExpectedSubmission(models.Model):
    provider = models.ForeignKey("providers.ProviderProfile", on_delete=models.PROTECT, related_name="expected_submissions")
    form_template = models.ForeignKey("forms_engine.FormTemplate", on_delete=models.PROTECT)
    period = models.ForeignKey(ReportingPeriod, on_delete=models.PROTECT, related_name="expected_submissions")
    workflow_status = models.CharField(max_length=30, choices=WORKFLOW_STATUSES, default="NOT_STARTED")
    due_state = models.CharField(max_length=15, choices=DUE_STATES, default="NOT_OPEN")
    assigned_officer = models.ForeignKey(
        "users.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="assigned_submissions"
    )
    due_at_override = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    replacement = models.OneToOneField(
        "self", null=True, blank=True, on_delete=models.PROTECT,
        related_name="replaces_legacy_obligation",
    )
    migration_report = models.JSONField(default=dict, blank=True)

    def compute_due_state(self):
        now = timezone.now()
        terminal = ("APPROVED", "ARCHIVED")
        if self.workflow_status in terminal or self.period.status == "CLOSED":
            return "CLOSED"
        if self.period.opens_at > now:
            return "NOT_OPEN"
        effective_due = self.effective_due_at
        submitted = self.workflow_status in ("SUBMITTED", "UNDER_REVIEW", "RESUBMITTED", "APPROVED")
        if submitted:
            return "CLOSED"
        delta = (effective_due - now).days
        if now > effective_due:
            return "OVERDUE"
        if delta == 0:
            return "DUE_TODAY"
        if delta <= 7:
            return "DUE_SOON"
        return "OPEN"

    def refresh_due_state(self):
        new_state = self.compute_due_state()
        if self.due_state != new_state:
            self.due_state = new_state
            self.save(update_fields=["due_state"])

    def __str__(self):
        return f"{self.provider} / {self.form_template.form_code} / {self.period.name}"

    class Meta:
        unique_together = [["provider", "form_template", "period"]]
        ordering = ["-period__year", "-period__month"]

    @property
    def effective_due_at(self):
        approved = self.deadline_changes.filter(status="APPROVED").order_by("-decided_at", "-id").first()
        return approved.proposed_due_at if approved else (self.due_at_override or self.period.due_at)


class DeadlineChangeRequest(models.Model):
    expected_submission = models.ForeignKey(ExpectedSubmission, on_delete=models.CASCADE, related_name="deadline_changes")
    previous_due_at = models.DateTimeField()
    proposed_due_at = models.DateTimeField()
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=[("PENDING", "Pending"), ("APPROVED", "Approved"), ("REJECTED", "Rejected")], default="PENDING")
    requested_by = models.ForeignKey("users.User", on_delete=models.PROTECT, related_name="deadline_changes_requested")
    requested_at = models.DateTimeField(auto_now_add=True)
    decided_by = models.ForeignKey("users.User", null=True, blank=True, on_delete=models.PROTECT, related_name="deadline_changes_decided")
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.TextField(blank=True)


class SubmissionOverride(models.Model):
    expected_submission = models.ForeignKey(ExpectedSubmission, on_delete=models.CASCADE, related_name="readiness_overrides")
    blocker_ids = models.JSONField(default=list)
    reason = models.TextField()
    evidence_reference = models.CharField(max_length=500, blank=True)
    expires_at = models.DateTimeField()
    status = models.CharField(max_length=20, choices=[("PENDING", "Pending"), ("APPROVED", "Approved"), ("REJECTED", "Rejected"), ("EXPIRED", "Expired")], default="PENDING")
    requested_by = models.ForeignKey("users.User", on_delete=models.PROTECT, related_name="submission_overrides_requested")
    requested_at = models.DateTimeField(auto_now_add=True)
    approved_by = models.ForeignKey("users.User", null=True, blank=True, on_delete=models.PROTECT, related_name="submission_overrides_approved")
    approved_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.TextField(blank=True)


class Submission(models.Model):
    expected = models.ForeignKey(ExpectedSubmission, on_delete=models.PROTECT, related_name="versions")
    version = models.PositiveIntegerField(default=1)
    completion_pct = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    submitted_by = models.ForeignKey(
        "users.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="submitted_submissions"
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        "users.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="reviewed_submissions"
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    revision = models.PositiveIntegerField(default=0)
    supersedes = models.OneToOneField(
        "self", null=True, blank=True, on_delete=models.PROTECT,
        related_name="superseded_by",
        help_text="Previous immutable official version cloned for correction.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.expected} v{self.version}"

    class Meta:
        ordering = ["-version"]
        unique_together = [["expected", "version"]]


class ValidationRun(models.Model):
    submission = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name="validation_runs")
    scope = models.CharField(max_length=100, default="FULL")
    status = models.CharField(max_length=10, choices=[("PASS", "Pass"), ("WARN", "Warnings"), ("FAIL", "Failed")])
    ruleset_snapshot = models.JSONField(default=list)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)


class ValidationResult(models.Model):
    run = models.ForeignKey(ValidationRun, on_delete=models.CASCADE, related_name="results")
    rule = models.ForeignKey("forms_engine.ValidationRule", null=True, on_delete=models.SET_NULL)
    severity = models.CharField(max_length=10)
    target_type = models.CharField(max_length=20)
    target_id = models.CharField(max_length=100)
    code = models.CharField(max_length=50)
    message = models.TextField()
    details = models.JSONField(default=dict)


class SubmissionValue(models.Model):
    submission = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name="values")
    field = models.ForeignKey("forms_engine.FormField", null=True, blank=True, on_delete=models.SET_NULL)
    grid = models.ForeignKey("forms_engine.FormGrid", null=True, blank=True, on_delete=models.SET_NULL)
    grid_row_id = models.CharField(max_length=100, blank=True)   # Fixed label or repeatable UUID
    grid_column = models.ForeignKey("forms_engine.GridColumn", null=True, blank=True, on_delete=models.SET_NULL)
    value = models.TextField(blank=True)
    value_status = models.CharField(max_length=30, choices=FIELD_STATUSES, default="MISSING")
    explanation = models.TextField(blank=True)
    updated_by = models.ForeignKey("users.User", null=True, on_delete=models.SET_NULL)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["submission", "field"]),
            models.Index(fields=["submission", "grid", "grid_row_id", "grid_column"]),
        ]
        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(field__isnull=False, grid__isnull=True, grid_column__isnull=True)
                    | models.Q(field__isnull=True, grid__isnull=False, grid_column__isnull=False)
                ),
                name="submission_value_exactly_one_target",
            ),
            models.UniqueConstraint(
                fields=["submission", "field"], condition=models.Q(field__isnull=False),
                name="unique_submission_scalar_value",
            ),
            models.UniqueConstraint(
                fields=["submission", "grid", "grid_row_id", "grid_column"],
                condition=models.Q(grid__isnull=False), name="unique_submission_grid_cell",
            ),
        ]


class ReviewAction(models.Model):
    ACTION_CHOICES = [
        ("APPROVE", "Approve"),
        ("REJECT", "Reject"),
        ("REQUEST_CORRECTION", "Request Correction"),
        ("ADD_NOTE", "Add Internal Note"),
        ("ADD_PROVIDER_COMMENT", "Add Provider-Visible Comment"),
    ]
    TARGET_CHOICES = [
        ("SUBMISSION", "Submission"),
        ("SECTION", "Section"),
        ("FIELD", "Field"),
        ("GRID_CELL", "Grid Cell"),
    ]

    submission = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name="review_actions")
    action = models.CharField(max_length=30, choices=ACTION_CHOICES)
    target_type = models.CharField(max_length=15, choices=TARGET_CHOICES, blank=True)
    target_id = models.CharField(max_length=100, blank=True)
    comment = models.TextField(blank=True)
    is_provider_visible = models.BooleanField(default=False)
    created_by = models.ForeignKey("users.User", on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class CorrectionItem(models.Model):
    source_submission = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name="correction_items")
    stage = models.CharField(
        max_length=25,
        choices=[("PROVIDER_APPROVAL", "Provider Approval"), ("NCA_REVIEW", "NCA Review")],
        default="NCA_REVIEW",
    )
    resolution_submission = models.ForeignKey(
        Submission, null=True, blank=True, on_delete=models.PROTECT,
        related_name="resolved_correction_items",
    )
    target_type = models.CharField(max_length=20, choices=ReviewAction.TARGET_CHOICES)
    target_id = models.CharField(max_length=100)
    instruction = models.TextField()
    status = models.CharField(max_length=20, choices=[("OPEN", "Open"), ("ADDRESSED", "Addressed"), ("VERIFIED", "Verified")], default="OPEN")
    created_by = models.ForeignKey("users.User", on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class SubmissionEvent(models.Model):
    AUDIENCE_CHOICES = [
        ("PROVIDER", "Provider"), ("NCA", "NCA"), ("BOTH", "Both"), ("INTERNAL", "Internal"),
    ]

    submission = models.ForeignKey(Submission, on_delete=models.PROTECT, related_name="timeline_events")
    event_type = models.CharField(max_length=60)
    from_status = models.CharField(max_length=30, blank=True)
    to_status = models.CharField(max_length=30, blank=True)
    message = models.TextField()
    audience = models.CharField(max_length=10, choices=AUDIENCE_CHOICES, default="BOTH")
    metadata = models.JSONField(default=dict)
    actor = models.ForeignKey("users.User", null=True, on_delete=models.PROTECT, related_name="submission_events")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]


class SubmissionNotification(models.Model):
    recipient = models.ForeignKey("users.User", on_delete=models.CASCADE, related_name="submission_notifications")
    submission = models.ForeignKey(Submission, on_delete=models.PROTECT, related_name="notifications")
    event = models.ForeignKey(SubmissionEvent, on_delete=models.PROTECT, related_name="notifications")
    title = models.CharField(max_length=255)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["recipient", "event"], name="unique_submission_event_recipient")
        ]


class NonFilledDisposition(models.Model):
    value = models.OneToOneField(SubmissionValue, on_delete=models.CASCADE, related_name="non_filled_disposition")
    decision = models.CharField(max_length=10, choices=[("ACCEPTED", "Accepted"), ("REJECTED", "Rejected")])
    note = models.TextField(blank=True)
    reviewed_by = models.ForeignKey("users.User", on_delete=models.PROTECT)
    reviewed_at = models.DateTimeField(auto_now_add=True)


class SubmissionReceipt(models.Model):
    submission = models.OneToOneField(Submission, on_delete=models.PROTECT, related_name="receipt")
    reference = models.CharField(max_length=50, unique=True)
    snapshot = models.JSONField(default=dict)
    private_path = models.CharField(max_length=500)
    mime_type = models.CharField(max_length=100, default="application/pdf")
    file_size = models.PositiveBigIntegerField(default=0)
    sha256 = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)
