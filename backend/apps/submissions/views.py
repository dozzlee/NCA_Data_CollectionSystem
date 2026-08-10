from django.db import transaction
from django.db.models import Count, Max, Q
from django.utils import timezone
from datetime import timedelta
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.models import AuditEvent
from apps.users.permissions import (
    IsNCAAdmin, IsNCAUser, IsProviderUser, IsProviderDataEntry, IsProviderApprover,
)
from .models import (
    ReportingPeriod, ExpectedSubmission, Submission,
    SubmissionValue, ReviewAction, EditRequest, Notification,
)
from .serializers import (
    ReportingPeriodSerializer, ExpectedSubmissionSerializer,
    SubmissionSerializer, SubmissionValueSerializer, ReviewActionSerializer,
    EditRequestSerializer, NotificationSerializer,
)
from .services import create_notifications, provider_users, nca_users


def write_audit(request, action, entity_type, entity_id, before=None, after=None):
    AuditEvent.objects.create(
        user=request.user, user_email=request.user.email, role=request.user.role,
        organization=request.user.organization.name if request.user.organization else "",
        action=action, entity_type=entity_type, entity_id=str(entity_id),
        before_value=before, after_value=after,
        ip_address=request.META.get("REMOTE_ADDR"),
    )


def expected_queryset_for(user):
    qs = ExpectedSubmission.objects.select_related(
        "provider__organization", "form_template", "period", "assigned_officer"
    ).prefetch_related("versions__submitted_by")
    if user.is_provider:
        return qs.filter(provider__organization=user.organization)
    return qs


def submission_queryset_for(user):
    qs = Submission.objects.select_related(
        "expected__provider__organization", "expected__form_template",
        "expected__period", "submitted_by", "reviewed_by",
    )
    if user.is_provider:
        return qs.filter(expected__provider__organization=user.organization)
    return qs


# ── Dashboard ────────────────────────────────────────────────────────────────

class DashboardSummaryView(APIView):
    permission_classes = [IsNCAUser]

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
    permission_classes = [IsNCAUser]

    def get(self, request):
        qs = ExpectedSubmission.objects.all()
        if pid := request.query_params.get("period_id"):
            qs = qs.filter(period_id=pid)
        return Response(list(qs.values("workflow_status").annotate(count=Count("id")).order_by("workflow_status")))


class CategoryCompletionView(APIView):
    permission_classes = [IsNCAUser]

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
    permission_classes = [IsNCAUser]

    def get(self, request):
        cutoff = timezone.now() - timedelta(days=365)
        data = (
            Submission.objects.filter(submitted_at__gte=cutoff, submitted_at__isnull=False)
            .extra(select={"month": "DATE_TRUNC('month', submitted_at)"})
            .values("month").annotate(count=Count("id")).order_by("month")
        )
        return Response(list(data))


class OverdueByFormView(APIView):
    permission_classes = [IsNCAUser]

    def get(self, request):
        return Response(list(
            ExpectedSubmission.objects.filter(due_state="OVERDUE")
            .values("form_template__form_code", "form_template__name")
            .annotate(count=Count("id")).order_by("-count")
        ))


# ── Periods ──────────────────────────────────────────────────────────────────

class ReportingPeriodListView(generics.ListCreateAPIView):
    queryset = ReportingPeriod.objects.all()
    serializer_class = ReportingPeriodSerializer
    filterset_fields = ["frequency", "status", "year"]

    def get_permissions(self):
        permission = IsNCAAdmin if self.request.method == "POST" else IsNCAUser
        return [permission()]


class ReportingPeriodDetailView(generics.RetrieveUpdateAPIView):
    queryset = ReportingPeriod.objects.all()
    serializer_class = ReportingPeriodSerializer

    def get_permissions(self):
        permission = IsNCAAdmin if self.request.method in ("PUT", "PATCH") else IsNCAUser
        return [permission()]


