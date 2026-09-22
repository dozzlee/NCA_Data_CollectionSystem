from rest_framework import serializers
from django.core.exceptions import ValidationError as DjangoValidationError
from .models import (
    ReportingPeriod, ExpectedSubmission, Submission, SubmissionValue, ReviewAction,
    SubmissionEvent, SubmissionNotification, ProviderApprovalDecision,
    ProviderWorkbookBaseline, WorkbookIndicatorMapping, MonthlyReportArtifact,
)


SUBMISSION_ACTION_LABELS = {
    "FORM_ASSIGNED": "Assigned",
    "SUBMISSION_STARTED": "Data Entry Started",
    "SUBMITTED_FOR_APPROVAL": "Submitted for Internal Review",
    "PROVIDER_CHANGES_REQUESTED": "Returned to Data Entry",
    "PROVIDER_RESUBMITTED": "Resubmitted for Internal Review",
    "PROVIDER_APPROVED": "Internally Approved",
    "OFFICIALLY_SUBMITTED": "Submitted Officially to NCA",
    "SUBMISSION_REVIEW_STARTED": "NCA Review Started",
    "CORRECTION_REQUESTED": "Flagged and Returned",
    "SUBMISSION_RESUBMITTED": "Resubmitted to NCA",
    "RESUBMITTED": "Resubmitted to NCA",
    "SUBMISSION_APPROVED": "Approved",
    "SUBMISSION_REJECTED": "Rejected",
    "DEADLINE_CHANGED": "Deadline Changed",
    "SUBMISSION_CORRESPONDENCE": "Message Sent",
    "ADD_NOTE": "Internal Note Added",
}


def _activity_for_expected(expected):
    event = SubmissionEvent.objects.filter(
        submission__expected=expected,
    ).order_by("-created_at", "-id").first()
    from apps.compliance.models import CommunicationRecord
    communication = CommunicationRecord.objects.filter(
        expected_submission=expected,
    ).order_by("-created_at", "-id").first()
    return event, communication


def _latest_message_payload(record, event):
    """Return correspondence content, falling back to legacy workflow events."""
    if record:
        body = record.body or ""
        return {
            "subject": record.subject,
            "preview": " ".join(body.split())[:160],
            "body": body,
            "event_type": record.event_type,
            "created_at": record.created_at,
        }
    if not event:
        return None
    body = event.message or ""
    return {
        "subject": SUBMISSION_ACTION_LABELS.get(
            event.event_type,
            event.event_type.replace("_", " ").title(),
        ),
        "preview": " ".join(body.split())[:160],
        "body": body,
        "event_type": event.event_type,
        "created_at": event.created_at,
    }


class ReportingPeriodSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReportingPeriod
        fields = "__all__"
        read_only_fields = ["created_at", "created_by"]

    def create(self, validated_data):
        validated_data["created_by"] = self.context["request"].user
        instance = ReportingPeriod(**validated_data)
        try:
            instance.full_clean()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(
                exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            ) from exc
        instance.save()
        return instance

    def update(self, instance, validated_data):
        for key, value in validated_data.items():
            setattr(instance, key, value)
        try:
            instance.full_clean()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(
                exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            ) from exc
        instance.save()
        return instance


