from rest_framework import serializers
from apps.forms_engine.models import FormField, FormTemplate, GridColumn
from apps.providers.models import ProviderProfile
from apps.submissions.models import ReportingPeriod
from apps.audit.services import record_audit
from .models import DataRequest, DataRequestEvent, DataRequestArtifact, DataRequestNotification


class EventSerializer(serializers.ModelSerializer):
    class Meta:
        model = DataRequestEvent
        exclude = ["request", "actor"]


class ArtifactSerializer(serializers.ModelSerializer):
    is_expired = serializers.BooleanField(read_only=True)
    class Meta:
        model = DataRequestArtifact
        exclude = ["id", "request", "private_path", "generated_by", "expired_at"]


class DataRequestSerializer(serializers.ModelSerializer):
    events = EventSerializer(many=True, read_only=True)
    artifact = ArtifactSerializer(read_only=True)
    reviewer_name = serializers.CharField(source="reviewer.name", read_only=True, allow_null=True)

    class Meta:
        model = DataRequest
        fields = "__all__"
        read_only_fields = [
            "requester", "requester_name", "requester_email", "status", "reviewer",
            "approval_manifest", "projected_row_count", "decision_note", "submitted_at",
            "updated_at", "approved_at", "completed_at", "expected_delivery_at", "events", "artifact",
        ]

    def validate_scope(self, scope):
        required = {"form_template_ids", "period_ids", "provider_scope"}
        if not required.issubset(scope):
            raise serializers.ValidationError("Choose at least one dataset, reporting period and provider scope.")
        if not scope.get("form_template_ids") or not scope.get("period_ids"):
            raise serializers.ValidationError("Choose at least one dataset and reporting period.")
        provider_scope = scope.get("provider_scope")
        if provider_scope not in {"ALL", "SECTOR", "CATEGORY", "SELECTED"}:
            raise serializers.ValidationError("Invalid provider scope.")
        if provider_scope == "SECTOR" and not scope.get("sector"):
            raise serializers.ValidationError("Choose a sector.")
        if provider_scope == "CATEGORY" and not scope.get("provider_category"):
            raise serializers.ValidationError("Choose a provider category.")
        if provider_scope == "SELECTED" and not scope.get("provider_ids"):
            raise serializers.ValidationError("Choose at least one provider.")
        form_ids = list(dict.fromkeys(scope.get("form_template_ids", [])))
        period_ids = list(dict.fromkeys(scope.get("period_ids", [])))
        field_ids = list(dict.fromkeys(scope.get("field_ids", [])))
        column_ids = list(dict.fromkeys(scope.get("grid_column_ids", [])))
        provider_ids = list(dict.fromkeys(scope.get("provider_ids", [])))
        if FormTemplate.objects.filter(id__in=form_ids, status="ACTIVE").count() != len(form_ids):
            raise serializers.ValidationError("One or more datasets are unavailable.")
        if ReportingPeriod.objects.filter(id__in=period_ids).count() != len(period_ids):
            raise serializers.ValidationError("One or more reporting periods are invalid.")
        if field_ids and FormField.objects.filter(id__in=field_ids, section__form_template_id__in=form_ids).count() != len(field_ids):
            raise serializers.ValidationError("Selected fields must belong to the selected datasets.")
        if column_ids and GridColumn.objects.filter(id__in=column_ids, grid__section__form_template_id__in=form_ids).count() != len(column_ids):
            raise serializers.ValidationError("Selected grid columns must belong to the selected datasets.")
        if not scope.get("all_fields", True) and not (field_ids or column_ids):
            raise serializers.ValidationError("Choose at least one field or grid column.")
        if provider_scope == "SELECTED" and ProviderProfile.objects.filter(id__in=provider_ids, status="ACTIVE").count() != len(provider_ids):
            raise serializers.ValidationError("One or more providers are unavailable.")
        return {
            "form_template_ids": form_ids,
            "period_ids": period_ids,
            "all_fields": bool(scope.get("all_fields", True)),
            "field_ids": field_ids,
            "grid_column_ids": column_ids,
            "provider_scope": provider_scope,
            "sector": scope.get("sector", ""),
            "provider_category": scope.get("provider_category", ""),
            "provider_ids": provider_ids if provider_scope == "SELECTED" else [],
        }

    def create(self, validated_data):
        user = self.context["request"].user
        from .services import eligible_submissions
        projected = sum(submission.values.count() for submission in eligible_submissions(validated_data["scope"]))
        item = DataRequest.objects.create(
            requester=user, requester_name=user.name, requester_email=user.email,
            projected_row_count=projected, **validated_data
        )
        add_event(item, user, "SUBMITTED", "", "SUBMITTED", "Request submitted for review.")
        return item


def add_event(item, actor, event_type, from_status, to_status, message, metadata=None, notify=False):
    event = DataRequestEvent.objects.create(
        request=item, actor=actor, actor_name=getattr(actor, "name", ""), actor_email=getattr(actor, "email", ""),
        event_type=event_type, from_status=from_status, to_status=to_status, message=message, metadata=metadata or {},
    )
    if notify:
        DataRequestNotification.objects.create(
            recipient=item.requester, request=item, title=event_type.replace("_", " ").title(), message=message
        )
    record_audit(
        user=actor,
        action=f"DATA_REQUEST_{event_type}",
        entity_type="DataRequest",
        entity_id=item.id,
        before={"status": from_status},
        after={"status": to_status, "message": message, "metadata": metadata or {}},
    )
    return event


class NotificationSerializer(serializers.ModelSerializer):
    request_title = serializers.CharField(source="request.title", read_only=True)
    class Meta:
        model = DataRequestNotification
        fields = ["id", "request", "request_title", "title", "message", "created_at", "read_at"]
