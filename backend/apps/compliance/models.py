from django.db import models


class EmailTemplate(models.Model):
    TYPE_CHOICES = [
        ("PERIOD_OPEN", "Period Opening Notice"),
        ("FORM_ASSIGNED", "New Form Assigned"),
        ("REMINDER", "Submission Reminder"),
        ("DEADLINE_REMINDER", "Deadline Reminder"),
        ("DRAFT_INCOMPLETE", "Draft Incomplete Reminder"),
        ("MISSING_FIELDS", "Missing Required Fields"),
        ("SUBMITTED_FOR_APPROVAL", "Form Submitted for Approval"),
        ("CORRECTION_REQUEST", "Correction Request"),
        ("PROVIDER_RESUBMITTED", "Provider Resubmission"),
        ("SUBMITTED_TO_NCA", "Submission Sent to NCA"),
        ("NCA_ACKNOWLEDGEMENT", "NCA Receipt Acknowledgement"),
        ("NCA_CORRECTION_REQUEST", "NCA Correction Request"),
        ("SUBMISSION_REJECTED", "Submission Rejected"),
        ("SUBMISSION_APPROVED", "Submission Approved"),
        ("DEADLINE_CHANGED", "Deadline Changed"),
        ("COMPLIANCE_NOTICE", "Compliance Notice"),
        ("SUBMISSION_CORRESPONDENCE", "General Submission Correspondence"),
        ("OVERDUE", "Overdue Notice"),
        ("ESCALATION", "Escalation Notice"),
        ("PENALTY_WARNING", "Penalty Warning"),
        ("FINAL_NOTICE", "Final Compliance Notice"),
    ]

    template_type = models.CharField(max_length=30, choices=TYPE_CHOICES)
    version = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=20, choices=[("DRAFT", "Draft"), ("APPROVED", "Approved"), ("ARCHIVED", "Archived")], default="DRAFT")
    subject = models.CharField(max_length=500)
    body = models.TextField()
    placeholders = models.JSONField(default=list, help_text="List of placeholder variable names")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    approved_by = models.ForeignKey("users.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="email_templates_approved")
    approved_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.get_template_type_display()

    class Meta:
        ordering = ["template_type"]
        constraints = [models.UniqueConstraint(fields=["template_type", "version"], name="unique_email_template_version")]


class EmailLog(models.Model):
    STATUS_CHOICES = [
        ("DRAFT", "Draft"),
        ("QUEUED", "Queued"),
        ("SENDING", "Sending"),
        ("RETRYING", "Retrying"),
        ("SENT", "Sent"),
        ("DELIVERED", "Delivered"),
        ("BOUNCED", "Bounced"),
        ("FAILED", "Failed"),
    ]

    template = models.ForeignKey(EmailTemplate, null=True, blank=True, on_delete=models.SET_NULL)
    subject = models.CharField(max_length=500)
    body = models.TextField()
    recipients = models.JSONField(help_text='[{"email": "...", "name": "..."}]')
    cc = models.JSONField(default=list)
    provider = models.ForeignKey(
        "providers.ProviderProfile", null=True, blank=True, on_delete=models.SET_NULL
    )
    expected_submission = models.ForeignKey(
        "submissions.ExpectedSubmission", null=True, blank=True, on_delete=models.SET_NULL
    )
    period = models.ForeignKey(
        "submissions.ReportingPeriod", null=True, blank=True, on_delete=models.SET_NULL
    )
    generated_by = models.ForeignKey("users.User", on_delete=models.PROTECT, related_name="emails_generated")
    generated_at = models.DateTimeField(auto_now_add=True)
    sent_by = models.ForeignKey(
        "users.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="emails_sent"
    )
    sent_at = models.DateTimeField(null=True, blank=True)
    compliance_stage = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="DRAFT")
    provider_key = models.CharField(max_length=50, blank=True)
    provider_message_id = models.CharField(max_length=255, blank=True)
    idempotency_key = models.CharField(max_length=100, blank=True, unique=True, null=True)
    queued_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveIntegerField(default=0)
    next_retry_at = models.DateTimeField(null=True, blank=True)
    failure_reason = models.TextField(blank=True)
    attachments = models.JSONField(default=list, blank=True)
    sender_snapshot = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"{self.subject} → {self.provider}"

    class Meta:
        ordering = ["-generated_at"]


class EmailDeliveryEvent(models.Model):
    email = models.ForeignKey(EmailLog, on_delete=models.CASCADE, related_name="delivery_events")
    event_type = models.CharField(max_length=30)
    provider_event_id = models.CharField(max_length=255, blank=True)
    details = models.JSONField(default=dict)
    occurred_at = models.DateTimeField()
    recorded_at = models.DateTimeField(auto_now_add=True)


