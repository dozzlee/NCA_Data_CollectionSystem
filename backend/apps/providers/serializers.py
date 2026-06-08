from rest_framework import serializers
from .models import ProviderProfile, ProviderContact


class ProviderContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProviderContact
        fields = [
            "id", "provider", "name", "designation", "email", "phone",
            "notification_role", "is_active",
            "notify_on_period_open", "notify_on_reminder", "notify_on_review",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class ProviderProfileSerializer(serializers.ModelSerializer):
    contacts = ProviderContactSerializer(many=True, read_only=True)

    class Meta:
        model = ProviderProfile
        fields = [
            "id", "provider_id", "registered_name", "trade_name", "category",
            "licence_type", "licence_number", "licence_issue_date", "licence_expiry_date",
            "physical_address", "digital_address", "postal_address", "website",
            "primary_email", "primary_phone", "status",
            "created_at", "updated_at", "contacts",
        ]
        read_only_fields = ["id", "provider_id", "created_at", "updated_at"]


class ProviderProfileListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list views — excludes nested contacts."""
    class Meta:
        model = ProviderProfile
        fields = [
            "id", "provider_id", "registered_name", "trade_name", "category",
            "licence_type", "licence_number", "primary_email", "primary_phone",
            "status", "created_at",
        ]
        read_only_fields = ["id", "provider_id", "created_at"]