class ActivatePeriodView(APIView):
    permission_classes = [IsNCAAdmin]

    def post(self, request, pk):
        try:
            period = ReportingPeriod.objects.get(pk=pk)
        except ReportingPeriod.DoesNotExist:
            return Response({"detail": "Not found."}, status=404)
        if period.status != "DRAFT":
            return Response({"detail": "Only DRAFT periods can be activated."}, status=400)
        period.activate()
        for expected in period.expected_submissions.select_related("provider__organization", "form_template"):
            create_notifications(
                provider_users(expected), "PERIOD_OPEN",
                f"{period.name} is open",
                f"{expected.form_template.name} is ready for your organisation.",
                f"/provider/submissions/{expected.id}",
                f"period-open:{period.id}:{expected.id}",
            )
        write_audit(request, "PERIOD_ACTIVATED", "ReportingPeriod", period.id)
        return Response({"detail": "Activated.", "expected_count": period.expected_submissions.count()})


# ── Expected Submissions ──────────────────────────────────────────────────────

class ExpectedSubmissionListView(generics.ListAPIView):
    queryset = ExpectedSubmission.objects.select_related("provider", "form_template", "period", "assigned_officer")
    serializer_class = ExpectedSubmissionSerializer
    filterset_fields = ["workflow_status", "due_state", "form_template", "period", "provider", "assigned_officer"]
    search_fields = ["provider__registered_name", "form_template__form_code"]
    ordering_fields = ["period__due_at", "workflow_status", "due_state"]

    def get_queryset(self):
        return expected_queryset_for(self.request.user)


class ExpectedSubmissionDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = ExpectedSubmissionSerializer

    def get_queryset(self):
        return expected_queryset_for(self.request.user)

    def get_permissions(self):
        permission = IsNCAUser if self.request.method == "GET" else IsNCAAdmin
        if getattr(self.request.user, "is_provider", False) and self.request.method == "GET":
            permission = IsProviderUser
        return [permission()]


# ── Submissions ───────────────────────────────────────────────────────────────

class StartSubmissionView(APIView):
    permission_classes = [IsProviderDataEntry]

    def post(self, request, pk):
        try:
            expected = expected_queryset_for(request.user).get(pk=pk)
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
    serializer_class = SubmissionSerializer

    def get_queryset(self):
        return submission_queryset_for(self.request.user)


class SectionValuesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk, section_code):
        try:
            submission = submission_queryset_for(request.user).get(pk=pk)
        except Submission.DoesNotExist:
            return Response({"detail": "Not found."}, status=404)
        values = SubmissionValue.objects.filter(
            submission=submission, field__section__section_code=section_code
        ).select_related("field", "grid", "grid_column")
        return Response(SubmissionValueSerializer(values, many=True).data)

    def put(self, request, pk, section_code):
        try:
            submission = submission_queryset_for(request.user).get(pk=pk)
        except Submission.DoesNotExist:
            return Response({"detail": "Not found."}, status=404)
        if submission.expected.workflow_status not in ("DRAFT", "CORRECTION_REQUESTED"):
            return Response({"detail": "Not editable."}, status=400)
        if request.user.role != "PROVIDER_DATA_ENTRY":
            return Response({"detail": "Only Provider Data Entry can edit values."}, status=403)

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
            submission = submission_queryset_for(request.user).get(pk=pk)
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
    permission_classes = [IsProviderDataEntry]

    def post(self, request, pk):
        try:
            submission = submission_queryset_for(request.user).get(pk=pk)
        except Submission.DoesNotExist:
            return Response({"detail": "Not found."}, status=404)
        if submission.expected.workflow_status != "DRAFT":
            return Response({"detail": "Only DRAFT can be submitted for approval."}, status=400)
        submission.expected.workflow_status = "PENDING_APPROVAL"
        submission.expected.save(update_fields=["workflow_status"])
        create_notifications(
            provider_users(submission.expected, ("PROVIDER_APPROVER",)),
            "PENDING_APPROVAL", "Submission awaiting approval",
            f"{submission.expected.form_template.name} is ready for provider approval.",
            f"/provider/approvals/{submission.id}",
            f"pending-approval:{submission.id}",
        )
        write_audit(request, "SUBMITTED_FOR_APPROVAL", "Submission", submission.id)
        return Response({"detail": "Submitted for provider approval."})


