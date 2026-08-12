from django.db import transaction
from django.db.models import Count, Q
from django.http import FileResponse, HttpResponse
from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_datetime
from django.db.models.functions import TruncMonth
from django.utils import timezone
from datetime import timedelta
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.services import record_audit
from apps.compliance.models import TransactionalOutbox
from apps.users.permissions import (
    IsNCAUser, IsNCAEditor,
    IsProviderDataEntry, IsProviderApprover,
)
from .access import (
    expected_submissions_for_user,
    submissions_for_user,
    get_expected_submission_for_user,
    get_submission_for_user,
)
from .readiness import calculate_submission_readiness, refresh_submission_completion
from .models import (
    ReportingPeriod, ExpectedSubmission, Submission,
    SubmissionValue, ReviewAction, CorrectionItem, NonFilledDisposition,
    DeadlineChangeRequest, SubmissionOverride, ReminderPolicy,
    SubmissionEvent, SubmissionNotification,
)
from .serializers import (
    ReportingPeriodSerializer, ExpectedSubmissionSerializer,
    SubmissionSerializer, SubmissionValueSerializer, ReviewActionSerializer,
    SubmissionEventSerializer, SubmissionNotificationSerializer,
)
from .workflow import (
    audit_transition, clone_for_nca_correction, complete_submission_revision,
    lock_submission, mark_matching_corrections_addressed, mark_notification_read,
)


def write_audit(request, action, entity_type, entity_id, before=None, after=None):
    return record_audit(user=request.user, action=action, entity_type=entity_type, entity_id=entity_id,
        before=before, after=after, ip_address=request.META.get("REMOTE_ADDR"))


def dashboard_queryset(request):
    qs = ExpectedSubmission.objects.all()
    filters = {
        "period_id": "period_id", "form_id": "form_template_id", "provider_category": "provider__category",
        "sector": "provider__sector", "assigned_officer": "assigned_officer_id", "due_state": "due_state",
        "workflow_status": "workflow_status",
    }
    for parameter, lookup in filters.items():
        if value := request.query_params.get(parameter): qs = qs.filter(**{lookup: value})
    return qs


# ── Dashboard ────────────────────────────────────────────────────────────────

class DashboardSummaryView(APIView):
    permission_classes = [IsNCAUser]

    def get(self, request):
        qs = dashboard_queryset(request)
        total = qs.count()
        approved = qs.filter(workflow_status="APPROVED").count()
        expected_ids = list(qs.values_list("id", flat=True))
        latest_submissions = [item.versions.order_by("-version").first() for item in qs.prefetch_related("versions")]
        latest_submissions = [item for item in latest_submissions if item]
        required_slots = sum(item.expected.form_template.sections.filter(fields__is_required=True).count() for item in latest_submissions)
        completed_required = sum(item.values.filter(field__is_required=True, value_status__in=["PROVIDED","SYSTEM_CALCULATED","NOT_APPLICABLE","NOT_AVAILABLE","NOT_REQUIRED"]).count() for item in latest_submissions)
        kmz_required = sum(item.expected.form_template.kmz_requirements.filter(is_required=True).count() for item in latest_submissions)
        kmz_clean = sum(item.kmz_uploads.filter(scan_status="CLEAN").values("requirement_id").distinct().count() for item in latest_submissions)
        from apps.compliance.models import EmailLog
        reminders = EmailLog.objects.filter(expected_submission_id__in=expected_ids, compliance_stage__in=["REMINDER","OVERDUE"])
        return Response({
            "total_expected": total,
            "not_started": qs.filter(workflow_status="NOT_STARTED").count(),
            "draft": qs.filter(workflow_status="DRAFT").count(),
            "pending_approval": qs.filter(workflow_status="PENDING_APPROVAL").count(),
            "submitted": qs.filter(workflow_status="SUBMITTED").count(),
            "under_review": qs.filter(workflow_status="UNDER_REVIEW").count(),
            "correction_requested": qs.filter(workflow_status="CORRECTION_REQUESTED").count(),
            "resubmitted": qs.filter(workflow_status="RESUBMITTED").count(),
            "approved": approved,
            "rejected": qs.filter(workflow_status="REJECTED").count(),
            "overdue": qs.filter(due_state="OVERDUE").count(),
            "due_soon": qs.filter(due_state="DUE_SOON").count(),
            "completion_pct": round((approved / total) * 100, 1) if total else 0,
            "required_value_slots": required_slots,
            "required_values_complete": completed_required,
            "required_values_missing": max(required_slots - completed_required, 0),
            "required_kmz_slots": kmz_required,
            "clean_kmz_uploads": kmz_clean,
            "required_kmz_missing": max(kmz_required - kmz_clean, 0),
            "reminders_draft": reminders.filter(status="DRAFT").count(),
            "reminders_queued": reminders.filter(status="QUEUED").count(),
            "reminders_delivered": reminders.filter(status="DELIVERED").count(),
        })


class MetricCatalogueView(APIView):
    permission_classes = [IsNCAUser]
    def get(self, request):
        return Response([
            {"code":"SUBMISSION_COMPLETION","label":"Approved submissions","unit":"percentage","source":"ExpectedSubmission.workflow_status"},
            {"code":"REQUIRED_VALUES","label":"Required value completeness","unit":"count","source":"FormField/SubmissionValue"},
            {"code":"KMZ_COMPLETENESS","label":"Clean required KMZ uploads","unit":"count","source":"KMZUploadRequirement/SubmissionKMZUpload"},
            {"code":"REMINDER_LIFECYCLE","label":"Reminder queue and delivery","unit":"count","source":"EmailLog"},
            {"code":"DUE_STATE","label":"Submission due state","unit":"count","source":"ExpectedSubmission.due_state"},
        ])


class StatusDonutView(APIView):
    permission_classes = [IsNCAUser]

    def get(self, request):
        qs = dashboard_queryset(request)
        return Response(list(qs.values("workflow_status").annotate(count=Count("id")).order_by("workflow_status")))


