from django.db import transaction
from django.utils import timezone
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.services import record_audit
from apps.submissions.access import get_submission_for_user
from apps.submissions.workflow import audit_transition, lock_submission
from apps.users.permissions import IsNCAEditor, IsNCAUser

from .emailing import validate_template
from .models import ComplianceFlag, CommunicationRecord, EmailLog, EmailTemplate, ExternalEmailHandoff
from .serializers import (
    CommunicationRecordSerializer,
    ComplianceFlagSerializer,
    EmailLogSerializer,
    EmailTemplateSerializer,
    ExternalEmailHandoffSerializer,
)


class EmailTemplateListView(generics.ListCreateAPIView):
    queryset = EmailTemplate.objects.all()
    serializer_class = EmailTemplateSerializer

    def get_permissions(self):
        return [(IsNCAEditor if self.request.method == "POST" else IsNCAUser)()]

    def perform_create(self, serializer):
        template_type = serializer.validated_data["template_type"]
        latest = EmailTemplate.objects.filter(template_type=template_type).order_by("-version").values_list("version", flat=True).first() or 0
        serializer.save(version=latest + 1, status="DRAFT")


class ApproveEmailTemplateView(APIView):
    permission_classes = [IsNCAEditor]

    @transaction.atomic
    def post(self, request, pk):
        template = generics.get_object_or_404(EmailTemplate.objects.select_for_update(), pk=pk, status="DRAFT")
        check = validate_template(template)
        if not check["valid"]:
            return Response({"detail": "Template contains unsupported placeholders.", **check}, status=409)
        EmailTemplate.objects.filter(template_type=template.template_type, status="APPROVED").update(status="ARCHIVED")
        template.status = "APPROVED"
        template.approved_by = request.user
        template.approved_at = timezone.now()
        template.placeholders = check["used"]
        template.save(update_fields=["status", "approved_by", "approved_at", "placeholders"])
        record_audit(
            user=request.user,
            action="EMAIL_TEMPLATE_APPROVED",
            entity_type="EmailTemplate",
            entity_id=template.id,
            after={"template_type": template.template_type, "version": template.version},
        )
        return Response(EmailTemplateSerializer(template).data)


class SubmissionCommunicationHistoryView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = CommunicationRecordSerializer
    pagination_class = None

    def get_queryset(self):
        submission = get_submission_for_user(self.request.user, pk=self.kwargs["pk"])
        queryset = CommunicationRecord.objects.filter(expected_submission=submission.expected).select_related(
            "sender", "email_log", "expected_submission__period",
            "expected_submission__form_template", "email_handoff", "submission",
        )
        if self.request.user.is_provider:
            queryset = queryset.exclude(direction="INTERNAL")
        return queryset.order_by("-created_at", "-id")


class SubmissionEmailHandoffView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        submission = get_submission_for_user(request.user, pk=pk)
        event = submission.timeline_events.filter(pk=request.data.get("event_id")).select_related("actor").first()
        if not event:
            return Response({"detail": "The completed workflow event was not found."}, status=404)
        if event.actor_id != request.user.id:
            return Response({"detail": "Only the sender can open the external email draft."}, status=403)
        if event.audience == "INTERNAL":
            return Response({"detail": "Internal-only events do not create an external email handoff."}, status=409)
        from .communications import ensure_email_handoff
        handoff = ensure_email_handoff(submission=submission, event=event, actor=request.user)
        return Response(ExternalEmailHandoffSerializer(handoff).data, status=201)


class EmailHandoffStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk, handoff_id):
        submission = get_submission_for_user(request.user, pk=pk)
        handoff = generics.get_object_or_404(ExternalEmailHandoff, pk=handoff_id, submission=submission)
        if handoff.event.actor_id != request.user.id:
            return Response({"detail": "Only the sender can update the external email draft."}, status=403)
        next_status = str(request.data.get("status") or "").upper()
        if next_status not in {"OPENED", "DEFERRED"}:
            return Response({"detail": "Status must be OPENED or DEFERRED."}, status=400)
        now = timezone.now()
        handoff.status = next_status
        update_fields = ["status"]
        if next_status == "OPENED":
            handoff.opened_by = request.user
            handoff.opened_at = now
            update_fields.extend(["opened_by", "opened_at"])
        else:
            handoff.deferred_at = now
            update_fields.append("deferred_at")
        handoff.save(update_fields=update_fields)
        return Response(ExternalEmailHandoffSerializer(handoff).data)


class SubmissionComplianceFlagListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ComplianceFlagSerializer
    pagination_class = None

    def get_queryset(self):
        submission = get_submission_for_user(self.request.user, pk=self.kwargs["pk"])
        return ComplianceFlag.objects.filter(expected_submission=submission.expected).select_related(
            "provider", "expected_submission__form_template", "expected_submission__period",
        )


class SubmissionComplianceFlagStatusView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def patch(self, request, pk, flag_id):
        submission = get_submission_for_user(request.user, pk=pk)
        flag = generics.get_object_or_404(ComplianceFlag, pk=flag_id, expected_submission=submission.expected)
        if request.user.role not in {"NCA_ADMIN", "NCA_OFFICER"}:
            return Response({"detail": "Only authorized NCA users may update compliance status."}, status=403)
        next_status = str(request.data.get("status") or "").upper()
        if next_status not in dict(ComplianceFlag.STATUS_CHOICES):
            return Response({"detail": "Invalid compliance flag status."}, status=400)
        previous_status = flag.status
        flag.status = next_status
        if next_status == "ACKNOWLEDGED":
            flag.acknowledged_at = timezone.now()
        elif next_status == "RESOLVED":
            flag.resolved_at = timezone.now()
        flag.save()
        locked = lock_submission(submission.id)
        event_type = "COMPLIANCE_FLAG_RESOLVED" if next_status == "RESOLVED" else "COMPLIANCE_FLAG_UPDATED"
        event = audit_transition(
            request=request,
            submission=locked,
            event_type=event_type,
            message=f"Compliance flag {flag.get_flag_type_display()} changed from {previous_status} to {next_status}.",
            from_status=locked.expected.workflow_status,
            to_status=locked.expected.workflow_status,
            audience="BOTH",
            notify=["PROVIDER_APPROVER"],
            metadata={"compliance_flag_id": flag.id, "previous_flag_status": previous_status, "flag_status": next_status},
        )
        payload = ComplianceFlagSerializer(flag).data
        payload.update({"event_id": event.id, "internal_notification_created": event.notifications.exists()})
        return Response(payload)


class LegacyEmailHistoryView(generics.ListAPIView):
    permission_classes = [IsNCAUser]
    serializer_class = EmailLogSerializer
    queryset = EmailLog.objects.select_related("provider", "period", "generated_by").order_by("-generated_at")


class SubmissionCorrespondenceView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, pk):
        authorized = get_submission_for_user(request.user, pk=pk)
        if request.user.role not in {"PROVIDER_APPROVER", "NCA_ADMIN", "NCA_OFFICER"}:
            return Response({"detail": "Only Provider Approvers and privileged NCA users may start correspondence."}, status=403)
        message = str(request.data.get("message") or "").strip()
        if not message:
            return Response({"detail": "A correspondence message is required."}, status=400)
        submission = lock_submission(authorized.id)
        current = submission.expected.workflow_status
        notify = ["NCA_REVIEWER"] if request.user.role == "PROVIDER_APPROVER" else ["PROVIDER_APPROVER"]
        event = audit_transition(
            request=request,
            submission=submission,
            event_type="SUBMISSION_CORRESPONDENCE",
            message=message,
            from_status=current,
            to_status=current,
            audience="BOTH",
            notify=notify,
            metadata={"correspondence": True},
        )
        return Response(
            {"detail": "Correspondence recorded in the portal.", "event_id": event.id,
             "internal_notification_created": event.notifications.exists()},
            status=201,
        )
