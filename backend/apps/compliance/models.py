from django.db import models


class EmailTemplate(models.Model):
    TYPE_CHOICES = [
        ("PERIOD_OPEN", "Period Opening Notice"),
        ("REMINDER", "Submission Reminder"),
        ("DRAFT_INCOMPLETE", "Draft Incomplete Reminder"),
        ("MISSING_FIELDS", "Missing Required Fields"),
        ("CORRECTION_REQUEST", "Correction Request"),
        ("OVERDUE", "Overdue Notice"),
        ("ESCALATION", "Escalation Notice"),
        ("PENALTY_WARNING", "Penalty Warning"),
        ("FINAL_NOTICE", "Final Compliance Notice"),
    ]

    template_type = models.CharField(max_length=30, choices=TYPE_CHOICES, unique=True)
    subject = models.CharField(max_length=500)
    body = models.TextField()
    placeholders = models.JSONField(default=list, help_text="List of placeholder variable names")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.get_template_type_display()


class EmailLog(models.Model):
    STATUS_CHOICES = [
        ("DRAFT", "Draft"),
        ("SENT", "Sent"),
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

    def __str__(self):
        return f"{self.subject} → {self.provider}"

    class Meta:
        ordering = ["-generated_at"]