class TransactionalOutbox(models.Model):
    topic = models.CharField(max_length=100)
    aggregate_type = models.CharField(max_length=100)
    aggregate_id = models.CharField(max_length=100)
    payload = models.JSONField(default=dict)
    idempotency_key = models.CharField(max_length=100, unique=True)
    status = models.CharField(max_length=20, choices=[("PENDING", "Pending"), ("PROCESSED", "Processed"), ("FAILED", "Failed")], default="PENDING")
    attempts = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)


class CommunicationPreview(models.Model):
    """Single-use workflow/email preview bound to a submission revision and action payload."""

    actor = models.ForeignKey("users.User", on_delete=models.PROTECT, related_name="communication_previews")
    submission = models.ForeignKey(
        "submissions.Submission", null=True, blank=True, on_delete=models.CASCADE,
        related_name="communication_previews",
    )
    expected_submission = models.ForeignKey(
        "submissions.ExpectedSubmission", null=True, blank=True, on_delete=models.CASCADE,
        related_name="communication_previews",
    )
    compliance_flag = models.ForeignKey(
        "ComplianceFlag", null=True, blank=True, on_delete=models.CASCADE,
        related_name="communication_previews",
    )
    action = models.CharField(max_length=80)
    action_payload = models.JSONField(default=dict)
    payload_sha256 = models.CharField(max_length=64)
    template = models.ForeignKey(EmailTemplate, null=True, blank=True, on_delete=models.PROTECT)
    subject = models.CharField(max_length=500)
    body = models.TextField()
    recipients = models.JSONField(default=list)
    cc = models.JSONField(default=list)
    attachments = models.JSONField(default=list)
    submission_revision = models.PositiveIntegerField(null=True, blank=True)
    workflow_status = models.CharField(max_length=30, blank=True)
    consumed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]


class CommunicationRecord(models.Model):
    CHANNEL_CHOICES = [("SYSTEM", "System Notification"), ("EMAIL", "Email"), ("BOTH", "System and Email")]
    DIRECTION_CHOICES = [("OUTBOUND", "Outbound"), ("INBOUND", "Inbound"), ("INTERNAL", "Internal")]

    submission = models.ForeignKey(
        "submissions.Submission", null=True, blank=True, on_delete=models.PROTECT,
        related_name="communications",
    )
    expected_submission = models.ForeignKey(
        "submissions.ExpectedSubmission", null=True, blank=True, on_delete=models.PROTECT,
        related_name="communications",
    )
    compliance_flag = models.ForeignKey(
        "ComplianceFlag", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="communications",
    )
    submission_event = models.ForeignKey(
        "submissions.SubmissionEvent", null=True, blank=True, on_delete=models.PROTECT,
        related_name="communications",
    )
    email_log = models.OneToOneField(
        EmailLog, null=True, blank=True, on_delete=models.PROTECT, related_name="communication",
    )
    event_type = models.CharField(max_length=80)
    channel = models.CharField(max_length=10, choices=CHANNEL_CHOICES)
    direction = models.CharField(max_length=10, choices=DIRECTION_CHOICES, default="OUTBOUND")
    sender = models.ForeignKey("users.User", null=True, blank=True, on_delete=models.PROTECT, related_name="communications_sent")
    sender_snapshot = models.JSONField(default=dict)
    recipients = models.JSONField(default=list)
    subject = models.CharField(max_length=500, blank=True)
    body = models.TextField()
    from_status = models.CharField(max_length=30, blank=True)
    to_status = models.CharField(max_length=30, blank=True)
    submission_reference = models.CharField(max_length=180, blank=True, db_index=True)
    attachments = models.JSONField(default=list)
    content_sha256 = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["submission_event"],
                condition=models.Q(submission_event__isnull=False),
                name="unique_communication_per_submission_event",
            ),
        ]


class ExternalEmailHandoff(models.Model):
    """An optional mail-client draft created after one completed workflow event."""

    STATUS_CHOICES = [
        ("AVAILABLE", "Available"),
        ("OPENED", "Opened in email application"),
        ("DEFERRED", "Deferred"),
    ]

    event = models.OneToOneField(
        "submissions.SubmissionEvent", on_delete=models.PROTECT,
        related_name="email_handoff",
    )
    communication = models.OneToOneField(
        CommunicationRecord, on_delete=models.PROTECT, related_name="email_handoff",
    )
    submission = models.ForeignKey(
        "submissions.Submission", on_delete=models.PROTECT, related_name="email_handoffs",
    )
    action = models.CharField(max_length=80)
    recipients = models.JSONField(default=list)
    subject = models.CharField(max_length=500)
    body = models.TextField()
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="AVAILABLE")
    created_by = models.ForeignKey(
        "users.User", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="email_handoffs_created",
    )
    opened_by = models.ForeignKey(
        "users.User", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="email_handoffs_opened",
    )
    opened_at = models.DateTimeField(null=True, blank=True)
    deferred_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]


