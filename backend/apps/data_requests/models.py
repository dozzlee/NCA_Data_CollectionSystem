import uuid
from django.conf import settings
from django.db import models


class DataRequest(models.Model):
    STATUSES = [(value, value.replace("_", " ").title()) for value in (
        "SUBMITTED", "UNDER_REVIEW", "CHANGES_REQUESTED", "APPROVED",
        "PREPARING", "READY", "GENERATION_FAILED", "REJECTED",
        "WITHDRAWN", "EXPIRED",
    )]
    FORMATS = [(value, value) for value in ("CSV", "XLSX", "PDF")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    requester = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="data_requests")
    requester_name = models.CharField(max_length=255)
    requester_email = models.EmailField()
    requesting_division = models.CharField(max_length=255)
    title = models.CharField(max_length=255)
    purpose = models.TextField()
    requested_format = models.CharField(max_length=5, choices=FORMATS)
    scope = models.JSONField(default=dict)
    status = models.CharField(max_length=30, choices=STATUSES, default="SUBMITTED", db_index=True)
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="reviewed_data_requests")
    expected_delivery_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.TextField(blank=True)
    approval_manifest = models.JSONField(null=True, blank=True)
    projected_row_count = models.PositiveIntegerField(null=True, blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-submitted_at"]


class DataRequestEvent(models.Model):
    request = models.ForeignKey(DataRequest, on_delete=models.CASCADE, related_name="events")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    actor_name = models.CharField(max_length=255, blank=True)
    actor_email = models.EmailField(blank=True)
    event_type = models.CharField(max_length=50)
    from_status = models.CharField(max_length=30, blank=True)
    to_status = models.CharField(max_length=30, blank=True)
    message = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValueError("Data request events are immutable.")
        super().save(*args, **kwargs)


class DataRequestNotification(models.Model):
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="data_request_notifications")
    request = models.ForeignKey(DataRequest, on_delete=models.CASCADE, related_name="notifications")
    title = models.CharField(max_length=255)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]


class DataRequestArtifact(models.Model):
    request = models.OneToOneField(DataRequest, on_delete=models.CASCADE, related_name="artifact")
    private_path = models.CharField(max_length=500)
    filename = models.CharField(max_length=255)
    mime_type = models.CharField(max_length=150)
    file_size = models.PositiveBigIntegerField(default=0)
    row_count = models.PositiveIntegerField(default=0)
    sha256 = models.CharField(max_length=64)
    generated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    generated_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    expired_at = models.DateTimeField(null=True, blank=True)

    @property
    def is_expired(self):
        from django.utils import timezone
        return bool(self.expired_at or self.expires_at <= timezone.now())