class CategoryCompletionView(APIView):
    permission_classes = [IsNCAUser]

    def get(self, request):
        qs = dashboard_queryset(request)
        cats = qs.values("provider__sector", "provider__category").annotate(
            total=Count("id"),
            approved=Count("id", filter=Q(workflow_status="APPROVED")),
        )
        return Response([{
            "sector": c["provider__sector"],
            "category": c["provider__category"],
            "completion_pct": round((c["approved"] / (c["total"] or 1)) * 100, 1),
            "total": c["total"], "approved": c["approved"],
        } for c in cats])


class SubmissionTrendView(APIView):
    permission_classes = [IsNCAUser]

    def get(self, request):
        cutoff = timezone.now() - timedelta(days=365)
        data = (
            Submission.objects.filter(submitted_at__gte=cutoff, submitted_at__isnull=False)
            .annotate(month=TruncMonth("submitted_at"))
            .values("month").annotate(count=Count("id")).order_by("month")
        )
        return Response(list(data))


class OverdueByFormView(APIView):
    permission_classes = [IsNCAUser]

    def get(self, request):
        return Response(list(
            dashboard_queryset(request).filter(due_state="OVERDUE")
            .values("form_template__form_code", "form_template__name")
            .annotate(count=Count("id")).order_by("-count")
        ))


# ── Periods ──────────────────────────────────────────────────────────────────

class ReportingPeriodListView(generics.ListCreateAPIView):
    queryset = ReportingPeriod.objects.all()
    serializer_class = ReportingPeriodSerializer
    filterset_fields = ["frequency", "status", "year"]

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsNCAEditor()]
        return [IsNCAUser()]


class ReportingPeriodDetailView(generics.RetrieveUpdateAPIView):
    queryset = ReportingPeriod.objects.all()
    serializer_class = ReportingPeriodSerializer

    def get_permissions(self):
        if self.request.method in ("GET", "HEAD", "OPTIONS"):
            return [IsNCAUser()]
        return [IsNCAEditor()]


class ActivatePeriodView(APIView):
    permission_classes = [IsNCAEditor]

    def post(self, request, pk):
        try:
            period = ReportingPeriod.objects.get(pk=pk)
        except ReportingPeriod.DoesNotExist:
            return Response({"detail": "Not found."}, status=404)
        if period.status != "DRAFT":
            return Response({"detail": "Only DRAFT periods can be activated."}, status=400)
        try:
            period.activate()
        except ValueError as exc:
            return Response({"code": "ACTIVATION_BLOCKED", "detail": str(exc)}, status=409)
        write_audit(request, "PERIOD_ACTIVATED", "ReportingPeriod", period.id)
        return Response({"detail": "Activated.", "expected_count": period.expected_submissions.count()})


# ── Expected Submissions ──────────────────────────────────────────────────────

class ExpectedSubmissionListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    queryset = ExpectedSubmission.objects.select_related("provider", "form_template", "period", "assigned_officer")
    serializer_class = ExpectedSubmissionSerializer
    filterset_fields = [
        "workflow_status", "due_state", "form_template", "period", "provider",
        "provider__sector", "provider__category", "assigned_officer",
    ]
    search_fields = ["provider__registered_name", "form_template__form_code"]
    ordering_fields = ["period__due_at", "workflow_status", "due_state"]

    def get_queryset(self):
        return expected_submissions_for_user(self.request.user).select_related(
            "provider", "form_template", "period", "assigned_officer"
        )


class ExpectedSubmissionDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = ExpectedSubmissionSerializer
    http_method_names = ["get", "patch", "head", "options"]

    def get_permissions(self):
        if self.request.method == "PATCH":
            return [IsNCAEditor()]
        return [IsAuthenticated()]

    def get_queryset(self):
        return expected_submissions_for_user(self.request.user)


# ── Submissions ───────────────────────────────────────────────────────────────

class StartSubmissionView(APIView):
    permission_classes = [IsProviderDataEntry]

    @transaction.atomic
    def post(self, request, pk):
        visible = get_expected_submission_for_user(request.user, pk=pk)
        expected = ExpectedSubmission.objects.select_for_update().get(pk=visible.pk)
        if expected.workflow_status not in ("NOT_STARTED", "CORRECTION_REQUESTED"):
            return Response({"detail": "Cannot start in current state."}, status=400)
        last = expected.versions.order_by("-version").first()
        correcting = expected.workflow_status == "CORRECTION_REQUESTED" and last is not None
        if correcting:
            if last.supersedes_id and last.submitted_at is None:
                submission = last
            else:
                submission = clone_for_nca_correction(last)
                last.correction_items.filter(stage="NCA_REVIEW", status="OPEN").update(resolution_submission=submission)
        else:
            submission = Submission.objects.create(expected=expected, version=1)
        prior_status = expected.workflow_status
        expected.workflow_status = "DRAFT"
        expected.save(update_fields=["workflow_status"])
        audit_transition(
            request=request, submission=submission, event_type="SUBMISSION_STARTED",
            message="A correction version was opened for editing." if correcting else "The form was opened for data entry.",
            from_status=prior_status, to_status="DRAFT", audience="BOTH",
        )
        return Response(SubmissionSerializer(submission).data, status=201)


class SubmissionDetailView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = SubmissionSerializer

    def get_queryset(self):
        return submissions_for_user(self.request.user).select_related(
            "expected__provider", "expected__form_template", "expected__period"
        )