class ExpectedSubmissionSerializer(serializers.ModelSerializer):
    provider_name = serializers.CharField(source="provider.registered_name", read_only=True)
    provider_sector = serializers.CharField(source="provider.sector", read_only=True)
    provider_category = serializers.CharField(source="provider.category", read_only=True)
    form_code = serializers.SerializerMethodField()
    form_name = serializers.SerializerMethodField()
    form_sector = serializers.SerializerMethodField()
    period_name = serializers.CharField(source="period.name", read_only=True)
    due_at = serializers.DateTimeField(source="period.due_at", read_only=True)
    effective_due_at = serializers.DateTimeField(read_only=True)
    assigned_officer_name = serializers.CharField(source="assigned_officer.name", read_only=True, default=None)
    latest_submission_id = serializers.SerializerMethodField()
    submission_reference = serializers.SerializerMethodField()
    latest_submission_version = serializers.SerializerMethodField()
    completion_pct = serializers.SerializerMethodField()
    last_edited_by = serializers.SerializerMethodField()
    last_edited_by_name = serializers.SerializerMethodField()
    last_edited_at = serializers.SerializerMethodField()
    submitted_at = serializers.SerializerMethodField()
    correction_count = serializers.SerializerMethodField()
    open_correction_count = serializers.SerializerMethodField()
    open_compliance_flag_count = serializers.SerializerMethodField()
    compliance_flag_types = serializers.SerializerMethodField()
    receipt_available = serializers.SerializerMethodField()
    receipt_reference = serializers.SerializerMethodField()
    permitted_actions = serializers.SerializerMethodField()
    assignment_source = serializers.SerializerMethodField()
    form_version = serializers.SerializerMethodField()
    form_created_at = serializers.SerializerMethodField()
    ownership_label = serializers.SerializerMethodField()
    data_entry_team = serializers.SerializerMethodField()
    last_data_entry_editor = serializers.SerializerMethodField()
    sent_at = serializers.SerializerMethodField()
    latest_message = serializers.SerializerMethodField()
    latest_action = serializers.SerializerMethodField()
    latest_action_at = serializers.SerializerMethodField()
    latest_communication_at = serializers.SerializerMethodField()
    penalty_amount_ghs = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)

    def _activity(self, obj):
        cache_name = "_serialized_expected_activity"
        cached = getattr(obj, cache_name, None)
        if cached is None:
            cached = _activity_for_expected(obj)
            setattr(obj, cache_name, cached)
        return cached

    def get_latest_action(self, obj):
        event, _ = self._activity(obj)
        if not event:
            return None
        return {
            "code": event.event_type,
            "label": SUBMISSION_ACTION_LABELS.get(event.event_type, event.event_type.replace("_", " ").title()),
            "from_status": event.from_status,
            "to_status": event.to_status,
        }

    def get_latest_action_at(self, obj):
        event, _ = self._activity(obj)
        return event.created_at if event else None

    def get_latest_communication_at(self, obj):
        _, communication = self._activity(obj)
        return communication.created_at if communication else None

    def _latest(self, obj):
        prefetched = getattr(obj, "workspace_versions", None)
        return prefetched[0] if prefetched else obj.versions.select_related("last_edited_by").order_by("-version").first()

    def get_form_code(self, obj):
        return obj.form_template.form_code if obj.form_template_id else obj.form_code_snapshot

    def get_form_name(self, obj):
        return obj.form_template.name if obj.form_template_id else obj.form_name_snapshot

    def get_form_sector(self, obj):
        return obj.form_template.sector if obj.form_template_id else obj.form_sector_snapshot

    def get_form_version(self, obj):
        return obj.form_template.version if obj.form_template_id else obj.form_version_snapshot

    def get_form_created_at(self, obj):
        return obj.form_template.created_at if obj.form_template_id else obj.form_created_at_snapshot

    def get_latest_submission_id(self, obj):
        latest = self._latest(obj)
        return latest.id if latest else None

    def get_submission_reference(self, obj):
        latest = self._latest(obj)
        return latest.submission_reference if latest else None

    def get_latest_submission_version(self, obj):
        latest = self._latest(obj)
        return latest.version if latest else None

    def get_completion_pct(self, obj):
        latest = self._latest(obj)
        return latest.completion_pct if latest else 0

    def get_last_edited_by(self, obj):
        latest = self._latest(obj)
        return latest.last_edited_by_id if latest else None

    def get_last_edited_by_name(self, obj):
        latest = self._latest(obj)
        return latest.last_edited_by.name if latest and latest.last_edited_by else None

    def get_last_edited_at(self, obj):
        latest = self._latest(obj)
        return latest.last_edited_at if latest else None

    def get_submitted_at(self, obj):
        latest = self._latest(obj)
        return latest.submitted_at if latest else None

    def get_correction_count(self, obj):
        latest = self._latest(obj)
        if not latest:
            return 0
        return latest.correction_items.count() + latest.resolved_correction_items.count()

    def get_open_correction_count(self, obj):
        latest = self._latest(obj)
        if not latest:
            return 0
        return latest.correction_items.filter(status="OPEN").count() + latest.resolved_correction_items.filter(status="OPEN").count()

    def get_open_compliance_flag_count(self, obj):
        return obj.compliance_flags.exclude(status="RESOLVED").count()

    def get_compliance_flag_types(self, obj):
        return list(obj.compliance_flags.exclude(status="RESOLVED").values_list("flag_type", flat=True))

    def get_receipt_available(self, obj):
        latest = self._latest(obj)
        return bool(latest and hasattr(latest, "receipt"))

    def get_receipt_reference(self, obj):
        latest = self._latest(obj)
        receipt = getattr(latest, "receipt", None) if latest else None
        return receipt.reference if receipt else None

    def get_permitted_actions(self, obj):
        from .provider_workspace import permitted_actions
        request = self.context.get("request")
        return permitted_actions(request.user, obj, self._latest(obj)) if request else []

    def get_assignment_source(self, obj):
        if obj.manual_assignment_id:
            return {"type": "MANUAL", "id": obj.manual_assignment_id}
        if obj.recurring_assignment_id:
            return {"type": "RECURRING", "id": obj.recurring_assignment_id}
        return {"type": "LEGACY", "id": None}

    def get_ownership_label(self, obj):
        return "Shared Data Entry queue"

    def get_data_entry_team(self, obj):
        organization_id = obj.provider.organization_id
        if not organization_id:
            return []
        from apps.users.models import User
        return list(User.objects.filter(
            organization_id=organization_id, role="PROVIDER_DATA_ENTRY", is_active=True,
        ).order_by("name").values("id", "name", "email"))

    def get_last_data_entry_editor(self, obj):
        latest = self._latest(obj)
        if not latest:
            return None
        value = latest.values.filter(
            updated_by__role="PROVIDER_DATA_ENTRY",
        ).select_related("updated_by").order_by("-updated_at", "-id").first()
        if not value or not value.updated_by:
            return None
        return {
            "id": value.updated_by_id,
            "name": value.updated_by.name,
            "email": value.updated_by.email,
            "edited_at": value.updated_at,
        }

    def get_sent_at(self, obj):
        event = obj.versions.filter(
            timeline_events__event_type="FORM_ASSIGNED",
        ).values_list("timeline_events__created_at", flat=True).order_by("timeline_events__created_at").first()
        return event or obj.created_at

    def get_latest_message(self, obj):
        event, record = self._activity(obj)
        return _latest_message_payload(record, event)

    class Meta:
        model = ExpectedSubmission
        fields = [
            "id", "provider", "provider_name", "provider_sector", "provider_category",
            "form_template", "form_code", "form_name", "form_sector", "form_version", "form_created_at",
            "period", "period_name", "due_at", "effective_due_at", "due_at_override",
            "workflow_status", "provider_status", "form_reference", "due_state",
            "assigned_officer", "assigned_officer_name",
            "latest_submission_id", "submission_reference",
            "latest_submission_version", "completion_pct", "last_edited_by", "last_edited_by_name",
            "last_edited_at", "submitted_at", "correction_count", "open_correction_count",
            "open_compliance_flag_count", "compliance_flag_types",
            "receipt_available", "receipt_reference", "permitted_actions", "assignment_source",
            "ownership_label", "data_entry_team", "last_data_entry_editor", "sent_at", "latest_message",
            "latest_action", "latest_action_at", "latest_communication_at",
            "penalty_amount_ghs", "penalty_reference", "penalty_note",
            "penalty_updated_by", "penalty_updated_at",
            "created_at",
            "replacement", "migration_report",
        ]
        read_only_fields = [
            "provider", "form_template", "period", "workflow_status", "due_state", "due_at_override",
            "penalty_amount_ghs", "penalty_reference", "penalty_note", "penalty_updated_by", "penalty_updated_at",
            "created_at", "replacement", "migration_report",
        ]


