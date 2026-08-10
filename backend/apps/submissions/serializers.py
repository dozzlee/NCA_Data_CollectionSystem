from rest_framework import serializers
from .models import (
    ReportingPeriod, ExpectedSubmission, Submission, SubmissionValue,
    ReviewAction, EditRequest, Notification,
)


class ReportingPeriodSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReportingPeriod
        fields = "__all__"
        read_only_fields = ["created_at", "created_by"]

    def create(self, validated_data):
        validated_data["created_by"] = self.context["request"].user
        return super().create(validated_data)


class ExpectedSubmissionSerializer(serializers.ModelSerializer):
    provider_name = serializers.CharField(source="provider.registered_name", read_only=True)
    provider_category = serializers.CharField(source="provider.category", read_only=True)
    form_code = serializers.CharField(source="form_template.form_code", read_only=True)
    form_name = serializers.CharField(source="form_template.name", read_only=True)
    period_name = serializers.CharField(source="period.name", read_only=True)
    due_at = serializers.DateTimeField(source="period.due_at", read_only=True)
    assigned_officer_name = serializers.CharField(source="assigned_officer.name", read_only=True, default=None)
    latest_submission_id = serializers.SerializerMethodField()
    latest_version = serializers.SerializerMethodField()
    latest_completion_pct = serializers.SerializerMethodField()
    latest_submitted_by = serializers.SerializerMethodField()
    latest_submitted_at = serializers.SerializerMethodField()

    def _latest(self, obj):
        prefetched = getattr(obj, "_prefetched_objects_cache", {}).get("versions")
        return max(prefetched, key=lambda item: item.version) if prefetched else obj.versions.order_by("-version").first()

    def get_latest_submission_id(self, obj):
        latest = self._latest(obj)
        return latest.id if latest else None

    def get_latest_version(self, obj):
        latest = self._latest(obj)
        return latest.version if latest else None

    def get_latest_completion_pct(self, obj):
        latest = self._latest(obj)
        return float(latest.completion_pct) if latest else 0

    def get_latest_submitted_by(self, obj):
        latest = self._latest(obj)
        return latest.submitted_by.email if latest and latest.submitted_by else None

    def get_latest_submitted_at(self, obj):
        latest = self._latest(obj)
        return latest.submitted_at if latest else None

    class Meta:
        model = ExpectedSubmission
        fields = [
            "id", "provider", "provider_name", "provider_category",
            "form_template", "form_code", "form_name",
            "period", "period_name", "due_at", "due_at_override",
            "workflow_status", "due_state",
            "assigned_officer", "assigned_officer_name",
            "latest_submission_id", "latest_version", "latest_completion_pct",
            "latest_submitted_by", "latest_submitted_at",
            "created_at",
        ]
        read_only_fields = ["due_state", "created_at"]


class SubmissionSerializer(serializers.ModelSerializer):
    provider_name = serializers.CharField(source="expected.provider.registered_name", read_only=True)
    form_code = serializers.CharField(source="expected.form_template.form_code", read_only=True)
    form_name = serializers.CharField(source="expected.form_template.name", read_only=True)
    period_name = serializers.CharField(source="expected.period.name", read_only=True)
    workflow_status = serializers.CharField(source="expected.workflow_status", read_only=True)
    kmz_required = serializers.BooleanField(source="expected.form_template.kmz_required", read_only=True)
    submitted_by_email = serializers.EmailField(source="submitted_by.email", read_only=True, default=None)

    class Meta:
        model = Submission
        fields = [
            "id", "expected", "version", "completion_pct",
            "submitted_by", "submitted_at", "reviewed_by", "reviewed_at", "created_at",
            "provider_name", "form_code", "form_name", "period_name", "workflow_status", "kmz_required",
            "submitted_by_email",
        ]
        read_only_fields = ["version", "created_at"]


class SubmissionValueSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubmissionValue
        fields = [
            "id", "submission", "field", "grid", "grid_row_id", "grid_column",
            "value", "value_status", "explanation", "updated_by", "updated_at",
        ]
        read_only_fields = ["id", "updated_at"]


class ReviewActionSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source="created_by.name", read_only=True)

    class Meta:
        model = ReviewAction
        fields = ["id", "submission", "action", "target_type", "target_id", "comment", "is_provider_visible", "created_by", "created_by_name", "created_at"]
        read_only_fields = ["id", "created_at", "created_by"]

    def create(self, validated_data):
        validated_data["created_by"] = self.context["request"].user
        return super().create(validated_data)


class EditRequestSerializer(serializers.ModelSerializer):
    provider_name = serializers.CharField(source="submission.expected.provider.registered_name", read_only=True)
    form_name = serializers.CharField(source="submission.expected.form_template.name", read_only=True)
    period_name = serializers.CharField(source="submission.expected.period.name", read_only=True)
    version = serializers.IntegerField(source="submission.version", read_only=True)
    requested_by_name = serializers.CharField(source="requested_by.name", read_only=True)
    decided_by_name = serializers.CharField(source="decided_by.name", read_only=True, default=None)

    class Meta:
        model = EditRequest
        fields = [
            "id", "submission", "provider_name", "form_name", "period_name", "version",
            "reason", "status", "requested_by", "requested_by_name", "requested_at",
            "decided_by", "decided_by_name", "decision_note", "decided_at",
            "reopened_submission",
        ]
        read_only_fields = [
            "id", "status", "requested_by", "requested_at", "decided_by",
            "decided_at", "decision_note", "reopened_submission",
        ]


class NotificationSerializer(serializers.ModelSerializer):
    is_read = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = [
            "id", "event_type", "title", "message", "target_url",
            "created_at", "read_at", "is_read",
        ]

    def get_is_read(self, obj):
        return obj.read_at is not None