class OfficialSubmitView(APIView):
    permission_classes = [IsProviderApprover]

    def post(self, request, pk):
        try:
            submission = submission_queryset_for(request.user).get(pk=pk)
        except Submission.DoesNotExist:
            return Response({"detail": "Not found."}, status=404)
        if submission.expected.workflow_status != "PENDING_APPROVAL":
            return Response({"detail": "Only PENDING_APPROVAL can be officially submitted."}, status=400)
        submission.expected.workflow_status = "RESUBMITTED" if submission.version > 1 else "SUBMITTED"
        submission.expected.refresh_due_state()
        submission.submitted_by = request.user
        submission.submitted_at = timezone.now()
        submission.save(update_fields=["submitted_by", "submitted_at"])
        submission.expected.save(update_fields=["workflow_status", "due_state"])
        create_notifications(
            nca_users(), "OFFICIAL_SUBMISSION", "Provider submission received",
            f"{submission.expected.provider.registered_name} submitted {submission.expected.form_template.name}.",
            f"/submissions/{submission.id}/review",
            f"official-submit:{submission.id}",
        )
        write_audit(request, "OFFICIALLY_SUBMITTED", "Submission", submission.id)
        return Response({"detail": "Officially submitted to NCA."})


# ── NCA Review ────────────────────────────────────────────────────────────────

class ReviewHistoryView(generics.ListAPIView):
    serializer_class = ReviewActionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        submission = generics.get_object_or_404(
            submission_queryset_for(self.request.user), pk=self.kwargs["pk"]
        )
        qs = ReviewAction.objects.filter(submission=submission).select_related("created_by")
        if self.request.user.is_provider:
            qs = qs.filter(is_provider_visible=True)
        return qs


class ReviewApproveView(APIView):
    permission_classes = [IsNCAUser]

    def post(self, request, pk):
        try:
            submission = submission_queryset_for(request.user).get(pk=pk)
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
        create_notifications(
            provider_users(submission.expected), "SUBMISSION_APPROVED",
            "Submission approved", f"{submission.expected.form_template.name} was approved by NCA.",
            f"/provider/history?expected={submission.expected_id}",
            f"review-approved:{submission.id}",
        )
        write_audit(request, "SUBMISSION_APPROVED", "Submission", submission.id)
        return Response({"detail": "Submission approved."})


class ReviewRejectView(APIView):
    permission_classes = [IsNCAUser]

    def post(self, request, pk):
        try:
            submission = submission_queryset_for(request.user).get(pk=pk)
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
        create_notifications(
            provider_users(submission.expected), "SUBMISSION_REJECTED",
            "Submission rejected", request.data.get("comment", "NCA rejected the submission."),
            f"/provider/history?expected={submission.expected_id}",
            f"review-rejected:{submission.id}",
        )
        write_audit(request, "SUBMISSION_REJECTED", "Submission", submission.id)
        return Response({"detail": "Submission rejected."})


class ReviewRequestCorrectionView(APIView):
    permission_classes = [IsNCAUser]

    def post(self, request, pk):
        try:
            submission = submission_queryset_for(request.user).get(pk=pk)
        except Submission.DoesNotExist:
            return Response({"detail": "Not found."}, status=404)
        targets = request.data.get("targets", [])  # [{type, id, comment}]
        comment = request.data.get("comment", "")

        # Mark targeted fields as WAITING_CORRECTION
        for t in targets:
            if t.get("type") == "FIELD" and t.get("id"):
                SubmissionValue.objects.filter(
                    submission=submission, field_id=t["id"]
                ).update(value_status="WAITING_CORRECTION")

        next_version = (submission.expected.versions.aggregate(
            max_version=Max("version")
        )["max_version"] or 0) + 1
        corrected = Submission.objects.create(
            expected=submission.expected, version=next_version,
            completion_pct=submission.completion_pct,
        )
        SubmissionValue.objects.bulk_create([
            SubmissionValue(
                submission=corrected, field=value.field, grid=value.grid,
                grid_row_id=value.grid_row_id, grid_column=value.grid_column,
                value=value.value, value_status=value.value_status,
                explanation=value.explanation, updated_by=request.user,
            )
            for value in submission.values.all()
        ])
        submission.expected.workflow_status = "DRAFT"
        submission.expected.save(update_fields=["workflow_status"])

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
        create_notifications(
            provider_users(submission.expected), "CORRECTION_REQUESTED",
            "Correction requested", comment or f"NCA requested corrections to {submission.expected.form_template.name}.",
            f"/provider/submissions/{submission.expected_id}",
            f"correction-requested:{submission.id}:{ReviewAction.objects.filter(submission=submission).count()}",
        )
        return Response({"detail": "Correction requested.", "targets": len(targets)})