class SubmissionSerializer(serializers.ModelSerializer):
    provider = serializers.IntegerField(source="expected.provider_id", read_only=True)
    provider_name = serializers.CharField(source="expected.provider.registered_name", read_only=True)
    form_code = serializers.SerializerMethodField()
    form_name = serializers.SerializerMethodField()
    period_name = serializers.CharField(source="expected.period.name", read_only=True)
    workflow_status = serializers.CharField(source="expected.workflow_status", read_only=True)
    kmz_required = serializers.SerializerMethodField()
    form_template_id = serializers.IntegerField(source="expected.form_template_id", read_only=True)
    form_version = serializers.SerializerMethodField()
    mapping_basis = serializers.SerializerMethodField()
    source_reference = serializers.SerializerMethodField()
    last_edited_by_name = serializers.CharField(source="last_edited_by.name", read_only=True, default=None)
    receipt_reference = serializers.SerializerMethodField()
    provider_approval = serializers.SerializerMethodField()
    form_reference = serializers.CharField(source="expected.form_reference", read_only=True)
    latest_message = serializers.SerializerMethodField()
    is_formal_submission = serializers.SerializerMethodField()
    latest_action = serializers.SerializerMethodField()
    latest_action_at = serializers.SerializerMethodField()
    latest_communication_at = serializers.SerializerMethodField()

    def _activity(self, obj):
        cache_name = "_serialized_submission_activity"
        cached = getattr(obj, cache_name, None)
        if cached is None:
            cached = _activity_for_expected(obj.expected)
            setattr(obj, cache_name, cached)
        return cached

    def get_latest_action(self, obj):
        event, _ = self._activity(obj)
        if not event:
            return None
        return {
            "code": event.event_type,
            "label": SUBMISSION_ACTION_LABELS.get(event.event_type, event.event_type.replace("_", " ").title()),
            "from_status": event.from_status,
            "to_status": event.to_status,
        }

    def get_latest_action_at(self, obj):
        event, _ = self._activity(obj)
        return event.created_at if event else None

    def get_latest_communication_at(self, obj):
        _, communication = self._activity(obj)
        return communication.created_at if communication else None

    def get_receipt_reference(self, obj):
        receipt = getattr(obj, "receipt", None)
        return receipt.reference if receipt else None

    def _template_value(self, obj, key, default=""):
        if obj.expected.form_template_id:
            return getattr(obj.expected.form_template, key, default)
        snapshots = {
            "form_code": obj.expected.form_code_snapshot,
            "name": obj.expected.form_name_snapshot,
            "version": obj.expected.form_version_snapshot,
            "source_reference": obj.expected.form_source_reference_snapshot,
        }
        return snapshots.get(key, obj.form_schema_snapshot.get(key, default))

    def get_form_code(self, obj): return self._template_value(obj, "form_code")
    def get_form_name(self, obj): return self._template_value(obj, "name")
    def get_form_version(self, obj): return self._template_value(obj, "version")
    def get_mapping_basis(self, obj): return self._template_value(obj, "mapping_basis")
    def get_source_reference(self, obj): return self._template_value(obj, "source_reference")
    def get_kmz_required(self, obj): return bool(self._template_value(obj, "kmz_required", False))

    def get_provider_approval(self, obj):
        decision = getattr(obj, "provider_approval", None)
        if not decision:
            return None
        return ProviderApprovalDecisionSerializer(decision).data

    def get_latest_message(self, obj):
        event, record = self._activity(obj)
        return _latest_message_payload(record, event)

    def get_is_formal_submission(self, obj):
        return obj.regulatory_status != "DRAFT"

    class Meta:
        model = Submission
        fields = [
            "id", "submission_reference", "form_reference", "expected", "version", "completion_pct",
            "submitted_by", "submitted_at", "reviewed_by", "reviewed_at", "created_at",
            "provider", "provider_name", "form_code", "form_name", "period_name", "workflow_status", "kmz_required",
            "form_template_id", "form_version", "mapping_basis", "source_reference",
            "revision", "supersedes",
            "last_edited_by", "last_edited_by_name", "last_edited_at", "receipt_reference",
            "provider_approval", "regulatory_status", "latest_message", "is_formal_submission",
            "latest_action", "latest_action_at", "latest_communication_at",
        ]
        read_only_fields = ["submission_reference", "version", "created_at"]


