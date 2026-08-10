from django.db import models


class FeedbackItem(models.Model):
    CATEGORY_CHOICES = [
        ("GENERAL", "General Feedback"),
        ("BUG", "Bug Report"),
        ("FEATURE", "Feature Request"),
        ("USABILITY", "Usability Issue"),
        ("OTHER", "Other"),
    ]

    submitted_by = models.ForeignKey(
        "users.User", null=True, on_delete=models.SET_NULL, related_name="feedback_submitted"
    )
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default="GENERAL")
    subject = models.CharField(max_length=255)
    message = models.TextField()
    page_url = models.CharField(max_length=500, blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    acknowledged = models.BooleanField(default=False)

    class Meta:
        ordering = ["-submitted_at"]

    def __str__(self):
        return f"{self.category} — {self.subject}"


class SystemIssueTicket(models.Model):
    SEVERITY_CHOICES = [
        ("LOW", "Low"),
        ("MEDIUM", "Medium"),
        ("HIGH", "High"),
        ("CRITICAL", "Critical"),
    ]
    STATUS_CHOICES = [
        ("OPEN", "Open"),
        ("IN_PROGRESS", "In Progress"),
        ("RESOLVED", "Resolved"),
        ("CLOSED", "Closed"),
    ]

    reported_by = models.ForeignKey(
        "users.User", null=True, on_delete=models.SET_NULL, related_name="issues_reported"
    )
    title = models.CharField(max_length=255)
    description = models.TextField()
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default="MEDIUM")
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="OPEN")
    page_url = models.CharField(max_length=500, blank=True)
    reported_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_note = models.TextField(blank=True)
    assigned_to = models.ForeignKey("users.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="support_tickets_assigned")
    assigned_team = models.CharField(max_length=100, blank=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    sla_due_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-reported_at"]

    def __str__(self):
        return f"[{self.severity}] {self.title}"


class SystemIssueEvent(models.Model):
    ticket = models.ForeignKey(SystemIssueTicket, on_delete=models.CASCADE, related_name="events")
    event_type = models.CharField(max_length=30)
    from_status = models.CharField(max_length=15, blank=True)
    to_status = models.CharField(max_length=15, blank=True)
    note = models.TextField(blank=True)
    actor = models.ForeignKey("users.User", null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
