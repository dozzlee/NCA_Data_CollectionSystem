from rest_framework import serializers

from .models import AuditEvent


class AuditEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditEvent
        fields = [
            "id",
            "user_email",
            "role",
            "organization",
            "action",
            "entity_type",
            "entity_id",
            "before_value",
            "after_value",
            "ip_address",
            "timestamp",
            "previous_hash",
            "event_hash",
        ]
        read_only_fields = fields