class SubmissionReviewDataView(APIView):
    """One exact-version payload for regulatory review; never substitutes a newer template."""
    permission_classes = [IsNCAUser]

    def get(self, request, pk):
        from apps.forms_engine.gaps import recalculate_form_gaps
        from apps.forms_engine.serializers import FormTemplateDetailSerializer, FormGapAssessmentSerializer

        submission = get_submission_for_user(request.user, pk=pk)
        template = submission.expected.form_template
        readiness = refresh_submission_completion(submission)
        assessments = recalculate_form_gaps(template, request.user)
        values = submission.values.select_related("field", "grid", "grid_column", "non_filled_disposition")
        uploads = submission.kmz_uploads.select_related("requirement", "reviewed_by")
        validation_run = submission.validation_runs.prefetch_related("results").order_by("-started_at").first()
        correction_items = CorrectionItem.objects.filter(
            Q(source_submission=submission) | Q(resolution_submission=submission)
        ).distinct()
        high_gaps = [item for item in assessments if item.status != "MATCHED" and item.requirement.severity in {"BLOCKER", "HIGH"}]
        return Response({
            "submission": SubmissionSerializer(submission).data,
            "template": FormTemplateDetailSerializer(template).data,
            "values": SubmissionValueSerializer(values, many=True).data,
            "requirements": FormGapAssessmentSerializer(assessments, many=True).data,
            "uploads": [{
                "id": item.id, "requirement": item.requirement_id, "category": item.requirement.category,
                "file_name": item.file_name, "file_size": item.file_size, "sha256": item.sha256,
                "scan_status": item.scan_status, "review_status": item.review_status,
                "review_note": item.review_note, "uploaded_at": item.uploaded_at,
            } for item in uploads],
            "validation": None if not validation_run else {
                "id": validation_run.id, "status": validation_run.status, "scope": validation_run.scope,
                "completed_at": validation_run.completed_at,
                "results": [{"id": result.id, "severity": result.severity, "target_type": result.target_type,
                    "target_id": result.target_id, "code": result.code, "message": result.message,
                    "details": result.details} for result in validation_run.results.all()],
            },
            "approval_blockers": readiness.get("blocking_issues", []),
            "correction_items": [{"id": item.id, "stage": item.stage, "target_type": item.target_type, "target_id": item.target_id,
                "instruction": item.instruction, "status": item.status} for item in correction_items],
            "legacy_warning": None if template.mapping_basis == "PRD_SECTION_11" and not high_gaps else {
                "title": "Legacy or incomplete form mapping",
                "message": f"This submission remains bound to {template.form_code} v{template.version}. It is missing {len(high_gaps)} blocker/high Section 11 requirement(s) and will not be remapped to a newer version.",
                "missing_requirement_count": len(high_gaps),
            },
        })


class SectionValuesView(APIView):
    def get_permissions(self):
        if self.request.method == "PUT":
            return [IsProviderDataEntry()]
        return [IsAuthenticated()]

    def get(self, request, pk, section_code):
        submission = get_submission_for_user(request.user, pk=pk)
        values = SubmissionValue.objects.filter(
            Q(field__section__section_code=section_code)
            | Q(grid__section__section_code=section_code),
            submission=submission,
        ).select_related("field", "grid", "grid_column")
        return Response(SubmissionValueSerializer(values, many=True).data)

    @transaction.atomic
    def put(self, request, pk, section_code):
        visible = get_submission_for_user(request.user, pk=pk)
        submission = lock_submission(visible.pk)
        if submission.expected.workflow_status not in ("DRAFT", "PROVIDER_CHANGES_REQUESTED", "CORRECTION_REQUESTED"):
            return Response({"detail": "Not editable."}, status=400)
        if submission.expected.workflow_status == "CORRECTION_REQUESTED" and not submission.supersedes_id:
            return Response({"detail": "Official historical versions are immutable. Edit the linked correction version."}, status=409)
        supplied_revision = request.data.get("revision")
        if supplied_revision is not None and int(supplied_revision) != submission.revision:
            return Response({
                "code": "STALE_REVISION",
                "detail": "This section changed after it was opened. Reload before saving.",
                "current_revision": submission.revision,
            }, status=409)

        template = submission.expected.form_template
        section = get_object_or_404(template.sections.all(), section_code=section_code)
        values_payload = request.data.get("values", [])
        if not isinstance(values_payload, list):
            return Response({"detail": "values must be a list."}, status=400)
        correction_items = list(
            CorrectionItem.objects.filter(
                Q(source_submission=submission, stage="PROVIDER_APPROVAL")
                | Q(resolution_submission=submission, stage="NCA_REVIEW"),
                status__in=["OPEN", "ADDRESSED"],
            )
        )
        saved = []
        keep_scalar_ids = set()
        keep_grid_keys = set()
        target_keys = set()
        non_filled = {"NOT_APPLICABLE", "NOT_AVAILABLE", "NOT_REQUIRED"}
        valid_statuses = {choice[0] for choice in SubmissionValue._meta.get_field("value_status").choices}
        for v in values_payload:
            field_id = v.get("field")
            grid_id = v.get("grid")
            if bool(field_id) == bool(grid_id):
                return Response({"detail": "Each value must reference exactly one field or grid."}, status=400)
            if field_id and not section.fields.filter(id=field_id).exists():
                return Response({"detail": "Field does not belong to this form section."}, status=400)
            if grid_id and not section.grids.filter(id=grid_id, columns__id=v.get("grid_column")).exists():
                return Response({"detail": "Grid cell does not belong to this form section."}, status=400)
            value_status = v.get("value_status") or ("PROVIDED" if str(v.get("value", "")).strip() else "MISSING")
            if value_status not in valid_statuses or value_status == "SYSTEM_CALCULATED":
                return Response({"detail": "Invalid value status."}, status=400)
            value = "" if value_status in non_filled else str(v.get("value", ""))
            explanation = str(v.get("explanation", ""))
            if grid_id and not str(v.get("grid_row_id", "")).strip():
                return Response({"detail": "Every grid cell requires a row identifier."}, status=400)
            if correction_items:
                target = str(field_id or f"{grid_id}:{v.get('grid_row_id','')}:{v.get('grid_column','')}")
                allowed = any(
                    item.target_type == "SUBMISSION"
                    or (item.target_type == "SECTION" and item.target_id == section_code)
                    or (item.target_type == "FIELD" and item.target_id == str(field_id))
                    or (item.target_type == "GRID_CELL" and item.target_id == target)
                    for item in correction_items
                )
                if not allowed: return Response({"detail": "This value is locked because it was not included in the correction request."}, status=403)
            if field_id:
                keep_scalar_ids.add(int(field_id)); target_keys.add(str(field_id))
            else:
                key = (int(grid_id), str(v.get("grid_row_id", "")), int(v.get("grid_column")))
                keep_grid_keys.add(key); target_keys.add(f"{key[0]}:{key[1]}:{key[2]}")
            obj, _ = SubmissionValue.objects.update_or_create(
                submission=submission,
                field_id=field_id,
                grid_id=grid_id,
                grid_row_id=v.get("grid_row_id", ""),
                grid_column_id=v.get("grid_column"),
                defaults={
                    "value": value,
                    "value_status": value_status,
                    "explanation": explanation,
                    "updated_by": request.user,
                },
            )
            saved.append(obj)

        # Authoritative section snapshot: omitted editable values are removed.
        existing = SubmissionValue.objects.filter(
            Q(field__section=section) | Q(grid__section=section), submission=submission,
        )
        for current in existing:
            key = (current.grid_id, current.grid_row_id, current.grid_column_id)
            keep = current.field_id in keep_scalar_ids if current.field_id else key in keep_grid_keys
            if not keep:
                current.delete()

        if correction_items:
            mark_matching_corrections_addressed(
                submission, section_code=section_code, target_keys=target_keys,
            )
        revision = complete_submission_revision(submission)

        readiness = refresh_submission_completion(submission, section_code)
        write_audit(request, "SECTION_VALUES_SAVED", "Submission", submission.id,
                    after={"section": section_code, "count": len(saved)})
        return Response({"saved": len(saved), "revision": revision, **readiness})


