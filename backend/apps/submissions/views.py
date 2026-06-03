from django.db.models import Count, Q, Avg
from django.utils import timezone
from datetime import timedelta
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ReportingPeriod, ExpectedSubmission, Submission
from .serializers import ReportingPeriodSerializer, ExpectedSubmissionSerializer, SubmissionSerializer


class DashboardSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = ExpectedSubmission.objects.all()

        # Apply period filter if provided
        period_id = request.query_params.get("period_id")
        if period_id:
            qs = qs.filter(period_id=period_id)

        total = qs.count()
        summary = {
            "total_expected": total,
            "not_started": qs.filter(workflow_status="NOT_STARTED").count(),
            "draft": qs.filter(workflow_status="DRAFT").count(),
            "pending_approval": qs.filter(workflow_status="PENDING_APPROVAL").count(),
            "submitted": qs.filter(workflow_status="SUBMITTED").count(),
            "under_review": qs.filter(workflow_status="UNDER_REVIEW").count(),
            "correction_requested": qs.filter(workflow_status="CORRECTION_REQUESTED").count(),
            "resubmitted": qs.filter(workflow_status="RESUBMITTED").count(),
            "approved": qs.filter(workflow_status="APPROVED").count(),
            "rejected": qs.filter(workflow_status="REJECTED").count(),
            "overdue": qs.filter(due_state="OVERDUE").count(),
            "due_soon": qs.filter(due_state="DUE_SOON").count(),
            "completion_pct": 0,
        }

        if total > 0:
            approved = summary["approved"]
            summary["completion_pct"] = round((approved / total) * 100, 1)

        return Response(summary)


class StatusDonutView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = ExpectedSubmission.objects.all()
        period_id = request.query_params.get("period_id")
        if period_id:
            qs = qs.filter(period_id=period_id)

        data = (
            qs.values("workflow_status")
            .annotate(count=Count("id"))
            .order_by("workflow_status")
        )
        return Response(list(data))


class CategoryCompletionView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = ExpectedSubmission.objects.all()
        period_id = request.query_params.get("period_id")
        if period_id:
            qs = qs.filter(period_id=period_id)

        from django.db.models import FloatField, ExpressionWrapper, Case, When, Value
        categories = qs.values("provider__category").annotate(
            total=Count("id"),
            approved=Count("id", filter=Q(workflow_status="APPROVED")),
        )
        result = []
        for c in categories:
            total = c["total"] or 1
            result.append({
                "category": c["provider__category"],
                "completion_pct": round((c["approved"] / total) * 100, 1),
                "total": c["total"],
                "approved": c["approved"],
            })
        return Response(result)


class SubmissionTrendView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        cutoff = timezone.now() - timedelta(days=365)
        data = (
            Submission.objects
            .filter(submitted_at__gte=cutoff, submitted_at__isnull=False)
            .extra(select={"month": "DATE_TRUNC('month', submitted_at)"})
            .values("month")
            .annotate(count=Count("id"))
            .order_by("month")
        )
        return Response(list(data))


class OverdueByFormView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        data = (
            ExpectedSubmission.objects
            .filter(due_state="OVERDUE")
            .values("form_template__form_code", "form_template__name")
            .annotate(count=Count("id"))
            .order_by("-count")
        )
        return Response(list(data))


class ReportingPeriodListView(generics.ListCreateAPIView):
    queryset = ReportingPeriod.objects.all()
    serializer_class = ReportingPeriodSerializer
    filterset_fields = ["frequency", "status", "year"]


class ReportingPeriodDetailView(generics.RetrieveUpdateAPIView):
    queryset = ReportingPeriod.objects.all()
    serializer_class = ReportingPeriodSerializer


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
        return Response({"detail": "Period activated.", "expected_count": period.expected_submissions.count()})


class ExpectedSubmissionListView(generics.ListAPIView):
    queryset = ExpectedSubmission.objects.select_related(
        "provider", "form_template", "period", "assigned_officer"
    )
    serializer_class = ExpectedSubmissionSerializer
    filterset_fields = ["workflow_status", "due_state", "form_template", "period", "provider", "assigned_officer"]
    search_fields = ["provider__registered_name", "form_template__form_code"]
    ordering_fields = ["period__due_at", "workflow_status", "due_state"]


class ExpectedSubmissionDetailView(generics.RetrieveUpdateAPIView):
    queryset = ExpectedSubmission.objects.all()
    serializer_class = ExpectedSubmissionSerializer


class SubmissionDetailView(generics.RetrieveAPIView):
    queryset = Submission.objects.select_related("expected__provider", "expected__form_template", "expected__period")
    serializer_class = SubmissionSerializer