class FormalSubmissionListSerializer(SubmissionSerializer):
    provider = serializers.IntegerField(source="expected.provider_id", read_only=True)
    provider_sector = serializers.CharField(source="expected.provider.sector", read_only=True)
    provider_category = serializers.CharField(source="expected.provider.category", read_only=True)
    form_template = serializers.IntegerField(source="expected.form_template_id", read_only=True)
    period = serializers.IntegerField(source="expected.period_id", read_only=True)
    due_at = serializers.DateTimeField(source="expected.period.due_at", read_only=True)
    effective_due_at = serializers.DateTimeField(source="expected.effective_due_at", read_only=True)
    due_state = serializers.CharField(source="expected.due_state", read_only=True)
    workflow_status = serializers.CharField(source="regulatory_status", read_only=True)
    responsible_approver = serializers.SerializerMethodField()
    receipt_available = serializers.SerializerMethodField()
    latest_submission_id = serializers.IntegerField(source="id", read_only=True)
    open_compliance_flag_count = serializers.SerializerMethodField()

    def get_responsible_approver(self, obj):
        decision = getattr(obj, "provider_approval", None)
        return decision.approver.name if decision else None

    def get_receipt_available(self, obj):
        return hasattr(obj, "receipt")

    def get_open_compliance_flag_count(self, obj):
        return obj.expected.compliance_flags.filter(status__in=["OPEN", "ACKNOWLEDGED", "IN_PROGRESS"]).count()

    class Meta(SubmissionSerializer.Meta):
        fields = SubmissionSerializer.Meta.fields + [
            "provider", "provider_sector", "provider_category", "form_template", "period",
            "due_at", "effective_due_at", "due_state", "responsible_approver",
            "receipt_available", "latest_submission_id", "open_compliance_flag_count",
        ]