class IncomingMailboxMessage(models.Model):
    LINK_STATUS_CHOICES = [("MATCHED", "Matched"), ("UNMATCHED", "Unmatched"), ("LINKED", "Manually linked")]
    provider_message_id = models.CharField(max_length=255, unique=True)
    internet_message_id = models.CharField(max_length=500, blank=True)
    conversation_id = models.CharField(max_length=255, blank=True)
    sender = models.JSONField(default=dict)
    recipients = models.JSONField(default=list)
    subject = models.CharField(max_length=500)
    body = models.TextField(blank=True)
    received_at = models.DateTimeField()
    reference = models.CharField(max_length=180, blank=True, db_index=True)
    link_status = models.CharField(max_length=20, choices=LINK_STATUS_CHOICES, default="UNMATCHED")
    submission = models.ForeignKey(
        "submissions.Submission", null=True, blank=True, on_delete=models.PROTECT,
        related_name="incoming_mail",
    )
    communication = models.OneToOneField(
        CommunicationRecord, null=True, blank=True, on_delete=models.PROTECT,
        related_name="incoming_message",
    )
    attachments = models.JSONField(default=list)
    raw_metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-received_at", "-id"]


class IncomingEmailAttachment(models.Model):
    SCAN_CHOICES = [
        ("PENDING", "Pending"), ("CLEAN", "Clean"), ("INFECTED", "Infected"),
        ("ERROR", "Error"),
    ]
    message = models.ForeignKey(
        IncomingMailboxMessage, on_delete=models.CASCADE, related_name="quarantined_attachments",
    )
    provider_attachment_id = models.CharField(max_length=255, blank=True)
    file_name = models.CharField(max_length=255)
    mime_type = models.CharField(max_length=150, blank=True)
    file_size = models.PositiveBigIntegerField(default=0)
    storage_path = models.CharField(max_length=500)
    sha256 = models.CharField(max_length=64)
    scan_status = models.CharField(max_length=12, choices=SCAN_CHOICES, default="PENDING")
    scan_engine = models.CharField(max_length=100, blank=True)
    scan_details = models.TextField(blank=True)
    scanned_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]
        constraints = [models.UniqueConstraint(
            fields=["message", "provider_attachment_id"], name="unique_incoming_message_attachment",
        )]


class GraphMailboxState(models.Model):
    mailbox = models.EmailField(unique=True)
    subscription_id = models.CharField(max_length=255, blank=True)
    subscription_expires_at = models.DateTimeField(null=True, blank=True)
    delta_link = models.TextField(blank=True)
    last_reconciled_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)


class ComplianceFlag(models.Model):
    FLAG_TYPE_CHOICES = [
        ("MISSING_DATA", "Missing Required Data"),
        ("OVERDUE", "Overdue Submission"),
        ("INCOMPLETE", "Incomplete Form"),
        ("CORRECTION", "Correction Requested"),
    ]
    STATUS_CHOICES = [
        ("OPEN", "Open"),
        ("ACKNOWLEDGED", "Acknowledged by Provider"),
        ("IN_PROGRESS", "In Progress"),
        ("RESOLVED", "Resolved"),
    ]

    expected_submission = models.ForeignKey(
        "submissions.ExpectedSubmission",
        on_delete=models.CASCADE,
        related_name="compliance_flags",
    )
    provider = models.ForeignKey(
        "providers.ProviderProfile",
        on_delete=models.CASCADE,
        related_name="compliance_flags",
    )
    flag_type = models.CharField(max_length=20, choices=FLAG_TYPE_CHOICES)
    description = models.TextField(help_text="What is missing or needs attention")
    missing_field_count = models.PositiveIntegerField(default=0)
    completion_percentage = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="OPEN")
    created_at = models.DateTimeField(auto_now_add=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.get_flag_type_display()} - {self.provider}"

    class Meta:
        ordering = ["-created_at"]
        unique_together = [["expected_submission", "flag_type"]]


class FlagCorrespondence(models.Model):
    TYPE_CHOICES = [
        ("NOTE", "Internal Note"),
        ("EMAIL_SENT", "Email Sent to Provider"),
        ("EMAIL_RECEIVED", "Email from Provider"),
    ]

    flag = models.ForeignKey(
        ComplianceFlag,
        on_delete=models.CASCADE,
        related_name="correspondence",
    )
    message_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="NOTE")
    subject = models.CharField(max_length=500, blank=True, help_text="For emails")
    message = models.TextField()
    created_by = models.ForeignKey(
        "users.User", null=True, blank=True, on_delete=models.SET_NULL
    )
    created_at = models.DateTimeField(auto_now_add=True)
    email_log = models.ForeignKey(
        EmailLog, null=True, blank=True, on_delete=models.SET_NULL, related_name="correspondence"
    )

    def __str__(self):
        return f"{self.get_message_type_display()} on {self.created_at}"

    class Meta:
        ordering = ["created_at"]