class SubmissionCompletionView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        submission = get_submission_for_user(request.user, pk=pk)
        readiness = refresh_submission_completion(submission)
        open_items = CorrectionItem.objects.filter(
            Q(source_submission=submission, stage="PROVIDER_APPROVAL")
            | Q(resolution_submission=submission, stage="NCA_REVIEW"), status="OPEN"
        )
        if open_items.exists():
            return Response({"detail": "Address every correction item before submitting for approval.",
                "open_correction_item_ids": list(open_items.values_list("id", flat=True))}, status=409)
        return Response(readiness)


class SubmitForApprovalView(APIView):
    permission_classes = [IsProviderDataEntry]

    @transaction.atomic
    def post(self, request, pk):
        visible = get_submission_for_user(request.user, pk=pk)
        submission = lock_submission(visible.pk)
        if submission.expected.workflow_status not in ("DRAFT", "PROVIDER_CHANGES_REQUESTED", "CORRECTION_REQUESTED"):
            return Response(
                {"detail": "Only an editable draft can be sent for provider approval."},
                status=400,
            )
        if submission.expected.workflow_status == "CORRECTION_REQUESTED" and not submission.supersedes_id:
            return Response({"detail": "Official historical versions cannot be resubmitted."}, status=409)
        readiness = refresh_submission_completion(submission)
        if not readiness["can_submit"]:
            return Response({
                "code": "INCOMPLETE_SUBMISSION",
                "detail": "Complete all required items before submitting for approval.",
                **readiness,
            }, status=400)
        open_items = CorrectionItem.objects.filter(
            Q(source_submission=submission, stage="PROVIDER_APPROVAL")
            | Q(resolution_submission=submission, stage="NCA_REVIEW"),
            status="OPEN",
        )
        if open_items.exists():
            return Response({
                "detail": "Address every correction item before resubmitting.",
                "open_correction_item_ids": list(open_items.values_list("id", flat=True)),
            }, status=409)
        prior_status = submission.expected.workflow_status
        is_resubmission = prior_status in {"PROVIDER_CHANGES_REQUESTED", "CORRECTION_REQUESTED"} or submission.supersedes_id is not None
        submission.expected.workflow_status = "PROVIDER_RESUBMITTED" if is_resubmission else "PENDING_APPROVAL"
        submission.expected.save(update_fields=["workflow_status"])
        audit_transition(
            request=request, submission=submission,
            event_type="PROVIDER_RESUBMITTED" if is_resubmission else "SUBMITTED_FOR_APPROVAL",
            message="The corrected form was resubmitted to the Provider Approver." if is_resubmission else "The form was submitted to the Provider Approver.",
            from_status=prior_status, to_status=submission.expected.workflow_status,
            audience="PROVIDER", notify=["PROVIDER_APPROVER"],
        )
        return Response({"detail": "Submitted for provider approval.", "workflow_status": submission.expected.workflow_status})


class OfficialSubmitView(APIView):
    permission_classes = [IsProviderApprover]

    @transaction.atomic
    def post(self, request, pk):
        visible = get_submission_for_user(request.user, pk=pk)
        submission = lock_submission(visible.pk)
        if submission.expected.workflow_status not in ("PENDING_APPROVAL", "PROVIDER_RESUBMITTED"):
            return Response({"detail": "Only a form awaiting provider approval can be officially submitted."}, status=400)
        readiness = refresh_submission_completion(submission)
        if not readiness["can_submit"]:
            return Response({
                "code": "INCOMPLETE_SUBMISSION",
                "detail": "The form changed or failed validation and cannot be approved.",
                **readiness,
            }, status=409)
        prior_status = submission.expected.workflow_status
        was_correction = submission.supersedes_id is not None
        submission.expected.workflow_status = "RESUBMITTED" if was_correction else "SUBMITTED"
        submission.expected.due_state = submission.expected.compute_due_state()
        submission.expected.save(update_fields=["workflow_status", "due_state"])
        submission.submitted_by = request.user
        submission.submitted_at = timezone.now()
        submission.save(update_fields=["submitted_by", "submitted_at"])
        from .receipts import create_receipt
        receipt = create_receipt(submission)
        TransactionalOutbox.objects.get_or_create(topic="submission.official", aggregate_type="Submission",
            aggregate_id=str(submission.id), idempotency_key=f"official-submission:{submission.id}:{submission.version}",
            defaults={"payload": {"submission_id": submission.id, "receipt_reference": receipt.reference}})
        audit_transition(
            request=request, submission=submission, event_type="OFFICIALLY_SUBMITTED",
            message="The Provider Approver officially resubmitted the corrected form to NCA." if was_correction else "The Provider Approver officially submitted the form to NCA.",
            from_status=prior_status, to_status=submission.expected.workflow_status,
            audience="BOTH", notify=["PROVIDER_DATA_ENTRY", "NCA_REVIEWER"],
            metadata={"receipt_reference": receipt.reference},
        )
        return Response({"detail": "Officially submitted to NCA.", "receipt_reference": receipt.reference})


