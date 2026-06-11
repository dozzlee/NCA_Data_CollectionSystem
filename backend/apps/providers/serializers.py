from rest_framework import serializers

from .models import ProviderContact, ProviderProfile


class ProviderContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProviderContact
        fields = [
            "id",
            "name",
            "designation",
            "email",
            "phone",
            "notification_role",
            "is_active",
            "notify_on_period_open",
            "notify_on_reminder",
            "notify_on_review",
        ]


class ProviderProfileSerializer(serializers.ModelSerializer):
    contact_count = serializers.IntegerField(read_only=True)
    expected_count = serializers.IntegerField(read_only=True)
    overdue_count = serializers.IntegerField(read_only=True)
    open_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = ProviderProfile
        fields = [
            "id",
            "provider_id",
            "organization",
            "registered_name",
            "trade_name",
            "category",
            "licence_type",
            "licence_number",
            "licence_issue_date",
            "licence_expiry_date",
            "physical_address",
            "digital_address",
            "postal_address",
            "website",
            "primary_email",
            "primary_phone",
            "status",
            "contact_count",
            "expected_count",
            "overdue_count",
            "open_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "provider_id", "created_at", "updated_at"]
