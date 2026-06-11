from django.db.models import Count, Q
from django.db.models.functions import TruncMonth
from django.utils import timezone
from datetime import timedelta
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.models import AuditEvent
from .models import (
    ReportingPeriod, ExpectedSubmission, Submission,
    SubmissionValue, ReviewAction
)
from .serializers import (
    ReportingPeriodSerializer, ExpectedSubmissionSerializer,
    SubmissionSerializer, SubmissionValueSerializer, ReviewActionSerializer,
)


def write_audit(request, action, entity_type, entity_id, before=None, after=None):
    AuditEvent.objects.create(
        user=request.user, user_email=request.user.email, role=request.user.role,
        organization=request.user.organization.name if request.user.organization else "",
        action=action, entity_type=entity_type, entity_id=str(entity_id),
        before_value=before, after_value=after,
        ip_address=request.META.get("REMOTE_ADDR"),
    )


# ── Dashboard ────────────────────────────────────────────────────────────────

class DashboardSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = ExpectedSubmission.objects.all()
        if pid := request.query_params.get("period_id"):
            qs = qs.filter(period_id=pid)
        total = qs.count()
        approved = qs.filter(workflow_status="APPROVED").count()
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
        })


class StatusDonutView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = ExpectedSubmission.objects.all()
        if pid := request.query_params.get("period_id"):
            qs = qs.filter(period_id=pid)
        return Response(list(qs.values("workflow_status").annotate(count=Count("id")).order_by("workflow_status")))


class CategoryCompletionView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = ExpectedSubmission.objects.all()
        if pid := request.query_params.get("period_id"):
            qs = qs.filter(period_id=pid)
        cats = qs.values("provider__category").annotate(
            total=Count("id"),
            approved=Count("id", filter=Q(workflow_status="APPROVED")),
        )
        return Response([{
            "category": c["provider__category"],
            "completion_pct": round((c["approved"] / (c["total"] or 1)) * 100, 1),
            "total": c["total"], "approved": c["approved"],
        } for c in cats])


class SubmissionTrendView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        cutoff = timezone.now() - timedelta(days=365)
        data = (
            Submission.objects.filter(submitted_at__gte=cutoff, submitted_at__isnull=False)
            .annotate(month=TruncMonth("submitted_at"))
            .values("month")
            .annotate(count=Count("id"))
            .order_by("month")
        )
        return Response(list(data))


class OverdueByFormView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(list(
            ExpectedSubmission.objects.filter(due_state="OVERDUE")
            .values("form_template__form_code", "form_template__name")
            .annotate(count=Count("id")).order_by("-count")
        ))


# ── Periods ──────────────────────────────────────────────────────────────────

class ReportingPeriodListView(generics.ListCreateAPIView):
    serializer_class = ReportingPeriodSerializer
    filterset_fields = ["frequency", "status", "year"]

    def get_queryset(self):
        return ReportingPeriod.objects.annotate(
            expected_count=Count("expected_submissions", distinct=True),
            assigned_provider_count=Count("assigned_providers", distinct=True),
            form_template_count=Count("applicable_form_templates", distinct=True),
        ).order_by("-year", "-month", "name")


class ReportingPeriodDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = ReportingPeriodSerializer

    def get_queryset(self):
        return ReportingPeriod.objects.annotate(
            expected_count=Count("expected_submissions", distinct=True),
            assigned_provider_count=Count("assigned_providers", distinct=True),
            form_template_count=Count("applicable_form_templates", distinct=True),
        ).order_by("-year", "-month", "name")


class ActivatePeriodView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            period = ReportingPeriod.objects.get(pk=pk)
        except ReportingPeriod.DoesNotExist:
            return Response({"detail": "Not found."}, status=404)
        if period.status != "DRAFT":
            return Response({"detail": "Only DRAFT periods can be activated."}, status=400)
        period.activate()
        write_audit(request, "PERIOD_ACTIVATED", "ReportingPeriod", period.id)
        return Response({"detail": "Activated.", "expected_count": period.expected_submissions.count()})