# ── NCA Review ────────────────────────────────────────────────────────────────

class ReviewHistoryView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ReviewActionSerializer

    def get_queryset(self):
        submission = get_submission_for_user(self.request.user, pk=self.kwargs["pk"])
        queryset = ReviewAction.objects.filter(submission=submission).select_related("created_by")
        if self.request.user.is_provider:
            queryset = queryset.filter(is_provider_visible=True)
        return queryset


class StartReviewView(APIView):
    permission_classes = [IsNCAEditor]
    @transaction.atomic
    def post(self, request, pk):
        submission = lock_submission(pk)
        if submission.expected.workflow_status not in ("SUBMITTED", "RESUBMITTED"):
            return Response({"detail": "Only submitted returns can enter review."}, status=409)
        prior_status = submission.expected.workflow_status
        submission.expected.workflow_status = "UNDER_REVIEW"; submission.expected.save(update_fields=["workflow_status"])
        ReviewAction.objects.create(submission=submission, action="ADD_NOTE", comment="NCA review started.", created_by=request.user)
        audit_transition(request=request, submission=submission, event_type="SUBMISSION_REVIEW_STARTED",
            message="NCA regulatory review started.", from_status=prior_status,
            to_status="UNDER_REVIEW", audience="NCA")
        return Response({"detail": "Review started.", "workflow_status": "UNDER_REVIEW"})


class ReviewApproveView(APIView):
    permission_classes = [IsNCAEditor]

    @transaction.atomic
    def post(self, request, pk):
        try: submission = lock_submission(pk)
        except Submission.DoesNotExist: return Response({"detail": "Not found."}, status=404)
        if submission.expected.workflow_status != "UNDER_REVIEW":
            return Response({"detail": "Start the regulatory review before approving this submission."}, status=409)
        readiness = refresh_submission_completion(submission)
        if not readiness["can_submit"]:
            return Response({"detail": "Blocking validation issues must be resolved before approval.", **readiness}, status=409)
        non_filled = submission.values.filter(value_status__in=("NOT_APPLICABLE", "NOT_AVAILABLE", "NOT_REQUIRED"))
        unresolved = non_filled.filter(Q(non_filled_disposition__isnull=True) | Q(non_filled_disposition__decision="REJECTED"))
        if unresolved.exists():
            return Response({"detail": "Every non-filled explanation must have an Accepted disposition before approval.", "unresolved_value_ids": list(unresolved.values_list("id", flat=True))}, status=409)
        open_corrections = submission.resolved_correction_items.filter(status="OPEN")
        if open_corrections.exists():
            return Response({"detail": "Every requested correction must be verified before approval.", "correction_item_ids": list(open_corrections.values_list("id", flat=True))}, status=409)
        rejected_or_pending_kmz = submission.kmz_uploads.filter(requirement__is_required=True).exclude(scan_status="CLEAN", review_status="ACCEPTED")
        if rejected_or_pending_kmz.exists():
            return Response({"detail": "Every required KMZ upload must be clean and accepted before approval."}, status=409)
        from apps.forms_engine.gaps import recalculate_form_gaps
        objective_gaps = [gap for gap in recalculate_form_gaps(submission.expected.form_template, request.user)
            if gap.status != "MATCHED" and gap.requirement.severity in {"BLOCKER", "HIGH"}]
        if objective_gaps:
            return Response({"detail": "The exact form version has unresolved blocker/high Section 11 requirements.",
                "form_gap_ids": [gap.id for gap in objective_gaps]}, status=409)
        prior_status = submission.expected.workflow_status
        submission.expected.workflow_status = "APPROVED"
        submission.expected.refresh_due_state()
        submission.reviewed_by = request.user
        submission.reviewed_at = timezone.now()
        submission.save(update_fields=["reviewed_by", "reviewed_at"])
        submission.expected.save(update_fields=["workflow_status", "due_state"])
        submission.resolved_correction_items.filter(status="ADDRESSED").update(status="VERIFIED")
        ReviewAction.objects.create(
            submission=submission, action="APPROVE",
            comment=request.data.get("comment", ""), created_by=request.user,
        )
        audit_transition(request=request, submission=submission, event_type="SUBMISSION_APPROVED",
            message="NCA approved the official submission.", from_status=prior_status,
            to_status="APPROVED", audience="BOTH", notify=["PROVIDER_DATA_ENTRY", "PROVIDER_APPROVER"])
        return Response({"detail": "Submission approved."})


class ReviewRejectView(APIView):
    permission_classes = [IsNCAEditor]

    @transaction.atomic
    def post(self, request, pk):
        try: submission = lock_submission(pk)
        except Submission.DoesNotExist: return Response({"detail": "Not found."}, status=404)
        if submission.expected.workflow_status != "UNDER_REVIEW":
            return Response({"detail": "Start the regulatory review before rejecting this submission."}, status=409)
        if not request.data.get("comment", "").strip():
            return Response({"detail": "A rejection reason is required."}, status=400)
        comment = request.data.get("comment", "").strip()
        prior_status = submission.expected.workflow_status
        submission.expected.workflow_status = "REJECTED"
        submission.expected.save(update_fields=["workflow_status"])
        submission.reviewed_by = request.user
        submission.reviewed_at = timezone.now()
        submission.save(update_fields=["reviewed_by", "reviewed_at"])
        ReviewAction.objects.create(
            submission=submission, action="REJECT",
            comment=comment, is_provider_visible=True, created_by=request.user,
        )
        audit_transition(request=request, submission=submission, event_type="SUBMISSION_REJECTED",
            message=f"NCA rejected the submission: {comment}", from_status=prior_status,
            to_status="REJECTED", audience="BOTH", notify=["PROVIDER_DATA_ENTRY", "PROVIDER_APPROVER"])
        return Response({"detail": "Submission rejected."})