class ProviderFormalTaskListSerializer(ExpectedSubmissionSerializer):
    """One provider-facing row for a form task, backed by its latest formal version."""

    form_task_id = serializers.IntegerField(source="id", read_only=True)
    regulatory_status = serializers.SerializerMethodField()
    provider_display_status = serializers.SerializerMethodField()
    version = serializers.SerializerMethodField()
    responsible_approver = serializers.SerializerMethodField()
    receipt_available = serializers.SerializerMethodField()
    open_compliance_flag_count = serializers.SerializerMethodField()
    formal_versions = serializers.SerializerMethodField()

    def _latest_formal(self, obj):
        prefetched = getattr(obj, "latest_formal_versions", None)
        if prefetched is not None:
            return prefetched[0] if prefetched else None
        return obj.versions.filter(
            regulatory_status__in=[
                "SUBMITTED", "UNDER_REVIEW", "RETURNED_FOR_CORRECTION", "APPROVED", "REJECTED",
            ],
        ).order_by("-version", "-id").first()

    def get_latest_submission_id(self, obj):
        latest = self._latest_formal(obj)
        return latest.id if latest else None

    def get_submission_reference(self, obj):
        latest = self._latest_formal(obj)
        return latest.submission_reference if latest else None

    def get_latest_submission_version(self, obj):
        latest = self._latest_formal(obj)
        return latest.version if latest else None

    def get_submitted_at(self, obj):
        latest = self._latest_formal(obj)
        return latest.submitted_at if latest else None

    def get_regulatory_status(self, obj):
        latest = self._latest_formal(obj)
        return latest.regulatory_status if latest else None

    def get_provider_display_status(self, obj):
        latest = self._latest_formal(obj)
        if latest and latest.regulatory_status == "RETURNED_FOR_CORRECTION":
            return "FLAGGED"
        return latest.regulatory_status if latest else None

    def get_version(self, obj):
        latest = self._latest_formal(obj)
        return latest.version if latest else None

    def get_responsible_approver(self, obj):
        latest = self._latest_formal(obj)
        decision = getattr(latest, "provider_approval", None) if latest else None
        return decision.approver.name if decision else None

    def get_receipt_available(self, obj):
        latest = self._latest_formal(obj)
        return bool(latest and hasattr(latest, "receipt"))

    def get_open_compliance_flag_count(self, obj):
        return obj.compliance_flags.filter(status__in=["OPEN", "ACKNOWLEDGED", "IN_PROGRESS"]).count()

    def get_formal_versions(self, obj):
        versions = getattr(obj, "latest_formal_versions", None)
        if versions is None:
            versions = obj.versions.filter(regulatory_status__in=[
                "SUBMITTED", "UNDER_REVIEW", "RETURNED_FOR_CORRECTION", "APPROVED", "REJECTED",
            ]).order_by("-version", "-id")
        return [{
            "id": item.id,
            "version": item.version,
            "submission_reference": item.submission_reference,
            "regulatory_status": item.regulatory_status,
            "submitted_at": item.submitted_at,
        } for item in versions]

    class Meta(ExpectedSubmissionSerializer.Meta):
        fields = ExpectedSubmissionSerializer.Meta.fields + [
            "form_task_id", "regulatory_status", "provider_display_status", "version",
            "responsible_approver", "formal_versions",
        ]


class ProviderApprovalDecisionSerializer(serializers.ModelSerializer):
    approver_name = serializers.CharField(source="approver.name", read_only=True)

    class Meta:
        model = ProviderApprovalDecision
        fields = [
            "id", "submission", "approver", "approver_name", "attestation",
            "approval_note", "change_summary", "approver_edited", "edit_batch_count", "decided_at",
        ]