# ── Expected Submissions ──────────────────────────────────────────────────────

class ExpectedSubmissionListView(generics.ListAPIView):
    queryset = ExpectedSubmission.objects.select_related("provider", "form_template", "period", "assigned_officer")
    serializer_class = ExpectedSubmissionSerializer
    filterset_fields = ["workflow_status", "due_state", "form_template", "period", "provider", "assigned_officer", "provider__category"]
    search_fields = ["provider__registered_name", "form_template__form_code"]
    ordering_fields = ["period__due_at", "workflow_status", "due_state"]

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.user.is_provider and self.request.user.organization:
            qs = qs.filter(provider__organization=self.request.user.organization)
        return qs


class ExpectedSubmissionDetailView(generics.RetrieveUpdateAPIView):
    queryset = ExpectedSubmission.objects.all()
    serializer_class = ExpectedSubmissionSerializer


# ── Submissions ───────────────────────────────────────────────────────────────

class StartSubmissionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            expected = ExpectedSubmission.objects.get(pk=pk)
        except ExpectedSubmission.DoesNotExist:
            return Response({"detail": "Not found."}, status=404)
        if expected.workflow_status not in ("NOT_STARTED", "CORRECTION_REQUESTED"):
            return Response({"detail": "Cannot start in current state."}, status=400)
        last = expected.versions.order_by("-version").first()
        version = (last.version + 1) if last else 1
        submission = Submission.objects.create(expected=expected, version=version)
        expected.workflow_status = "DRAFT"
        expected.save(update_fields=["workflow_status"])
        write_audit(request, "SUBMISSION_STARTED", "Submission", submission.id)
        return Response(SubmissionSerializer(submission).data, status=201)


class SubmissionDetailView(generics.RetrieveAPIView):
    queryset = Submission.objects.select_related("expected__provider", "expected__form_template", "expected__period")
    serializer_class = SubmissionSerializer


class SectionValuesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk, section_code):
        try:
            submission = Submission.objects.get(pk=pk)
        except Submission.DoesNotExist:
            return Response({"detail": "Not found."}, status=404)
        values = SubmissionValue.objects.filter(
            submission=submission, field__section__section_code=section_code
        ).select_related("field", "grid", "grid_column")
        return Response(SubmissionValueSerializer(values, many=True).data)

    def put(self, request, pk, section_code):
        try:
            submission = Submission.objects.get(pk=pk)
        except Submission.DoesNotExist:
            return Response({"detail": "Not found."}, status=404)
        if submission.expected.workflow_status not in ("DRAFT", "CORRECTION_REQUESTED"):
            return Response({"detail": "Not editable."}, status=400)

        saved = []
        for v in request.data.get("values", []):
            obj, _ = SubmissionValue.objects.update_or_create(
                submission=submission,
                field_id=v.get("field"),
                grid_id=v.get("grid"),
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

        total_req = sum(
            s.fields.filter(is_required=True).count()
            for s in submission.expected.form_template.sections.all()
        )
        provided = submission.values.filter(value_status__in=["PROVIDED","NOT_APPLICABLE","NOT_AVAILABLE","NOT_REQUIRED","SYSTEM_CALCULATED"]).count()
        pct = round((provided / total_req) * 100, 2) if total_req else 0
        submission.completion_pct = pct
        submission.save(update_fields=["completion_pct"])
        write_audit(request, "SECTION_VALUES_SAVED", "Submission", submission.id,
                    after={"section": section_code, "count": len(saved)})
        return Response({"saved": len(saved), "completion_pct": float(pct)})


class SubmissionCompletionView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            submission = Submission.objects.get(pk=pk)
        except Submission.DoesNotExist:
            return Response({"detail": "Not found."}, status=404)
        sections = []
        for section in submission.expected.form_template.sections.prefetch_related("fields").all():
            required = section.fields.filter(is_required=True).count()
            provided = submission.values.filter(
                field__section=section,
                value_status__in=["PROVIDED","NOT_APPLICABLE","NOT_AVAILABLE","NOT_REQUIRED","SYSTEM_CALCULATED"],
            ).count()
            sections.append({
                "section_code": section.section_code, "title": section.title,
                "required": required, "provided": provided, "complete": provided >= required,
            })
        return Response({"completion_pct": float(submission.completion_pct), "sections": sections})


class SubmitForApprovalView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            submission = Submission.objects.get(pk=pk)
        except Submission.DoesNotExist:
            return Response({"detail": "Not found."}, status=404)
        if submission.expected.workflow_status != "DRAFT":
            return Response({"detail": "Only DRAFT can be submitted for approval."}, status=400)
        submission.expected.workflow_status = "PENDING_APPROVAL"
        submission.expected.save(update_fields=["workflow_status"])
        write_audit(request, "SUBMITTED_FOR_APPROVAL", "Submission", submission.id)
        return Response({"detail": "Submitted for provider approval."})


class OfficialSubmitView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            submission = Submission.objects.get(pk=pk)
        except Submission.DoesNotExist:
            return Response({"detail": "Not found."}, status=404)
        if submission.expected.workflow_status != "PENDING_APPROVAL":
            return Response({"detail": "Only PENDING_APPROVAL can be officially submitted."}, status=400)
        submission.expected.workflow_status = "SUBMITTED"
        submission.expected.refresh_due_state()
        submission.submitted_by = request.user
        submission.submitted_at = timezone.now()
        submission.save(update_fields=["submitted_by", "submitted_at"])
        write_audit(request, "OFFICIALLY_SUBMITTED", "Submission", submission.id)
        return Response({"detail": "Officially submitted to NCA."})


# ── NCA Review ────────────────────────────────────────────────────────────────

class ReviewHistoryView(generics.ListAPIView):
    serializer_class = ReviewActionSerializer

    def get_queryset(self):
        return ReviewAction.objects.filter(submission_id=self.kwargs["pk"]).select_related("created_by")


class ReviewApproveView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            submission = Submission.objects.get(pk=pk)
        except Submission.DoesNotExist:
            return Response({"detail": "Not found."}, status=404)
        submission.expected.workflow_status = "APPROVED"
        submission.expected.refresh_due_state()
        submission.reviewed_by = request.user
        submission.reviewed_at = timezone.now()
        submission.save(update_fields=["reviewed_by", "reviewed_at"])
        submission.expected.save(update_fields=["workflow_status", "due_state"])
        ReviewAction.objects.create(
            submission=submission, action="APPROVE",
            comment=request.data.get("comment", ""), created_by=request.user,
        )
        write_audit(request, "SUBMISSION_APPROVED", "Submission", submission.id)
        return Response({"detail": "Submission approved."})


class ReviewRejectView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            submission = Submission.objects.get(pk=pk)
        except Submission.DoesNotExist:
            return Response({"detail": "Not found."}, status=404)
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
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            submission = Submission.objects.get(pk=pk)
        except Submission.DoesNotExist:
            return Response({"detail": "Not found."}, status=404)
        targets = request.data.get("targets", [])  # [{type, id, comment}]
        comment = request.data.get("comment", "")

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
        write_audit(request, "CORRECTION_REQUESTED", "Submission", submission.id,
                    after={"targets": len(targets)})
        return Response({"detail": "Correction requested.", "targets": len(targets)})


class ReviewAddNoteView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            submission = Submission.objects.get(pk=pk)
        except Submission.DoesNotExist:
            return Response({"detail": "Not found."}, status=404)
        is_provider = request.data.get("provider_visible", False)
        action = "ADD_PROVIDER_COMMENT" if is_provider else "ADD_NOTE"
        ReviewAction.objects.create(
            submission=submission, action=action,
            comment=request.data.get("comment", ""),
            is_provider_visible=is_provider, created_by=request.user,
        )
        return Response({"detail": "Note added."})