class ReviewAddNoteView(APIView):
    permission_classes = [IsNCAUser]

    def post(self, request, pk):
        try:
            submission = submission_queryset_for(request.user).get(pk=pk)
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


# ── Expected Submission Management ───────────────────────────────────────────

class AssignOfficerView(APIView):
    permission_classes = [IsNCAAdmin]

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
    permission_classes = [IsNCAAdmin]

    def patch(self, request, pk):
        try:
            expected = ExpectedSubmission.objects.get(pk=pk)
        except ExpectedSubmission.DoesNotExist:
            return Response({"detail": "Not found."}, status=404)

        new_due = request.data.get("due_at_override")
        before = str(expected.due_at_override) if expected.due_at_override else None
        expected.due_at_override = new_due  # None clears the override
        expected.refresh_due_state()
        expected.save(update_fields=["due_at_override", "due_state"])
        write_audit(request, "DUE_DATE_OVERRIDDEN", "ExpectedSubmission", pk,
                    before={"due_at_override": before},
                    after={"due_at_override": new_due})
        return Response(ExpectedSubmissionSerializer(expected).data)


class ReturnToDraftView(APIView):
    permission_classes = [IsProviderApprover]

    def post(self, request, pk):
        try:
            submission = submission_queryset_for(request.user).get(pk=pk)
        except Submission.DoesNotExist:
            return Response({"detail": "Not found."}, status=404)
        if submission.expected.workflow_status != "PENDING_APPROVAL":
            return Response({"detail": "Only PENDING_APPROVAL can be returned to draft."}, status=400)
        submission.expected.workflow_status = "DRAFT"
        submission.expected.save(update_fields=["workflow_status"])
        reason = request.data.get("reason", "")
        ReviewAction.objects.create(
            submission=submission, action="ADD_PROVIDER_COMMENT",
            target_type="SUBMISSION", comment=reason,
            is_provider_visible=True, created_by=request.user,
        )
        create_notifications(
            provider_users(submission.expected, ("PROVIDER_DATA_ENTRY",)),
            "RETURNED_TO_DRAFT", "Submission returned for changes",
            reason or f"{submission.expected.form_template.name} was returned by your approver.",
            f"/provider/submissions/{submission.expected_id}",
            f"returned-to-draft:{submission.id}:{ReviewAction.objects.filter(submission=submission).count()}",
        )
        write_audit(request, "RETURNED_TO_DRAFT", "Submission", submission.id)
        return Response({"detail": "Returned to draft."})


class ProviderHistoryView(APIView):
    permission_classes = [IsProviderUser]

    def get(self, request):
        expected_items = expected_queryset_for(request.user).prefetch_related(
            "versions__submitted_by", "versions__reviewed_by", "versions__review_actions__created_by",
            "versions__edit_requests__requested_by", "versions__edit_requests__decided_by",
        )
        results = []
        for expected in expected_items:
            versions = []
            for submission in expected.versions.all().order_by("-version"):
                events = [{
                    "type": action.action,
                    "comment": action.comment,
                    "actor": action.created_by.name,
                    "created_at": action.created_at,
                } for action in submission.review_actions.filter(is_provider_visible=True).all()]
                events.extend({
                    "type": f"EDIT_REQUEST_{edit.status}",
                    "comment": edit.decision_note or edit.reason,
                    "actor": (edit.decided_by or edit.requested_by).name,
                    "created_at": edit.decided_at or edit.requested_at,
                } for edit in submission.edit_requests.all())
                versions.append({
                    **SubmissionSerializer(submission).data,
                    "events": sorted(events, key=lambda event: str(event["created_at"]), reverse=True),
                })
            results.append({
                **ExpectedSubmissionSerializer(expected).data,
                "versions": versions,
            })
        return Response(results)


