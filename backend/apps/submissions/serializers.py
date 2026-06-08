from rest_framework import serializers
from .models import ReportingPeriod, ExpectedSubmission, Submission, SubmissionValue, ReviewAction


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

    def get_latest_submission_id(self, obj):
        latest = obj.versions.order_by("-version").first()
        return latest.id if latest else None

    class Meta:
        model = ExpectedSubmission
        fields = [
            "id", "provider", "provider_name", "provider_category",
            "form_template", "form_code", "form_name",
            "period", "period_name", "due_at", "due_at_override",
            "workflow_status", "due_state",
            "assigned_officer", "assigned_officer_name",
            "latest_submission_id",
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

    class Meta:
        model = Submission
        fields = [
            "id", "expected", "version", "completion_pct",
            "submitted_by", "submitted_at", "reviewed_by", "reviewed_at", "created_at",
            "provider_name", "form_code", "form_name", "period_name", "workflow_status", "kmz_required",
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