class ReviewRequestCorrectionView(APIView):
    permission_classes = [IsNCAEditor]

    @transaction.atomic
    def post(self, request, pk):
        try: submission = lock_submission(pk)
        except Submission.DoesNotExist: return Response({"detail": "Not found."}, status=404)
        if submission.expected.workflow_status != "UNDER_REVIEW":
            return Response({"detail": "Start the regulatory review before requesting corrections."}, status=409)
        targets = request.data.get("targets", [])  # [{type, id, comment}]
        comment = request.data.get("comment", "")
        if not comment.strip() and not any(str(t.get("comment", "")).strip() for t in targets):
            return Response({"detail": "A correction instruction is required."}, status=400)

        correction_submission = clone_for_nca_correction(submission)
        prior_status = submission.expected.workflow_status
        submission.expected.workflow_status = "CORRECTION_REQUESTED"
        submission.expected.save(update_fields=["workflow_status"])

        # Mark targeted fields as WAITING_CORRECTION
        for t in targets:
            if t.get("type") == "FIELD" and t.get("id"):
                SubmissionValue.objects.filter(
                    submission=submission, field_id=t["id"]
                ).update(value_status="WAITING_CORRECTION")

        ReviewAction.objects.create(
            submission=submission, action="REQUEST_CORRECTION",
            target_type="SUBMISSION", comment=comment,
            is_provider_visible=True, created_by=request.user,
        )
        for t in targets:
            ReviewAction.objects.create(
                submission=submission, action="REQUEST_CORRECTION",
                target_type=t.get("type", "FIELD"),
                target_id=str(t.get("id", "")),
                comment=t.get("comment", ""),
                is_provider_visible=True, created_by=request.user,
            )
            CorrectionItem.objects.create(source_submission=submission, resolution_submission=correction_submission,
                stage="NCA_REVIEW", target_type=t.get("type", "FIELD"), target_id=str(t.get("id", "")),
                instruction=t.get("comment", "") or comment, created_by=request.user)
        if not targets:
            CorrectionItem.objects.create(source_submission=submission, resolution_submission=correction_submission,
                stage="NCA_REVIEW", target_type="SUBMISSION", target_id=str(submission.id), instruction=comment, created_by=request.user)
        audit_transition(request=request, submission=submission, event_type="CORRECTION_REQUESTED",
            message=f"NCA requested corrections: {comment}", from_status=prior_status,
            to_status="CORRECTION_REQUESTED", audience="BOTH", notify=["PROVIDER_DATA_ENTRY", "PROVIDER_APPROVER"],
            metadata={"targets": len(targets), "correction_submission_id": correction_submission.id})
        return Response({"detail": "Correction requested.", "targets": len(targets), "correction_submission_id": correction_submission.id})


class ReviewAddNoteView(APIView):
    permission_classes = [IsNCAEditor]

    def post(self, request, pk):
        submission = get_submission_for_user(request.user, pk=pk)
        is_provider = request.data.get("provider_visible", False)
        action = "ADD_PROVIDER_COMMENT" if is_provider else "ADD_NOTE"
        ReviewAction.objects.create(
            submission=submission, action=action,
            comment=request.data.get("comment", ""),
            is_provider_visible=is_provider, created_by=request.user,
        )
        return Response({"detail": "Note added."})


# ── Expected Submission Management ───────────────────────────────────────────

class AssignOfficerView(APIView):
    permission_classes = [IsNCAEditor]

    def patch(self, request, pk):
        try:
            expected = ExpectedSubmission.objects.get(pk=pk)
        except ExpectedSubmission.DoesNotExist:
            return Response({"detail": "Not found."}, status=404)

        officer_id = request.data.get("assigned_officer")
        before = expected.assigned_officer_id

        if officer_id is None:
            expected.assigned_officer = None
        else:
            from apps.users.models import User
            try:
                officer = User.objects.get(pk=officer_id, role__in=["NCA_ADMIN", "NCA_OFFICER"])
            except User.DoesNotExist:
                return Response({"detail": "Officer not found or not an NCA user."}, status=400)
            expected.assigned_officer = officer

        expected.save(update_fields=["assigned_officer"])
        write_audit(request, "OFFICER_ASSIGNED", "ExpectedSubmission", pk,
                    before={"assigned_officer": before},
                    after={"assigned_officer": officer_id})
        return Response(ExpectedSubmissionSerializer(expected).data)


class OverrideDueDateView(APIView):
    permission_classes = [IsNCAEditor]

    def patch(self, request, pk):
        try:
            expected = ExpectedSubmission.objects.get(pk=pk)
        except ExpectedSubmission.DoesNotExist:
            return Response({"detail": "Not found."}, status=404)

        proposed = parse_datetime(request.data.get("due_at_override", ""))
        reason = request.data.get("reason", "").strip()
        if not proposed or proposed <= timezone.now() or not reason: return Response({"detail": "A future due_at_override and reason are required."}, status=400)
        change = DeadlineChangeRequest.objects.create(expected_submission=expected, previous_due_at=expected.effective_due_at,
            proposed_due_at=proposed, reason=reason, requested_by=request.user)
        write_audit(request, "DEADLINE_CHANGE_REQUESTED", "DeadlineChangeRequest", change.id, after={"proposed_due_at": proposed.isoformat()})
        return Response({"id": change.id, "status": change.status}, status=201)


class DeadlineDecisionView(APIView):
    permission_classes = [IsNCAEditor]
    def post(self, request, pk):
        change = get_object_or_404(DeadlineChangeRequest, pk=pk, status="PENDING")
        decision = request.data.get("decision")
        if decision not in ("APPROVED", "REJECTED"): return Response({"detail": "decision must be APPROVED or REJECTED."}, status=400)
        change.status=decision; change.decided_by=request.user; change.decided_at=timezone.now(); change.decision_note=request.data.get("note", ""); change.save()
        change.expected_submission.refresh_due_state()
        write_audit(request, f"DEADLINE_CHANGE_{decision}", "DeadlineChangeRequest", change.id)
        return Response({"id": change.id, "status": change.status})


