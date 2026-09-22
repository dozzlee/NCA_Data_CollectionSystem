import uuid
import re
from datetime import date
from django.db import models
from django.core.exceptions import ValidationError
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

PROVIDER_WORKFLOW_STATUSES = [
    ("IN_PROGRESS", "In Progress"),
    ("AWAITING_APPROVAL", "Awaiting Approval"),
    ("CORRECTIONS_REQUIRED", "Corrections Required"),
    ("CLOSED", "Closed"),
]

REGULATORY_STATUSES = [
    ("DRAFT", "Draft"),
    ("SUBMITTED", "Submitted"),
    ("UNDER_REVIEW", "Under Review"),
    ("RETURNED_FOR_CORRECTION", "Returned for Correction"),
    ("APPROVED", "Approved"),
    ("REJECTED", "Rejected"),
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
        ("QUARTERLY", "Quarterly"),
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
    quarter = models.PositiveIntegerField(null=True, blank=True)
    opens_at = models.DateTimeField()
    due_at = models.DateTimeField()
    status = models.CharField(max_length=10, choices=PERIOD_STATUS_CHOICES, default="DRAFT")
    applicable_form_templates = models.ManyToManyField("forms_engine.FormTemplate", blank=True)
    assigned_providers = models.ManyToManyField("providers.ProviderProfile", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey("users.User", on_delete=models.PROTECT, related_name="periods_created")

    def __str__(self):
        return self.name

    def clean(self):
        if self.due_at and self.opens_at and self.due_at <= self.opens_at:
            raise ValidationError({"due_at": "The due date must be after the opening date."})
        if self.frequency == "MONTHLY" and not self.month:
            raise ValidationError({"month": "Month is required for a monthly period."})
        if self.month and (self.frequency != "MONTHLY" or not 1 <= self.month <= 12):
            raise ValidationError({"month": "Month must be 1-12 and is only valid for monthly periods."})
        if self.frequency == "MONTHLY" and self.month and self.due_at:
            next_year = self.year + 1 if self.month == 12 else self.year
            next_month = 1 if self.month == 12 else self.month + 1
            if self.due_at.date() != date(next_year, next_month, 10):
                raise ValidationError({
                    "due_at": "Monthly periods must be due on the 10th of the following month."
                })
        if self.frequency == "QUARTERLY" and not self.quarter:
            raise ValidationError({"quarter": "Quarter is required for a quarterly period."})
        if self.quarter and (self.frequency != "QUARTERLY" or not 1 <= self.quarter <= 4):
            raise ValidationError({"quarter": "Quarter must be 1-4 and is only valid for quarterly periods."})
        if self.frequency == "SEMI_ANNUAL":
            expected_date = (6, 30) if self.due_at.month == 6 else (12, 31)
            if (self.due_at.month, self.due_at.day) != expected_date:
                raise ValidationError({
                    "due_at": "Bi-annual periods must be due on 30 June or 31 December."
                })

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
        provider_ids = set(self.assigned_providers.values_list("id", flat=True))
        template_ids = set(self.applicable_form_templates.values_list("id", flat=True))
        recurring = ProviderFormAssignment.objects.filter(
            form_family__canonical_frequency=self.frequency,
            obligation__in=["REQUIRED", "OPTIONAL"], effective_from__lte=self.due_at.date(),
        ).filter(models.Q(effective_to__isnull=True) | models.Q(effective_to__gte=self.opens_at.date()))
        if provider_ids:
            recurring = recurring.filter(provider_id__in=provider_ids)
        for assignment in recurring.select_related("provider", "form_family"):
            form = assignment.form_family.versions.filter(
                status="ACTIVE", approval_status="APPROVED", frequency=self.frequency,
            ).order_by("-published_at", "-id").first()
            if not form:
                raise ValueError(f"No active approved {assignment.form_family.code} version is available.")
            if template_ids and form.id not in template_ids:
                continue
            ExpectedSubmission.create_from_assignment(
                provider=assignment.provider, form_template=form, period=self,
                recurring_assignment=assignment, actor=self.created_by,
            )
        for manual in self.manual_form_assignments.select_related("provider", "form_template", "assigned_by"):
            ExpectedSubmission.create_from_assignment(
                provider=manual.provider, form_template=manual.form_template, period=self,
                manual_assignment=manual, actor=manual.assigned_by,
            )
        self.status = "ACTIVE"
        self.save()

    class Meta:
        ordering = ["-year", "-month"]


class PeriodFormAssignment(models.Model):
    """One exact form version sent to one provider for one reporting period."""
    period = models.ForeignKey(ReportingPeriod, on_delete=models.PROTECT, related_name="manual_form_assignments")
    form_template = models.ForeignKey("forms_engine.FormTemplate", on_delete=models.PROTECT, related_name="period_assignments")
    provider = models.ForeignKey("providers.ProviderProfile", on_delete=models.PROTECT, related_name="period_form_assignments")
    mismatch_override_reason = models.TextField(blank=True)
    assigned_by = models.ForeignKey("users.User", on_delete=models.PROTECT, related_name="period_form_assignments")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["period", "form_template", "provider"], name="unique_manual_period_form_provider")]


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
    form_template = models.ForeignKey(
        "forms_engine.FormTemplate", null=True, blank=True, on_delete=models.SET_NULL,
        help_text="Null only for archived obligations whose immutable form identity/schema was snapshotted.",
    )
    form_code_snapshot = models.CharField(max_length=50, blank=True)
    form_name_snapshot = models.CharField(max_length=255, blank=True)
    form_version_snapshot = models.CharField(max_length=20, blank=True)
    form_frequency_snapshot = models.CharField(max_length=15, blank=True)
    form_sector_snapshot = models.CharField(max_length=20, blank=True)
    form_provider_category_snapshot = models.CharField(max_length=30, blank=True)
    form_source_reference_snapshot = models.CharField(max_length=500, blank=True)
    form_created_at_snapshot = models.DateTimeField(null=True, blank=True)
    workflow_status_snapshot = models.CharField(max_length=30, blank=True)
    period = models.ForeignKey(ReportingPeriod, on_delete=models.PROTECT, related_name="expected_submissions")
    workflow_status = models.CharField(max_length=30, choices=WORKFLOW_STATUSES, default="NOT_STARTED")
    provider_status = models.CharField(
        max_length=30, choices=PROVIDER_WORKFLOW_STATUSES, default="IN_PROGRESS", db_index=True,
    )
    form_reference = models.CharField(max_length=180, unique=True, editable=False)
    due_state = models.CharField(max_length=15, choices=DUE_STATES, default="NOT_OPEN")
    assigned_officer = models.ForeignKey(
        "users.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="assigned_submissions"
    )
    due_at_override = models.DateTimeField(null=True, blank=True)
    penalty_amount_ghs = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    penalty_reference = models.CharField(max_length=120, blank=True)
    penalty_note = models.TextField(blank=True)
    penalty_updated_by = models.ForeignKey(
        "users.User", null=True, blank=True, on_delete=models.PROTECT,
        related_name="penalties_updated",
    )
    penalty_updated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    replacement = models.OneToOneField(
        "self", null=True, blank=True, on_delete=models.PROTECT,
        related_name="replaces_legacy_obligation",
    )
    migration_report = models.JSONField(default=dict, blank=True)
    recurring_assignment = models.ForeignKey(
        "providers.ProviderFormAssignment", null=True, blank=True, on_delete=models.PROTECT,
        related_name="expected_submissions",
    )
    manual_assignment = models.ForeignKey(
        PeriodFormAssignment, null=True, blank=True, on_delete=models.PROTECT,
        related_name="expected_submissions",
    )

    @classmethod
    def create_from_assignment(
        cls, *, provider, form_template, period, recurring_assignment=None,
        manual_assignment=None, actor=None, message_subject="", message_body="",
    ):
        expected, created = cls.objects.get_or_create(
            provider=provider, form_template=form_template, period=period,
            defaults={
                "workflow_status": "NOT_STARTED",
                "provider_status": "IN_PROGRESS",
                "recurring_assignment": recurring_assignment,
                "manual_assignment": manual_assignment,
            },
        )
        if created:
            from .workflow import emit_submission_event
            submission = Submission.objects.create(expected=expected, version=1)
            expected.refresh_due_state()
            event = emit_submission_event(
                submission=submission, actor=actor, event_type="FORM_ASSIGNED",
                message=message_body or f"{form_template.name} was assigned for {period.name}.",
                to_status="NOT_STARTED", audience="PROVIDER",
                notify=["PROVIDER_DATA_ENTRY", "PROVIDER_APPROVER"],
                title=message_subject or "New form assigned",
                metadata={
                    "communication_subject": message_subject or "New form assigned",
                    "communication_body": message_body or f"{form_template.name} was assigned for {period.name}.",
                },
            )
            from apps.compliance.communications import create_system_record, queue_automatic_communication
            create_system_record(submission=submission, event=event)
            if actor:
                queue_automatic_communication(
                    submission=submission, event=event, action="FORM_ASSIGNED", actor=actor,
                )
        return expected, created

    def build_form_reference(self):
        period = self.period
        if period.frequency == "MONTHLY":
            period_token = f"{period.year}-{period.month:02d}"
        elif period.frequency == "QUARTERLY":
            period_token = f"{period.year}-Q{period.quarter}"
        elif period.frequency == "ANNUAL":
            period_token = str(period.year)
        else:
            period_token = f"{period.year}-SA-{period.id}"
        template = self.form_template
        form_code_value = template.form_code if template else self.form_code_snapshot
        form_code = re.sub(r"[^A-Z0-9-]+", "-", form_code_value.upper()).strip("-")
        return f"FORM-{form_code}-{self.provider.provider_code}-{period_token}-F{self.id}"

    def save(self, *args, **kwargs):
        creating = self._state.adding
        if creating and not self.form_reference:
            self.form_reference = f"PENDING-{uuid.uuid4().hex}"
            super().save(*args, **kwargs)
            self.form_reference = self.build_form_reference()
            type(self).objects.filter(pk=self.pk).update(form_reference=self.form_reference)
            return
        if self.pk:
            original = type(self).objects.filter(pk=self.pk).values_list("form_reference", flat=True).first()
            if original and self.form_reference != original:
                raise ValidationError({"form_reference": "Form references are immutable."})
        super().save(*args, **kwargs)

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
        code = self.form_template.form_code if self.form_template_id else self.form_code_snapshot
        return f"{self.provider} / {code or 'ARCHIVED-FORM'} / {self.period.name}"

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
    submission_reference = models.CharField(max_length=180, unique=True, editable=False)
    regulatory_status = models.CharField(
        max_length=30, choices=REGULATORY_STATUSES, default="DRAFT", db_index=True,
    )
    form_schema_snapshot = models.JSONField(default=dict, blank=True)
    form_schema_sha256 = models.CharField(max_length=64, blank=True, editable=False)
    form_schema_snapshot_version = models.PositiveSmallIntegerField(default=1)
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
    last_edited_by = models.ForeignKey(
        "users.User", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="last_edited_submissions",
    )
    last_edited_at = models.DateTimeField(null=True, blank=True)
    supersedes = models.OneToOneField(
        "self", null=True, blank=True, on_delete=models.PROTECT,
        related_name="superseded_by",
        help_text="Previous immutable official version cloned for correction.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.expected} v{self.version}"

    def build_submission_reference(self):
        period = self.expected.period
        if period.frequency == "MONTHLY":
            period_token = f"{period.year}-{period.month:02d}"
        elif period.frequency == "QUARTERLY":
            period_token = f"{period.year}-Q{period.quarter}"
        elif period.frequency == "ANNUAL":
            period_token = str(period.year)
        else:
            period_token = f"{period.year}-SA-{period.id}"
        template = self.expected.form_template
        form_code_value = template.form_code if template else self.expected.form_code_snapshot
        version_value = template.version if template else self.expected.form_version_snapshot
        form_code = re.sub(r"[^A-Z0-9-]+", "-", form_code_value.upper()).strip("-")
        version = re.sub(r"[^A-Z0-9.-]+", "-", version_value.upper()).strip("-")
        return f"{form_code}-{self.expected.provider.provider_code}-{period_token}-V{version}-S{self.id}"

    def save(self, *args, **kwargs):
        creating = self._state.adding
        if creating and not self.submission_reference:
            # The final component is the database ID, so persist once to obtain it,
            # then store the immutable human-facing reference in the same call path.
            self.submission_reference = f"PENDING-{uuid.uuid4().hex}"
            super().save(*args, **kwargs)
            self.submission_reference = self.build_submission_reference()
            type(self).objects.filter(pk=self.pk).update(submission_reference=self.submission_reference)
            return
        if self.pk:
            original = type(self).objects.filter(pk=self.pk).values_list("submission_reference", flat=True).first()
            if original and self.submission_reference != original:
                raise ValidationError({"submission_reference": "Submission references are immutable."})
        super().save(*args, **kwargs)

    class Meta:
        ordering = ["-version"]
        unique_together = [["expected", "version"]]


class ProviderEditBatch(models.Model):
    """Immutable record of one Provider Approver section save."""

    submission = models.ForeignKey(Submission, on_delete=models.PROTECT, related_name="provider_edit_batches")
    actor = models.ForeignKey("users.User", on_delete=models.PROTECT, related_name="provider_edit_batches")
    stage = models.CharField(max_length=30)
    section_code = models.CharField(max_length=100)
    base_revision = models.PositiveIntegerField()
    resulting_revision = models.PositiveIntegerField()
    item_count = models.PositiveIntegerField(default=0)
    changes_sha256 = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]


