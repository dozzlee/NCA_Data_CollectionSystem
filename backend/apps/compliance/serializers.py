from rest_framework import serializers
from .models import ComplianceFlag, EmailTemplate, EmailLog, FlagCorrespondence, EmailDeliveryEvent


class EmailTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailTemplate
        fields = ["id", "template_type", "version", "status", "subject", "body", "placeholders", "approved_by", "approved_at"]
        read_only_fields = ["version", "status", "placeholders", "approved_by", "approved_at"]


class EmailDeliveryEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailDeliveryEvent
        fields = "__all__"
        read_only_fields = ["email", "recorded_at"]

    def validate_event_type(self, value):
        allowed = {"ACCEPTED", "DELIVERED", "FAILED", "BOUNCED", "DEFERRED"}
        if value not in allowed:
            raise serializers.ValidationError(f"Event type must be one of: {', '.join(sorted(allowed))}.")
        return value


class EmailLogSerializer(serializers.ModelSerializer):
    provider_name = serializers.CharField(source="provider.registered_name", read_only=True, default="")
    generated_by_name = serializers.CharField(source="generated_by.name", read_only=True)

    class Meta:
        model = EmailLog
        fields = [
            "id", "template", "subject", "recipients", "cc",
            "provider", "provider_name", "expected_submission", "period",
            "generated_by", "generated_by_name", "generated_at",
            "sent_by", "sent_at", "compliance_stage", "status", "provider_key", "provider_message_id", "queued_at",
        ]


class ComplianceFlagSerializer(serializers.ModelSerializer):
    provider_name = serializers.CharField(source="provider.registered_name", read_only=True)
    form_code = serializers.CharField(source="expected_submission.form_template.form_code", read_only=True)
    period_name = serializers.CharField(source="expected_submission.period.name", read_only=True)

    class Meta:
        model = ComplianceFlag
        fields = [
            "id", "expected_submission", "provider", "provider_name",
            "form_code", "period_name", "flag_type", "description",
            "missing_field_count", "completion_percentage", "status",
            "created_at", "acknowledged_at", "resolved_at",
        ]


class FlagCorrespondenceSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source="created_by.name", read_only=True, default="System")
    message_type_display = serializers.CharField(source="get_message_type_display", read_only=True)

    class Meta:
        model = FlagCorrespondence
        fields = [
            "id", "flag", "message_type", "message_type_display",
            "subject", "message", "created_by", "created_by_name",
            "created_at", "email_log",
        ]
