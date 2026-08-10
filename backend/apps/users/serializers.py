from rest_framework import serializers
from .models import User, Organization


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ["id", "name", "org_type"]


class UserSerializer(serializers.ModelSerializer):
    organization = OrganizationSerializer(read_only=True)
    organization_id = serializers.PrimaryKeyRelatedField(
        source="organization",
        queryset=Organization.objects.filter(org_type="PROVIDER"),
        write_only=True,
        required=False,
        allow_null=True,
    )
    password = serializers.CharField(write_only=True, min_length=12, required=False)
    capabilities = serializers.SerializerMethodField()

    def get_capabilities(self, user):
        is_admin = user.role == "NCA_ADMIN"
        is_editor = user.role in {"NCA_ADMIN", "NCA_OFFICER"}
        is_nca_operations = user.role in {"NCA_ADMIN", "NCA_OFFICER"}
        is_requester = user.role == "NCA_VIEWER"
        return {
            "can_view_nca_operations": is_nca_operations,
            "can_review_submissions": is_editor,
            "can_manage_compliance": is_editor,
            "can_manage_periods": is_admin,
            "can_manage_forms": is_admin,
            "can_manage_users": is_admin,
            "can_export": is_nca_operations,
            "can_request_data": is_requester,
            "can_manage_data_requests": is_admin,
        }

    def validate(self, attrs):
        role = attrs.get("role", getattr(self.instance, "role", None))
        organization = attrs.get(
            "organization",
            getattr(self.instance, "organization", None),
        )
        if role in {"PROVIDER_DATA_ENTRY", "PROVIDER_APPROVER"} and not organization:
            raise serializers.ValidationError({
                "organization_id": "Provider users must be linked to a provider organization."
            })
        if role in {"NCA_ADMIN", "NCA_OFFICER", "NCA_VIEWER"}:
            attrs["organization"] = None
        return attrs

    def create(self, validated_data):
        password = validated_data.pop("password", None)
        user = User(**validated_data)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        instance = super().update(instance, validated_data)
        if password:
            instance.set_password(password)
            instance.save(update_fields=["password"])
        return instance

    class Meta:
        model = User
        fields = [
            "id", "email", "name", "password", "role", "organization",
            "organization_id", "is_active",
            "mfa_enabled", "created_at", "capabilities",
        ]
        read_only_fields = ["id", "created_at"]


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        from django.contrib.auth import authenticate
        from django.utils import timezone

        user = authenticate(email=data["email"], password=data["password"])
        if not user:
            raise serializers.ValidationError("Invalid email or password.")
        if not user.is_active:
            raise serializers.ValidationError("Account is inactive.")
        if user.locked_until and user.locked_until > timezone.now():
            raise serializers.ValidationError("Account is temporarily locked. Try again later.")
        data["user"] = user
        return data
