import hashlib
import json

from django.db import models
from django.utils import timezone


class AuditEvent(models.Model):
    """
    Immutable audit log. NEVER update or delete rows from this table.
    All system actions that change data must write an entry here.
    """
    user = models.ForeignKey("users.User", null=True, on_delete=models.SET_NULL, related_name="audit_events")
    user_email = models.EmailField()         # Denormalised — preserved if user is deleted
    role = models.CharField(max_length=50)
    organization = models.CharField(max_length=255)
    action = models.CharField(max_length=100)   # e.g. SUBMISSION_CREATED, VALUE_UPDATED
    entity_type = models.CharField(max_length=100)
    entity_id = models.CharField(max_length=100)
    before_value = models.JSONField(null=True, blank=True)
    after_value = models.JSONField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(default=timezone.now, editable=False)
    previous_hash = models.CharField(max_length=64, blank=True)
    event_hash = models.CharField(max_length=64, blank=True, db_index=True)

    class Meta:
        ordering = ["-timestamp"]

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValueError("AuditEvent records are immutable and cannot be updated.")
        if not self.previous_hash:
            previous = type(self).objects.order_by("-id").only("event_hash").first()
            self.previous_hash = previous.event_hash if previous else ""
        if not self.event_hash:
            payload = {
                "user_email": self.user_email,
                "role": self.role,
                "organization": self.organization,
                "action": self.action,
                "entity_type": self.entity_type,
                "entity_id": str(self.entity_id),
                "before": self.before_value,
                "after": self.after_value,
                "ip_address": str(self.ip_address or ""),
                "previous_hash": self.previous_hash,
                "timestamp": self.timestamp.isoformat(),
            }
            canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
            self.event_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        super().save(*args, **kwargs)

    def calculate_hash(self):
        payload = {
            "user_email": self.user_email,
            "role": self.role,
            "organization": self.organization,
            "action": self.action,
            "entity_type": self.entity_type,
            "entity_id": str(self.entity_id),
            "before": self.before_value,
            "after": self.after_value,
            "ip_address": str(self.ip_address or ""),
            "previous_hash": self.previous_hash,
            "timestamp": self.timestamp.isoformat(),
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()


class AuditAnchor(models.Model):
    anchor_date = models.DateField(unique=True)
    first_event_id = models.PositiveBigIntegerField(null=True)
    last_event_id = models.PositiveBigIntegerField(null=True)
    event_count = models.PositiveIntegerField(default=0)
    root_hash = models.CharField(max_length=64)
    signature = models.CharField(max_length=128)
    exported_reference = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