class ProviderEditItem(models.Model):
    """Sensitive before/after values, visible only within the provider tenant and NCA."""

    batch = models.ForeignKey(ProviderEditBatch, on_delete=models.PROTECT, related_name="items")
    target_type = models.CharField(max_length=20, choices=[("FIELD", "Field"), ("GRID_CELL", "Grid cell")])
    target_id = models.CharField(max_length=255)
    before = models.JSONField(default=dict)
    after = models.JSONField(default=dict)

    class Meta:
        ordering = ["id"]


class ProviderApprovalDecision(models.Model):
    """The immutable provider attestation attached to an official version."""

    submission = models.OneToOneField(Submission, on_delete=models.PROTECT, related_name="provider_approval")
    approver = models.ForeignKey("users.User", on_delete=models.PROTECT, related_name="provider_approval_decisions")
    attestation = models.BooleanField()
    approval_note = models.TextField(blank=True)
    change_summary = models.TextField(blank=True)
    approver_edited = models.BooleanField(default=False)
    edit_batch_count = models.PositiveIntegerField(default=0)
    decided_at = models.DateTimeField(auto_now_add=True)


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
    target_key_snapshot = models.CharField(max_length=255, blank=True, db_index=True)
    target_snapshot = models.JSONField(default=dict, blank=True)
    value = models.TextField(blank=True)
    value_status = models.CharField(max_length=30, choices=FIELD_STATUSES, default="MISSING")
    explanation = models.TextField(blank=True)
    value_source = models.CharField(
        max_length=20,
        choices=[("MANUAL", "Manual entry"), ("EXCEL_IMPORT", "Excel import"), ("SYSTEM", "System calculated")],
        default="MANUAL",
    )
    source_reference = models.CharField(max_length=100, blank=True)
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
                    | models.Q(
                        field__isnull=True, grid__isnull=True, grid_column__isnull=True,
                        target_key_snapshot__gt="",
                    )
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