class SubmissionValueSerializer(serializers.ModelSerializer):
    field = serializers.SerializerMethodField()
    grid = serializers.SerializerMethodField()
    grid_column = serializers.SerializerMethodField()
    non_filled_disposition = serializers.SerializerMethodField()
    disposition_note = serializers.SerializerMethodField()

    def get_non_filled_disposition(self, obj):
        disposition = getattr(obj, "non_filled_disposition", None)
        return disposition.decision if disposition else None

    def get_disposition_note(self, obj):
        disposition = getattr(obj, "non_filled_disposition", None)
        return disposition.note if disposition else ""

    def get_field(self, obj):
        if obj.field_id:
            return obj.field_id
        if obj.target_snapshot.get("target_type") == "FIELD":
            return obj.target_snapshot.get("target_id")
        return None

    def _grid_target_parts(self, obj):
        target = str(obj.target_snapshot.get("target_id", ""))
        parts = target.split(":")
        return parts if len(parts) == 3 else []

    def get_grid(self, obj):
        if obj.grid_id:
            return obj.grid_id
        parts = self._grid_target_parts(obj)
        return int(parts[0]) if parts and parts[0].isdigit() else None

    def get_grid_column(self, obj):
        if obj.grid_column_id:
            return obj.grid_column_id
        parts = self._grid_target_parts(obj)
        return int(parts[2]) if parts and parts[2].isdigit() else None

    class Meta:
        model = SubmissionValue
        fields = [
            "id", "submission", "field", "grid", "grid_row_id", "grid_column",
            "target_key_snapshot", "target_snapshot",
            "value", "value_status", "explanation", "value_source", "source_reference", "updated_by", "updated_at",
            "non_filled_disposition", "disposition_note",
        ]
        read_only_fields = ["id", "updated_at"]


class WorkbookIndicatorMappingSerializer(serializers.ModelSerializer):
    field_label = serializers.CharField(source="field.label", read_only=True, default=None)
    grid_title = serializers.CharField(source="grid.title", read_only=True, default=None)
    grid_row_label = serializers.CharField(source="grid_row.row_label", read_only=True, default=None)
    grid_column_label = serializers.CharField(source="grid_column.label", read_only=True, default=None)

    class Meta:
        model = WorkbookIndicatorMapping
        fields = "__all__"
        read_only_fields = ["baseline", "created_at"]


class ProviderWorkbookBaselineSerializer(serializers.ModelSerializer):
    provider_name = serializers.CharField(source="provider.registered_name", read_only=True)
    form_code = serializers.CharField(source="form_template.form_code", read_only=True)
    form_version = serializers.CharField(source="form_template.version", read_only=True)
    mappings = WorkbookIndicatorMappingSerializer(source="indicator_mappings", many=True, read_only=True)

    class Meta:
        model = ProviderWorkbookBaseline
        fields = "__all__"
        read_only_fields = [
            "form_template", "file_name", "storage_path", "file_size", "sha256",
            "scan_status", "scan_engine", "scan_details", "status", "mapping_summary",
            "created_by", "approved_by", "approved_at", "created_at", "updated_at",
        ]


class MonthlyReportArtifactSerializer(serializers.ModelSerializer):
    download_ready = serializers.SerializerMethodField()

    def get_download_ready(self, obj):
        return obj.status == "READY" and bool(obj.private_path)

    class Meta:
        model = MonthlyReportArtifact
        fields = [
            "id", "submission", "baseline", "status", "filename", "mime_type",
            "file_size", "sha256", "submission_revision", "generation_metadata",
            "error_message", "download_ready", "created_at", "completed_at", "updated_at",
        ]


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
    form_code = serializers.SerializerMethodField()
    provider_name = serializers.CharField(source="submission.expected.provider.registered_name", read_only=True)
    expected_submission = serializers.IntegerField(source="submission.expected_id", read_only=True)

    class Meta:
        model = SubmissionNotification
        fields = [
            "id", "submission", "event", "title", "message", "is_read", "read_at",
            "created_at", "form_code", "provider_name", "expected_submission",
        ]

    def get_form_code(self, obj):
        expected = obj.submission.expected
        return expected.form_template.form_code if expected.form_template_id else expected.form_code_snapshot
