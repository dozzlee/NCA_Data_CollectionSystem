from django.db import models


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
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValueError("AuditEvent records are immutable and cannot be updated.")
        super().save(*args, **kwargs)