class SectionSaveReceipt(models.Model):
    """Idempotency evidence for one authoritative provider section save."""

    submission = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name="section_save_receipts")
    client_save_id = models.UUIDField()
    section_code = models.CharField(max_length=50)
    actor = models.ForeignKey("users.User", on_delete=models.PROTECT, related_name="section_save_receipts")
    payload_sha256 = models.CharField(max_length=64)
    base_revision = models.PositiveIntegerField()
    resulting_revision = models.PositiveIntegerField()
    persisted_change_version = models.PositiveIntegerField(default=0)
    response = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["submission", "client_save_id"],
                name="unique_submission_client_section_save",
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


class ProviderWorkbookBaseline(models.Model):
    """Private provider-specific workbook used to render one monthly form family."""

    STATUS_CHOICES = [
        ("DRAFT", "Draft"), ("ACTIVE", "Active"), ("ARCHIVED", "Archived"),
    ]
    SCAN_CHOICES = [
        ("PENDING", "Pending"), ("CLEAN", "Clean"),
        ("INFECTED", "Infected"), ("ERROR", "Error"),
    ]

    provider = models.ForeignKey(
        "providers.ProviderProfile", on_delete=models.PROTECT, related_name="workbook_baselines",
    )
    form_template = models.ForeignKey(
        "forms_engine.FormTemplate", on_delete=models.PROTECT, related_name="provider_workbook_baselines",
    )
    contact = models.ForeignKey(
        "providers.ProviderContact", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="workbook_baselines",
    )
    version = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="DRAFT")
    file_name = models.CharField(max_length=255)
    storage_path = models.CharField(max_length=500)
    file_size = models.PositiveBigIntegerField(default=0)
    sha256 = models.CharField(max_length=64)
    scan_status = models.CharField(max_length=20, choices=SCAN_CHOICES, default="PENDING")
    scan_engine = models.CharField(max_length=100, blank=True)
    scan_details = models.TextField(blank=True)
    main_sheet = models.CharField(max_length=255, default="REVISED MNOs MONTHLY DATA")
    month_header_row = models.PositiveIntegerField(default=8)
    first_month_column = models.PositiveIntegerField(default=6)
    contact_cells = models.JSONField(default=dict, blank=True)
    mapping_summary = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(
        "users.User", on_delete=models.PROTECT, related_name="workbook_baselines_created",
    )
    approved_by = models.ForeignKey(
        "users.User", null=True, blank=True, on_delete=models.PROTECT,
        related_name="workbook_baselines_approved",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "form_template", "version"],
                name="unique_provider_form_workbook_baseline_version",
            ),
            models.UniqueConstraint(
                fields=["provider", "form_template"], condition=models.Q(status="ACTIVE"),
                name="unique_active_provider_form_workbook_baseline",
            ),
        ]