class SubmissionOverrideView(APIView):
    permission_classes = [IsNCAEditor]
    def post(self, request, pk):
        expected = get_object_or_404(ExpectedSubmission, pk=pk)
        blocker_ids = request.data.get("blocker_ids", []); reason=request.data.get("reason", "").strip(); expires=parse_datetime(request.data.get("expires_at", ""))
        if not blocker_ids or not reason or not expires or expires <= timezone.now(): return Response({"detail": "blocker_ids, reason and a future expires_at are required."}, status=400)
        item=SubmissionOverride.objects.create(expected_submission=expected, blocker_ids=blocker_ids, reason=reason,
            evidence_reference=request.data.get("evidence_reference", ""), expires_at=expires, requested_by=request.user)
        write_audit(request, "SUBMISSION_OVERRIDE_REQUESTED", "SubmissionOverride", item.id)
        return Response({"id": item.id, "status": item.status}, status=201)


class SubmissionOverrideDecisionView(APIView):
    permission_classes = [IsNCAEditor]
    def post(self, request, pk):
        item=get_object_or_404(SubmissionOverride, pk=pk, status="PENDING"); decision=request.data.get("decision")
        if decision not in ("APPROVED", "REJECTED"): return Response({"detail":"decision must be APPROVED or REJECTED."}, status=400)
        item.status=decision; item.approved_by=request.user if decision=="APPROVED" else None; item.approved_at=timezone.now(); item.decision_note=request.data.get("note",""); item.save()
        write_audit(request, f"SUBMISSION_OVERRIDE_{decision}", "SubmissionOverride", item.id)
        return Response({"id":item.id,"status":item.status})


class NonFilledDispositionView(APIView):
    permission_classes = [IsNCAEditor]
    def post(self, request, pk, value_id):
        submission=get_object_or_404(Submission, pk=pk); value=get_object_or_404(SubmissionValue, pk=value_id, submission=submission)
        if value.value_status not in ("NOT_APPLICABLE","NOT_AVAILABLE","NOT_REQUIRED"): return Response({"detail":"Only non-filled values require disposition."}, status=400)
        decision=request.data.get("decision")
        if decision not in ("ACCEPTED","REJECTED"): return Response({"detail":"decision must be ACCEPTED or REJECTED."}, status=400)
        disposition,_=NonFilledDisposition.objects.update_or_create(value=value, defaults={"decision":decision,"note":request.data.get("note", ""),"reviewed_by":request.user})
        write_audit(request, f"NON_FILLED_{decision}", "SubmissionValue", value.id)
        return Response({"id":disposition.id,"decision":disposition.decision})


class CorrectionDiffView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, pk):
        current=get_submission_for_user(request.user, pk=pk); previous=current.expected.versions.filter(version__lt=current.version).order_by("-version").first()
        if not previous: return Response([])
        def key(v): return (v.field_id, v.grid_id, v.grid_row_id, v.grid_column_id)
        before={key(v):v for v in previous.values.all()}; after={key(v):v for v in current.values.all()}; rows=[]
        for item_key in sorted(set(before)|set(after), key=str):
            old,new=before.get(item_key),after.get(item_key)
            if (old.value if old else None)!=(new.value if new else None) or (old.value_status if old else None)!=(new.value_status if new else None):
                rows.append({"target":item_key,"before_value":old.value if old else None,"after_value":new.value if new else None,
                    "before_status":old.value_status if old else None,"after_status":new.value_status if new else None})
        return Response(rows)


class ReceiptDownloadView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, pk):
        submission=get_submission_for_user(request.user, pk=pk)
        if not hasattr(submission,"receipt"): return Response({"detail":"Receipt not available."}, status=404)
        import os
        if not os.path.exists(submission.receipt.private_path): return Response({"detail":"Receipt file is missing; contact support."},status=410)
        write_audit(request,"SUBMISSION_RECEIPT_DOWNLOADED","SubmissionReceipt",submission.receipt.id)
        return FileResponse(open(submission.receipt.private_path,"rb"),as_attachment=True,filename=f"{submission.receipt.reference}.pdf",content_type="application/pdf")


class ReminderPolicyListCreate(generics.ListCreateAPIView):
    permission_classes = [IsNCAEditor]
    serializer_class = None
    def get(self, request, period_id):
        rows=ReminderPolicy.objects.filter(period_id=period_id).order_by("-version")
        return Response([{"id":x.id,"version":x.version,"name":x.name,"rules":x.rules,"status":x.status} for x in rows])
    def post(self, request, period_id):
        period=get_object_or_404(ReportingPeriod, pk=period_id); version=(period.reminder_policies.order_by("-version").values_list("version",flat=True).first() or 0)+1
        rules=request.data.get("rules",[])
        if not isinstance(rules,list) or not rules: return Response({"detail":"At least one reminder rule is required."},status=400)
        for rule in rules:
            if not isinstance(rule,dict) or not isinstance(rule.get("offset_days"),int) or not isinstance(rule.get("recipient_roles",[]),list) or not rule.get("template_version"):
                return Response({"detail":"Each rule requires integer offset_days, recipient_roles and template_version."},status=400)
        row=ReminderPolicy.objects.create(period=period,version=version,name=request.data.get("name",f"Policy v{version}"),rules=rules,prepared_by=request.user)
        return Response({"id":row.id,"version":row.version,"status":row.status},status=201)


class ApproveReminderPolicyView(APIView):
    permission_classes = [IsNCAEditor]
    def post(self, request, pk):
        row=get_object_or_404(ReminderPolicy,pk=pk,status="DRAFT")
        if row.prepared_by_id==request.user.id: return Response({"detail":"Maker/checker approval requires a different Admin."},status=409)
        row.period.reminder_policies.filter(status="APPROVED").update(status="ARCHIVED")
        row.status="APPROVED"; row.approved_by=request.user; row.approved_at=timezone.now(); row.save(update_fields=["status","approved_by","approved_at"])
        write_audit(request,"REMINDER_POLICY_APPROVED","ReminderPolicy",row.id,after={"version":row.version})
        return Response({"id":row.id,"version":row.version,"status":row.status})


class PeriodAssignedTemplatesView(APIView):
    permission_classes = [IsNCAUser]

    def get(self, request, pk):
        period = generics.get_object_or_404(ReportingPeriod, pk=pk)
        from apps.forms_engine.serializers import FormTemplateListSerializer
        return Response(FormTemplateListSerializer(period.applicable_form_templates.all(), many=True).data)