class EditRequestListCreateView(generics.ListCreateAPIView):
    serializer_class = EditRequestSerializer

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsProviderApprover()]
        return [IsAuthenticated()]

    def get_queryset(self):
        qs = EditRequest.objects.select_related(
            "submission__expected__provider__organization",
            "submission__expected__form_template", "submission__expected__period",
            "requested_by", "decided_by",
        )
        if self.request.user.is_provider:
            qs = qs.filter(submission__expected__provider__organization=self.request.user.organization)
        elif not self.request.user.is_nca:
            return qs.none()
        status_filter = self.request.query_params.get("status")
        return qs.filter(status=status_filter) if status_filter else qs

    def perform_create(self, serializer):
        submission = generics.get_object_or_404(
            submission_queryset_for(self.request.user), pk=self.request.data.get("submission")
        )
        allowed = ("SUBMITTED", "UNDER_REVIEW", "RESUBMITTED", "APPROVED", "REJECTED")
        if submission.expected.workflow_status not in allowed:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({"submission": "Only submissions already sent to NCA can be reopened."})
        if EditRequest.objects.filter(submission=submission, status="PENDING").exists():
            from rest_framework.exceptions import ValidationError
            raise ValidationError({"submission": "A pending edit request already exists."})
        edit = serializer.save(requested_by=self.request.user)
        create_notifications(
            nca_users(), "EDIT_REQUEST", "Provider requested an edit",
            f"{submission.expected.provider.registered_name} requested to edit {submission.expected.form_template.name}.",
            f"/edit-requests?request={edit.id}",
            f"edit-request:{edit.id}",
        )
        write_audit(self.request, "EDIT_REQUESTED", "EditRequest", edit.id)


class EditRequestDecisionView(APIView):
    permission_classes = [IsNCAUser]

    @transaction.atomic
    def post(self, request, pk, decision):
        edit = generics.get_object_or_404(
            EditRequest.objects.select_for_update().select_related(
                "submission__expected__provider__organization",
                "submission__expected__form_template",
            ),
            pk=pk, status="PENDING",
        )
        if decision not in ("approve", "deny"):
            return Response({"detail": "Unknown decision."}, status=400)
        edit.decided_by = request.user
        edit.decided_at = timezone.now()
        edit.decision_note = request.data.get("decision_note", "")
        if decision == "approve":
            source = edit.submission
            reopened = Submission.objects.create(
                expected=source.expected,
                version=(source.expected.versions.aggregate(max_version=Max("version"))["max_version"] or 0) + 1,
                completion_pct=source.completion_pct,
            )
            SubmissionValue.objects.bulk_create([
                SubmissionValue(
                    submission=reopened, field=value.field, grid=value.grid,
                    grid_row_id=value.grid_row_id, grid_column=value.grid_column,
                    value=value.value, value_status=value.value_status,
                    explanation=value.explanation, updated_by=request.user,
                )
                for value in source.values.all()
            ])
            source.expected.workflow_status = "DRAFT"
            source.expected.save(update_fields=["workflow_status"])
            edit.status = "APPROVED"
            edit.reopened_submission = reopened
        else:
            edit.status = "DENIED"
        edit.save()
        create_notifications(
            provider_users(edit.submission.expected), f"EDIT_REQUEST_{edit.status}",
            f"Edit request {edit.status.lower()}",
            edit.decision_note or f"NCA {edit.status.lower()} the edit request.",
            f"/provider/requests?request={edit.id}",
            f"edit-decision:{edit.id}:{edit.status}",
        )
        write_audit(request, f"EDIT_REQUEST_{edit.status}", "EditRequest", edit.id)
        return Response(EditRequestSerializer(edit).data)


class NotificationListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = request.user.notifications.all()
        if request.query_params.get("unread") == "true":
            qs = qs.filter(read_at__isnull=True)
        return Response({
            "unread_count": request.user.notifications.filter(read_at__isnull=True).count(),
            "results": NotificationSerializer(qs[:50], many=True).data,
        })


class NotificationReadView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        notification = generics.get_object_or_404(request.user.notifications.all(), pk=pk)
        if not notification.read_at:
            notification.read_at = timezone.now()
            notification.save(update_fields=["read_at"])
        return Response(NotificationSerializer(notification).data)


class NotificationReadAllView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        count = request.user.notifications.filter(read_at__isnull=True).update(read_at=timezone.now())
        return Response({"marked_read": count})