class WorkbookIndicatorMapping(models.Model):
    """Verified target-to-row mapping; generation never performs fuzzy matching."""

    baseline = models.ForeignKey(
        ProviderWorkbookBaseline, on_delete=models.CASCADE, related_name="indicator_mappings",
    )
    target_key = models.CharField(max_length=300)
    target_type = models.CharField(
        max_length=20, choices=[("FIELD", "Field"), ("GRID_CELL", "Grid cell")],
    )
    field = models.ForeignKey(
        "forms_engine.FormField", null=True, blank=True, on_delete=models.PROTECT,
        related_name="workbook_mappings",
    )
    grid = models.ForeignKey(
        "forms_engine.FormGrid", null=True, blank=True, on_delete=models.PROTECT,
        related_name="workbook_mappings",
    )
    grid_row = models.ForeignKey(
        "forms_engine.GridRow", null=True, blank=True, on_delete=models.PROTECT,
        related_name="workbook_mappings",
    )
    grid_column = models.ForeignKey(
        "forms_engine.GridColumn", null=True, blank=True, on_delete=models.PROTECT,
        related_name="workbook_mappings",
    )
    sheet_name = models.CharField(max_length=255)
    excel_row = models.PositiveIntegerField()
    value_kind = models.CharField(
        max_length=20, choices=[("INPUT", "Input"), ("CALCULATED", "Calculated")],
        default="INPUT",
    )
    source_indicator = models.CharField(max_length=500, blank=True)
    source_definition = models.TextField(blank=True)
    source_data_type = models.CharField(max_length=100, blank=True)
    formula_seed_column = models.PositiveIntegerField(null=True, blank=True)
    verified = models.BooleanField(default=False)
    provenance = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sheet_name", "excel_row", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["baseline", "target_key"], name="unique_baseline_indicator_target",
            ),
            models.UniqueConstraint(
                fields=["baseline", "sheet_name", "excel_row"],
                name="unique_baseline_sheet_indicator_row",
            ),
        ]


class MonthlyReportArtifact(models.Model):
    STATUS_CHOICES = [
        ("PREPARING", "Preparing"), ("READY", "Ready"),
        ("FAILED", "Failed"), ("SUPERSEDED", "Superseded"),
    ]

    submission = models.OneToOneField(
        Submission, on_delete=models.PROTECT, related_name="monthly_report_artifact",
    )
    baseline = models.ForeignKey(
        ProviderWorkbookBaseline, null=True, blank=True, on_delete=models.SET_NULL, related_name="artifacts",
    )
    baseline_snapshot = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PREPARING")
    filename = models.CharField(max_length=255, blank=True)
    private_path = models.CharField(max_length=500, blank=True)
    mime_type = models.CharField(
        max_length=100, default="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    file_size = models.PositiveBigIntegerField(default=0)
    sha256 = models.CharField(max_length=64, blank=True)
    submission_revision = models.PositiveIntegerField(default=0)
    generation_metadata = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
