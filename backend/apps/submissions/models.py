import uuid
from django.db import models
from django.utils import timezone


WORKFLOW_STATUSES = [
    ("NOT_STARTED", "Not Started"),
    ("DRAFT", "Draft"),
    ("PENDING_APPROVAL", "Pending Provider Approval"),
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
        for provider in self.assigned_providers.all():
            for form in self.applicable_form_templates.filter(provider_category=provider.category):
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

    def compute_due_state(self):
        now = timezone.now()
        terminal = ("APPROVED", "ARCHIVED")
        if self.workflow_status in terminal or self.period.status == "CLOSED":
            return "CLOSED"
        if self.period.opens_at > now:
            return "NOT_OPEN"
        effective_due = self.due_at_override or self.period.due_at
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
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.expected} v{self.version}"

    class Meta:
        ordering = ["-version"]
        unique_together = [["expected", "version"]]


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
