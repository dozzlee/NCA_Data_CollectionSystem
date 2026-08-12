from rest_framework import serializers
from .models import (
    ReportingPeriod, ExpectedSubmission, Submission, SubmissionValue, ReviewAction,
    SubmissionEvent, SubmissionNotification,
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
    provider_sector = serializers.CharField(source="provider.sector", read_only=True)
    provider_category = serializers.CharField(source="provider.category", read_only=True)
    form_code = serializers.CharField(source="form_template.form_code", read_only=True)
    form_name = serializers.CharField(source="form_template.name", read_only=True)
    form_sector = serializers.CharField(source="form_template.sector", read_only=True)
    period_name = serializers.CharField(source="period.name", read_only=True)
    due_at = serializers.DateTimeField(source="period.due_at", read_only=True)
    effective_due_at = serializers.DateTimeField(read_only=True)
    assigned_officer_name = serializers.CharField(source="assigned_officer.name", read_only=True, default=None)
    latest_submission_id = serializers.SerializerMethodField()

    def get_latest_submission_id(self, obj):
        latest = obj.versions.order_by("-version").first()
        return latest.id if latest else None

    class Meta:
        model = ExpectedSubmission
        fields = [
            "id", "provider", "provider_name", "provider_sector", "provider_category",
            "form_template", "form_code", "form_name", "form_sector",
            "period", "period_name", "due_at", "effective_due_at", "due_at_override",
            "workflow_status", "due_state",
            "assigned_officer", "assigned_officer_name",
            "latest_submission_id",
            "created_at",
            "replacement", "migration_report",
        ]
        read_only_fields = ["provider", "form_template", "period", "workflow_status", "due_state", "due_at_override", "created_at", "replacement", "migration_report"]


class SubmissionSerializer(serializers.ModelSerializer):
    provider_name = serializers.CharField(source="expected.provider.registered_name", read_only=True)
    form_code = serializers.CharField(source="expected.form_template.form_code", read_only=True)
    form_name = serializers.CharField(source="expected.form_template.name", read_only=True)
    period_name = serializers.CharField(source="expected.period.name", read_only=True)
    workflow_status = serializers.CharField(source="expected.workflow_status", read_only=True)
    kmz_required = serializers.BooleanField(source="expected.form_template.kmz_required", read_only=True)
    form_template_id = serializers.IntegerField(source="expected.form_template_id", read_only=True)
    form_version = serializers.CharField(source="expected.form_template.version", read_only=True)
    mapping_basis = serializers.CharField(source="expected.form_template.mapping_basis", read_only=True)
    source_reference = serializers.CharField(source="expected.form_template.source_reference", read_only=True)

    class Meta:
        model = Submission
        fields = [
            "id", "expected", "version", "completion_pct",
            "submitted_by", "submitted_at", "reviewed_by", "reviewed_at", "created_at",
            "provider_name", "form_code", "form_name", "period_name", "workflow_status", "kmz_required",
            "form_template_id", "form_version", "mapping_basis", "source_reference",
            "revision", "supersedes",
        ]
        read_only_fields = ["version", "created_at"]


class SubmissionValueSerializer(serializers.ModelSerializer):
    non_filled_disposition = serializers.SerializerMethodField()
    disposition_note = serializers.SerializerMethodField()

    def get_non_filled_disposition(self, obj):
        disposition = getattr(obj, "non_filled_disposition", None)
        return disposition.decision if disposition else None

    def get_disposition_note(self, obj):
        disposition = getattr(obj, "non_filled_disposition", None)
        return disposition.note if disposition else ""

    class Meta:
        model = SubmissionValue
        fields = [
            "id", "submission", "field", "grid", "grid_row_id", "grid_column",
            "value", "value_status", "explanation", "updated_by", "updated_at",
            "non_filled_disposition", "disposition_note",
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


class SubmissionEventSerializer(serializers.ModelSerializer):
    actor_name = serializers.CharField(source="actor.name", read_only=True, default=None)

    class Meta:
        model = SubmissionEvent
        fields = [
            "id", "submission", "event_type", "from_status", "to_status", "message",
            "audience", "metadata", "actor", "actor_name", "created_at",
        ]


class SubmissionNotificationSerializer(serializers.ModelSerializer):
    form_code = serializers.CharField(source="submission.expected.form_template.form_code", read_only=True)
    provider_name = serializers.CharField(source="submission.expected.provider.registered_name", read_only=True)
    expected_submission = serializers.IntegerField(source="submission.expected_id", read_only=True)

    class Meta:
        model = SubmissionNotification
        fields = [
            "id", "submission", "event", "title", "message", "is_read", "read_at",
            "created_at", "form_code", "provider_name", "expected_submission",
        ]
