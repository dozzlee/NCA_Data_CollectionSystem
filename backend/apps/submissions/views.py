from django.db import transaction
from django.db.models import Count, Q
from django.http import FileResponse
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
    IsNCAUser, IsNCAEditor, IsSystemAdmin,
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
    DeadlineChangeRequest, SubmissionOverride, ReminderPolicy
)
from .serializers import (
    ReportingPeriodSerializer, ExpectedSubmissionSerializer,
    SubmissionSerializer, SubmissionValueSerializer, ReviewActionSerializer,
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
            return [IsSystemAdmin()]
        return [IsNCAUser()]


class ReportingPeriodDetailView(generics.RetrieveUpdateAPIView):
    queryset = ReportingPeriod.objects.all()
    serializer_class = ReportingPeriodSerializer

    def get_permissions(self):
        if self.request.method in ("GET", "HEAD", "OPTIONS"):
            return [IsNCAUser()]
        return [IsSystemAdmin()]


class ActivatePeriodView(APIView):
    permission_classes = [IsSystemAdmin]

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
            return [IsSystemAdmin()]
        return [IsAuthenticated()]

    def get_queryset(self):
        return expected_submissions_for_user(self.request.user)


# ── Submissions ───────────────────────────────────────────────────────────────

class StartSubmissionView(APIView):
    permission_classes = [IsProviderDataEntry]

    def post(self, request, pk):
        expected = get_expected_submission_for_user(request.user, pk=pk)
        if expected.workflow_status not in ("NOT_STARTED", "CORRECTION_REQUESTED"):
            return Response({"detail": "Cannot start in current state."}, status=400)
        last = expected.versions.order_by("-version").first()
        correcting = expected.workflow_status == "CORRECTION_REQUESTED" and last is not None
        version = (last.version + 1) if last else 1
        submission = Submission.objects.create(expected=expected, version=version)
        if correcting:
            SubmissionValue.objects.bulk_create([
                SubmissionValue(submission=submission, field=value.field, grid=value.grid, grid_row_id=value.grid_row_id,
                    grid_column=value.grid_column, value=value.value, value_status=value.value_status,
                    explanation=value.explanation, updated_by=request.user)
                for value in last.values.all()
            ])
        expected.workflow_status = "DRAFT"
        expected.save(update_fields=["workflow_status"])
        write_audit(request, "SUBMISSION_STARTED", "Submission", submission.id)
        return Response(SubmissionSerializer(submission).data, status=201)


class SubmissionDetailView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = SubmissionSerializer

    def get_queryset(self):
        return submissions_for_user(self.request.user).select_related(
            "expected__provider", "expected__form_template", "expected__period"
        )


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

    def put(self, request, pk, section_code):
        submission = get_submission_for_user(request.user, pk=pk)
        if submission.expected.workflow_status not in ("DRAFT", "CORRECTION_REQUESTED"):
            return Response({"detail": "Not editable."}, status=400)

        previous = submission.expected.versions.filter(version__lt=submission.version).order_by("-version").first()
        correction_items = list(previous.correction_items.all()) if previous else []
        saved = []
        for v in request.data.get("values", []):
            field_id = v.get("field")
            grid_id = v.get("grid")
            if bool(field_id) == bool(grid_id):
                return Response({"detail": "Each value must reference exactly one field or grid."}, status=400)
            if field_id and not submission.expected.form_template.sections.filter(
                section_code=section_code, fields__id=field_id
            ).exists():
                return Response({"detail": "Field does not belong to this form section."}, status=400)
            if grid_id and not submission.expected.form_template.sections.filter(
                section_code=section_code,
                grids__id=grid_id,
                grids__columns__id=v.get("grid_column"),
            ).exists():
                return Response({"detail": "Grid cell does not belong to this form section."}, status=400)
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
            obj, _ = SubmissionValue.objects.update_or_create(
                submission=submission,
                field_id=field_id,
                grid_id=grid_id,
                grid_row_id=v.get("grid_row_id", ""),
                grid_column_id=v.get("grid_column"),
                defaults={
                    "value": v.get("value", ""),
                    "value_status": v.get("value_status", "PROVIDED"),
                    "explanation": v.get("explanation", ""),
                    "updated_by": request.user,
                },
            )
            saved.append(obj)
            if correction_items:
                target = str(field_id or f"{grid_id}:{v.get('grid_row_id','')}:{v.get('grid_column','')}")
                for item in correction_items:
                    if (item.target_type == "SUBMISSION" or
                        (item.target_type == "SECTION" and item.target_id == section_code) or
                        (item.target_type == "FIELD" and item.target_id == str(field_id)) or
                        (item.target_type == "GRID_CELL" and item.target_id == target)):
                        if item.status == "OPEN":
                            item.status = "ADDRESSED"; item.save(update_fields=["status"])

        readiness = refresh_submission_completion(submission, section_code)
        write_audit(request, "SECTION_VALUES_SAVED", "Submission", submission.id,
                    after={"section": section_code, "count": len(saved)})
        return Response({"saved": len(saved), **readiness})


class SubmissionCompletionView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        submission = get_submission_for_user(request.user, pk=pk)
        readiness = refresh_submission_completion(submission)
        previous = submission.expected.versions.filter(version__lt=submission.version).order_by("-version").first()
        if previous and previous.correction_items.filter(status="OPEN").exists():
            return Response({"detail": "Address every correction item before submitting for approval.",
                "open_correction_item_ids": list(previous.correction_items.filter(status="OPEN").values_list("id", flat=True))}, status=409)
        return Response(readiness)


class SubmitForApprovalView(APIView):
    permission_classes = [IsProviderDataEntry]

    def post(self, request, pk):
        submission = get_submission_for_user(request.user, pk=pk)
        if submission.expected.workflow_status not in ("DRAFT", "CORRECTION_REQUESTED"):
            return Response(
                {"detail": "Only DRAFT or CORRECTION_REQUESTED submissions can be sent for approval."},
                status=400,
            )
        readiness = refresh_submission_completion(submission)
        if not readiness["can_submit"]:
            return Response({
                "code": "INCOMPLETE_SUBMISSION",
                "detail": "Complete all required items before submitting for approval.",
                **readiness,
            }, status=400)
        submission.expected.workflow_status = "PENDING_APPROVAL"
        submission.expected.save(update_fields=["workflow_status"])
        write_audit(request, "SUBMITTED_FOR_APPROVAL", "Submission", submission.id)
        return Response({"detail": "Submitted for provider approval."})


class OfficialSubmitView(APIView):
    permission_classes = [IsProviderApprover]

    @transaction.atomic
    def post(self, request, pk):
        submission = get_submission_for_user(request.user, pk=pk)
        if submission.expected.workflow_status != "PENDING_APPROVAL":
            return Response({"detail": "Only PENDING_APPROVAL can be officially submitted."}, status=400)
        was_correction = submission.version > 1
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
        write_audit(request, "OFFICIALLY_SUBMITTED", "Submission", submission.id)
        return Response({"detail": "Officially submitted to NCA.", "receipt_reference": receipt.reference})


# ── NCA Review ────────────────────────────────────────────────────────────────

class ReviewHistoryView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ReviewActionSerializer

    def get_queryset(self):
        submission = get_submission_for_user(self.request.user, pk=self.kwargs["pk"])
        return ReviewAction.objects.filter(submission=submission).select_related("created_by")


class StartReviewView(APIView):
    permission_classes = [IsNCAEditor]
    def post(self, request, pk):
        submission = get_object_or_404(Submission, pk=pk)
        if submission.expected.workflow_status not in ("SUBMITTED", "RESUBMITTED"):
            return Response({"detail": "Only submitted returns can enter review."}, status=409)
        submission.expected.workflow_status = "UNDER_REVIEW"; submission.expected.save(update_fields=["workflow_status"])
        ReviewAction.objects.create(submission=submission, action="ADD_NOTE", comment="NCA review started.", created_by=request.user)
        write_audit(request, "SUBMISSION_REVIEW_STARTED", "Submission", submission.id)
        return Response({"detail": "Review started.", "workflow_status": "UNDER_REVIEW"})


class ReviewApproveView(APIView):
    permission_classes = [IsNCAEditor]

    def post(self, request, pk):
        try:
            submission = Submission.objects.get(pk=pk)
        except Submission.DoesNotExist:
            return Response({"detail": "Not found."}, status=404)
        if submission.expected.workflow_status != "UNDER_REVIEW":
            return Response({"detail": "Start the regulatory review before approving this submission."}, status=409)
        readiness = refresh_submission_completion(submission)
        if not readiness["can_submit"]:
            return Response({"detail": "Blocking validation issues must be resolved before approval.", **readiness}, status=409)
        non_filled = submission.values.filter(value_status__in=("NOT_APPLICABLE", "NOT_AVAILABLE", "NOT_REQUIRED"))
        unresolved = non_filled.filter(Q(non_filled_disposition__isnull=True) | Q(non_filled_disposition__decision="REJECTED"))
        if unresolved.exists():
            return Response({"detail": "Every non-filled explanation must have an Accepted disposition before approval.", "unresolved_value_ids": list(unresolved.values_list("id", flat=True))}, status=409)
        submission.expected.workflow_status = "APPROVED"
        submission.expected.refresh_due_state()
        submission.reviewed_by = request.user
        submission.reviewed_at = timezone.now()
        submission.save(update_fields=["reviewed_by", "reviewed_at"])
        submission.expected.save(update_fields=["workflow_status", "due_state"])
        previous = submission.expected.versions.filter(version__lt=submission.version).order_by("-version").first()
        if previous:
            previous.correction_items.filter(status="ADDRESSED").update(status="VERIFIED")
        ReviewAction.objects.create(
            submission=submission, action="APPROVE",
            comment=request.data.get("comment", ""), created_by=request.user,
        )
        write_audit(request, "SUBMISSION_APPROVED", "Submission", submission.id)
        return Response({"detail": "Submission approved."})


class ReviewRejectView(APIView):
    permission_classes = [IsNCAEditor]

    def post(self, request, pk):
        try:
            submission = Submission.objects.get(pk=pk)
        except Submission.DoesNotExist:
            return Response({"detail": "Not found."}, status=404)
        if submission.expected.workflow_status != "UNDER_REVIEW":
            return Response({"detail": "Start the regulatory review before rejecting this submission."}, status=409)
        if not request.data.get("comment", "").strip():
            return Response({"detail": "A rejection reason is required."}, status=400)
        submission.expected.workflow_status = "REJECTED"
        submission.expected.save(update_fields=["workflow_status"])
        submission.reviewed_by = request.user
        submission.reviewed_at = timezone.now()
        submission.save(update_fields=["reviewed_by", "reviewed_at"])
        ReviewAction.objects.create(
            submission=submission, action="REJECT",
            comment=request.data.get("comment", ""), created_by=request.user,
        )
        write_audit(request, "SUBMISSION_REJECTED", "Submission", submission.id)
        return Response({"detail": "Submission rejected."})


class ReviewRequestCorrectionView(APIView):
    permission_classes = [IsNCAEditor]

    def post(self, request, pk):
        try:
            submission = Submission.objects.get(pk=pk)
        except Submission.DoesNotExist:
            return Response({"detail": "Not found."}, status=404)
        if submission.expected.workflow_status != "UNDER_REVIEW":
            return Response({"detail": "Start the regulatory review before requesting corrections."}, status=409)
        targets = request.data.get("targets", [])  # [{type, id, comment}]
        comment = request.data.get("comment", "")
        if not comment.strip() and not any(str(t.get("comment", "")).strip() for t in targets):
            return Response({"detail": "A correction instruction is required."}, status=400)

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
            CorrectionItem.objects.create(source_submission=submission, target_type=t.get("type", "FIELD"),
                target_id=str(t.get("id", "")), instruction=t.get("comment", "") or comment, created_by=request.user)
        if not targets:
            CorrectionItem.objects.create(source_submission=submission, target_type="SUBMISSION", target_id=str(submission.id), instruction=comment, created_by=request.user)
        write_audit(request, "CORRECTION_REQUESTED", "Submission", submission.id,
                    after={"targets": len(targets)})
        return Response({"detail": "Correction requested.", "targets": len(targets)})


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
    permission_classes = [IsSystemAdmin]

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
    permission_classes = [IsSystemAdmin]

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
    permission_classes = [IsSystemAdmin]
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
    permission_classes = [IsSystemAdmin]
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
    permission_classes = [IsSystemAdmin]
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
    permission_classes = [IsSystemAdmin]
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


class ReturnToDraftView(APIView):
    permission_classes = [IsProviderApprover]

    def post(self, request, pk):
        submission = get_submission_for_user(request.user, pk=pk)
        if submission.expected.workflow_status != "PENDING_APPROVAL":
            return Response({"detail": "Only PENDING_APPROVAL can be returned to draft."}, status=400)
        submission.expected.workflow_status = "DRAFT"
        submission.expected.save(update_fields=["workflow_status"])
        write_audit(request, "RETURNED_TO_DRAFT", "Submission", submission.id)
        return Response({"detail": "Returned to draft."})