class PeriodAssignedProvidersView(APIView):
    permission_classes = [IsNCAUser]

    def get(self, request, pk):
        period = generics.get_object_or_404(ReportingPeriod, pk=pk)
        from apps.providers.serializers import ProviderProfileListSerializer
        return Response(ProviderProfileListSerializer(period.assigned_providers.all(), many=True).data)


class ProviderRequestCorrectionView(APIView):
    permission_classes = [IsProviderApprover]

    @transaction.atomic
    def post(self, request, pk):
        visible = get_submission_for_user(request.user, pk=pk)
        submission = lock_submission(visible.pk)
        if submission.expected.workflow_status not in ("PENDING_APPROVAL", "PROVIDER_RESUBMITTED"):
            return Response({"detail": "Only a form awaiting provider approval can be returned."}, status=400)
        reason = str(request.data.get("reason") or request.data.get("comment") or "").strip()
        targets = request.data.get("targets", [])
        if not reason:
            return Response({"detail": "A clear correction reason is required."}, status=400)
        if not isinstance(targets, list) or not targets:
            return Response({"detail": "Identify at least one section, field or grid cell to correct."}, status=400)
        valid_types = {"SECTION", "FIELD", "GRID_CELL"}
        for target in targets:
            target_type = target.get("type")
            target_id = str(target.get("id", "")).strip()
            if target_type not in valid_types or not target_id:
                return Response({"detail": "Every correction target requires a valid type and id."}, status=400)
        prior_status = submission.expected.workflow_status
        for target in targets:
            CorrectionItem.objects.create(
                source_submission=submission,
                resolution_submission=submission,
                stage="PROVIDER_APPROVAL",
                target_type=target["type"],
                target_id=str(target["id"]),
                instruction=str(target.get("instruction") or target.get("comment") or reason).strip(),
                created_by=request.user,
            )
        submission.expected.workflow_status = "PROVIDER_CHANGES_REQUESTED"
        submission.expected.save(update_fields=["workflow_status"])
        audit_transition(request=request, submission=submission, event_type="PROVIDER_CHANGES_REQUESTED",
            message=f"The Provider Approver requested corrections: {reason}", from_status=prior_status,
            to_status="PROVIDER_CHANGES_REQUESTED", audience="PROVIDER", notify=["PROVIDER_DATA_ENTRY"],
            metadata={"targets": targets})
        return Response({"detail": "Returned to Data Entry for correction.", "workflow_status": "PROVIDER_CHANGES_REQUESTED"})


class ReturnToDraftView(ProviderRequestCorrectionView):
    """Compatibility wrapper for existing clients; the reason/targets contract is mandatory."""


class SubmissionTimelineView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = SubmissionEventSerializer
    pagination_class = None

    def get_queryset(self):
        submission = get_submission_for_user(self.request.user, pk=self.kwargs["pk"])
        queryset = SubmissionEvent.objects.filter(submission=submission).select_related("actor")
        if self.request.user.is_provider:
            queryset = queryset.filter(audience__in=["PROVIDER", "BOTH"])
        elif self.request.user.role in {"NCA_ADMIN", "NCA_OFFICER"}:
            queryset = queryset.exclude(audience="INTERNAL")
        else:
            return queryset.none()
        return queryset


class SubmissionNotificationListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = SubmissionNotificationSerializer

    def get_queryset(self):
        queryset = SubmissionNotification.objects.filter(recipient=self.request.user).select_related(
            "submission__expected__form_template", "submission__expected__provider", "event"
        )
        if self.request.query_params.get("unread") in {"1", "true", "True"}:
            queryset = queryset.filter(is_read=False)
        return queryset


class SubmissionNotificationReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        notification = get_object_or_404(SubmissionNotification, pk=pk, recipient=request.user)
        mark_notification_read(notification)
        return Response({"id": notification.id, "is_read": True})


class SubmissionNotificationReadAllView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        now = timezone.now()
        count = SubmissionNotification.objects.filter(recipient=request.user, is_read=False).update(is_read=True, read_at=now)
        return Response({"marked_read": count})


class IndustryDashboardExportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.query_params.get("format", "xlsx").lower() != "xlsx":
            return Response({"detail": "Only aggregate XLSX export is available."}, status=400)
        from openpyxl import Workbook
        from .industry_dashboard import aggregate_rows, dataset_for_user, load_dashboard_dataset
        dataset = dataset_for_user(load_dashboard_dataset(), request.user)
        workbook = Workbook(write_only=True)
        details = workbook.create_sheet("Export Details")
        details.append(["Dataset", dataset.get("metadata", {}).get("source", "NCA Industry Dashboard")])
        details.append(["Latest period", dataset.get("metadata", {}).get("latestObservedPeriod", "")])
        details.append(["Export scope", "Aggregate chart observations only; no source workbook or provider-level rows."])
        data_sheet = workbook.create_sheet("Aggregate Data")
        headers = ["dashboard", "chart", "unit", "period", "series_kind", "series", "value"]
        data_sheet.append(headers)
        count = 0
        for row in aggregate_rows(dataset):
            data_sheet.append([row[header] for header in headers]); count += 1
        import io, hashlib
        output = io.BytesIO(); workbook.save(output); content = output.getvalue(); digest = hashlib.sha256(content).hexdigest()
        record_audit(user=request.user, action="INDUSTRY_DASHBOARD_AGGREGATE_EXPORTED",
            entity_type="IndustryDashboard", entity_id=digest,
            after={"rows": count, "sha256": digest}, ip_address=request.META.get("REMOTE_ADDR"))
        response = HttpResponse(content, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        response["Content-Disposition"] = 'attachment; filename="nca_industry_dashboard_aggregate.xlsx"'
        response["X-Content-Type-Options"] = "nosniff"
        return response


class IndustryDashboardDataView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from .industry_dashboard import dataset_for_user, load_dashboard_dataset
        response = Response(dataset_for_user(load_dashboard_dataset(), request.user))
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        return response
