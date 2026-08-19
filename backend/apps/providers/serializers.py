from django.db.models import Q
import re
from rest_framework import serializers
from .models import ProviderProfile, ProviderContact, ProviderFormAssignment


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
            "id", "provider_id", "provider_code", "organization_id", "registered_name", "trade_name", "sector", "category",
            "licence_type", "licence_number", "licence_issue_date", "licence_expiry_date",
            "physical_address", "digital_address", "postal_address", "website",
            "primary_email", "primary_phone", "status",
            "created_at", "updated_at", "contacts",
        ]
        read_only_fields = ["id", "provider_id", "organization_id", "created_at", "updated_at"]
        extra_kwargs = {"provider_code": {"required": True}}

    def validate_provider_code(self, value):
        value = value.strip().upper()
        if not re.fullmatch(r"[A-Z0-9]{2,12}", value):
            raise serializers.ValidationError("Use 2-12 uppercase letters or numbers.")
        return value

    def validate(self, attrs):
        instance = self.instance
        if instance and "provider_code" in attrs and attrs["provider_code"] != instance.provider_code:
            if instance.expected_submissions.exists():
                raise serializers.ValidationError({"provider_code": "The provider code cannot change after submissions exist."})
        return attrs


class ProviderProfileListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list views — excludes nested contacts."""
    class Meta:
        model = ProviderProfile
        fields = [
            "id", "provider_id", "provider_code", "organization_id", "registered_name", "trade_name", "sector", "category",
            "licence_type", "licence_number", "primary_email", "primary_phone",
            "status", "created_at",
        ]
        read_only_fields = ["id", "provider_id", "organization_id", "created_at"]


class ProviderFormAssignmentSerializer(serializers.ModelSerializer):
    provider_name = serializers.CharField(source="provider.registered_name", read_only=True)
    provider_identifier = serializers.UUIDField(source="provider.provider_id", read_only=True)
    form_code = serializers.CharField(source="form_family.code", read_only=True)
    form_name = serializers.CharField(source="form_family.name", read_only=True)
    confirmed_by_name = serializers.CharField(source="confirmed_by.name", read_only=True)

    class Meta:
        model = ProviderFormAssignment
        fields = "__all__"
        read_only_fields = ["confirmed_by", "created_at", "updated_at"]

    def validate(self, attrs):
        provider = attrs.get("provider", getattr(self.instance, "provider", None))
        family = attrs.get("form_family", getattr(self.instance, "form_family", None))
        start = attrs.get("effective_from", getattr(self.instance, "effective_from", None))
        end = attrs.get("effective_to", getattr(self.instance, "effective_to", None))
        if start and end and end < start:
            raise serializers.ValidationError({"effective_to": "Must be on or after effective_from."})
        if provider and family and start:
            overlaps = ProviderFormAssignment.objects.filter(provider=provider, form_family=family).exclude(pk=getattr(self.instance, "pk", None))
            if end:
                overlaps = overlaps.filter(effective_from__lte=end)
            overlaps = overlaps.filter(Q(effective_to__isnull=True) | Q(effective_to__gte=start))
            if overlaps.exists():
                raise serializers.ValidationError("This provider and form already have an overlapping official assignment.")
        return attrs
