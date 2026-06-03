from rest_framework import serializers
from .models import EmailTemplate, EmailLog


class EmailTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailTemplate
        fields = ["id", "template_type", "subject", "body", "placeholders"]


class EmailLogSerializer(serializers.ModelSerializer):
    provider_name = serializers.CharField(source="provider.registered_name", read_only=True, default="")
    generated_by_name = serializers.CharField(source="generated_by.name", read_only=True)

    class Meta:
        model = EmailLog
        fields = [
            "id", "template", "subject", "recipients", "cc",
            "provider", "provider_name", "expected_submission", "period",
            "generated_by", "generated_by_name", "generated_at",
            "sent_by", "sent_at", "compliance_stage", "status",
        ]
