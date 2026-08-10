from rest_framework import serializers
from .models import User, Organization


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ["id", "name", "org_type"]


class UserSerializer(serializers.ModelSerializer):
    organization = OrganizationSerializer(read_only=True)
    organization_id = serializers.PrimaryKeyRelatedField(
        source="organization", queryset=Organization.objects.all(),
        write_only=True, required=False, allow_null=True,
    )
    password = serializers.CharField(write_only=True, required=False, min_length=10)

    class Meta:
        model = User
        fields = [
            "id", "email", "name", "role", "organization", "organization_id",
            "password", "is_active", "mfa_enabled", "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def validate(self, attrs):
        role = attrs.get("role", getattr(self.instance, "role", None))
        organization = attrs.get("organization", getattr(self.instance, "organization", None))
        if role in ("PROVIDER_DATA_ENTRY", "PROVIDER_APPROVER"):
            if not organization or organization.org_type != "PROVIDER":
                raise serializers.ValidationError(
                    {"organization_id": "Provider roles require a provider organization."}
                )
        elif role in ("NCA_ADMIN", "NCA_OFFICER"):
            if organization and organization.org_type != "NCA":
                raise serializers.ValidationError(
                    {"organization_id": "NCA roles cannot belong to a provider organization."}
                )
        else:
            raise serializers.ValidationError({"role": "Unsupported role."})
        return attrs

    def create(self, validated_data):
        password = validated_data.pop("password", None)
        if not password:
            raise serializers.ValidationError({"password": "Password is required."})
        return User.objects.create_user(password=password, **validated_data)

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        instance = super().update(instance, validated_data)
        if password:
            instance.set_password(password)
            instance.save(update_fields=["password"])
        return instance


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
