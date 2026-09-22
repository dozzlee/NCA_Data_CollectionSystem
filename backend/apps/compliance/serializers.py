from rest_framework import serializers
from .models import (
    ComplianceFlag, EmailTemplate, EmailLog, FlagCorrespondence, EmailDeliveryEvent,
    CommunicationRecord, ExternalEmailHandoff, IncomingMailboxMessage,
)


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
            "id", "template", "subject", "body", "recipients", "cc", "attachments", "sender_snapshot",
            "provider", "provider_name", "expected_submission", "period",
            "generated_by", "generated_by_name", "generated_at",
            "sent_by", "sent_at", "compliance_stage", "status", "provider_key", "provider_message_id", "queued_at",
            "attempts", "next_retry_at", "failure_reason",
        ]


class ComplianceFlagSerializer(serializers.ModelSerializer):
    provider_name = serializers.CharField(source="provider.registered_name", read_only=True)
    form_code = serializers.SerializerMethodField()
    period_name = serializers.CharField(source="expected_submission.period.name", read_only=True)
    latest_submission_id = serializers.SerializerMethodField()

    def get_latest_submission_id(self, obj):
        versions = getattr(obj.expected_submission, "compliance_versions", None)
        latest = versions[0] if versions else obj.expected_submission.versions.order_by("-version").first()
        return latest.id if latest else None

    def get_form_code(self, obj):
        expected = obj.expected_submission
        return expected.form_template.form_code if expected.form_template_id else expected.form_code_snapshot

    class Meta:
        model = ComplianceFlag
        fields = [
            "id", "expected_submission", "latest_submission_id", "provider", "provider_name",
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


class CommunicationRecordSerializer(serializers.ModelSerializer):
    sender_name = serializers.SerializerMethodField()
    delivery_status = serializers.SerializerMethodField()
    email_handoff = serializers.SerializerMethodField()
    form_code = serializers.SerializerMethodField()
    form_name = serializers.SerializerMethodField()
    period_name = serializers.CharField(source="expected_submission.period.name", read_only=True, default="")
    submission_version = serializers.IntegerField(source="submission.version", read_only=True, default=None)

    def get_sender_name(self, obj):
        return obj.sender.name if obj.sender_id else obj.sender_snapshot.get("name", "System")

    def get_delivery_status(self, obj):
        return obj.email_log.status if obj.email_log_id else None

    def get_email_handoff(self, obj):
        handoff = getattr(obj, "email_handoff", None)
        request = self.context.get("request")
        if handoff and request and handoff.event.actor_id != request.user.id:
            return None
        return ExternalEmailHandoffSerializer(handoff).data if handoff else None

    def get_form_code(self, obj):
        expected = obj.expected_submission
        if not expected:
            return ""
        return expected.form_template.form_code if expected.form_template_id else expected.form_code_snapshot

    def get_form_name(self, obj):
        expected = obj.expected_submission
        if not expected:
            return ""
        return expected.form_template.name if expected.form_template_id else expected.form_name_snapshot

    class Meta:
        model = CommunicationRecord
        fields = [
            "id", "submission", "expected_submission", "compliance_flag", "submission_event",
            "email_log", "event_type", "channel", "direction", "sender", "sender_name",
            "sender_snapshot", "recipients", "subject", "body", "from_status", "to_status",
            "submission_reference", "attachments", "content_sha256", "delivery_status",
            "email_handoff", "form_code", "form_name", "period_name", "submission_version", "created_at",
        ]


class ExternalEmailHandoffSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExternalEmailHandoff
        fields = [
            "id", "event", "submission", "action", "recipients", "subject", "body",
            "status", "opened_at", "deferred_at", "created_at",
        ]


class IncomingMailboxMessageSerializer(serializers.ModelSerializer):
    quarantined_attachments = serializers.SerializerMethodField()

    def get_quarantined_attachments(self, obj):
        return [{
            "id": item.id, "file_name": item.file_name, "mime_type": item.mime_type,
            "file_size": item.file_size, "sha256": item.sha256, "scan_status": item.scan_status,
            "scan_details": item.scan_details,
        } for item in obj.quarantined_attachments.all()]

    class Meta:
        model = IncomingMailboxMessage
        fields = [
            "id", "provider_message_id", "internet_message_id", "conversation_id", "sender",
            "recipients", "subject", "body", "received_at", "reference", "link_status",
            "submission", "communication", "attachments", "quarantined_attachments", "created_at",
        ]
