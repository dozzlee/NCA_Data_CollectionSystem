from django.utils import timezone
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from apps.users.permissions import IsNCAUser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.submissions.models import ExpectedSubmission
from .models import ComplianceFlag, EmailTemplate, EmailLog, FlagCorrespondence
from .serializers import ComplianceFlagSerializer, EmailTemplateSerializer, EmailLogSerializer, FlagCorrespondenceSerializer


class ProviderComplianceFlagListView(generics.ListAPIView):
    """Provider-facing: flags for their own submissions only."""
    permission_classes = [IsAuthenticated]
    serializer_class = ComplianceFlagSerializer

    def get_queryset(self):
        user = self.request.user
        provider = getattr(user, 'organization', None)
        if provider is None:
            return ComplianceFlag.objects.none()
        return ComplianceFlag.objects.filter(
            provider__organization=provider
        ).select_related(
            "provider",
            "expected_submission__form_template",
            "expected_submission__period",
        )


class ComplianceDashboardView(APIView):
    permission_classes = [IsNCAUser]

    def get(self, request):
        overdue = ExpectedSubmission.objects.filter(due_state="OVERDUE").count()
        correction = ExpectedSubmission.objects.filter(workflow_status="CORRECTION_REQUESTED").count()
        not_started = ExpectedSubmission.objects.filter(workflow_status="NOT_STARTED", due_state__in=["OPEN","DUE_SOON","DUE_TODAY","OVERDUE"]).count()
        draft_due = ExpectedSubmission.objects.filter(workflow_status="DRAFT", due_state__in=["DUE_SOON","DUE_TODAY","OVERDUE"]).count()
        pending_emails = EmailLog.objects.filter(status="DRAFT").count()
        return Response({
            "overdue": overdue,
            "correction_requested": correction,
            "not_started_open": not_started,
            "draft_due_soon": draft_due,
            "pending_email_drafts": pending_emails,
            "total_requiring_action": overdue + correction,
        })


class EmailTemplateListView(generics.ListAPIView):
    queryset = EmailTemplate.objects.all()
    serializer_class = EmailTemplateSerializer


class ComplianceFlagListView(generics.ListAPIView):
    permission_classes = [IsNCAUser]
    serializer_class = ComplianceFlagSerializer
    filterset_fields = ["status", "flag_type", "provider"]

    def get_queryset(self):
        return ComplianceFlag.objects.select_related(
            "provider",
            "expected_submission__form_template",
            "expected_submission__period",
        )


class UpdateFlagStatusView(APIView):
    """Update flag status to any valid status."""
    permission_classes = [IsNCAUser]

    def patch(self, request, pk):
        try:
            flag = ComplianceFlag.objects.get(pk=pk)
        except ComplianceFlag.DoesNotExist:
            return Response({"detail": "Not found."}, status=404)

        new_status = request.data.get("status")
        valid_statuses = dict(ComplianceFlag.STATUS_CHOICES)
        if new_status not in valid_statuses:
            return Response({"detail": f"Invalid status. Choose from: {', '.join(valid_statuses.keys())}"}, status=400)

        flag.status = new_status

        if new_status == "ACKNOWLEDGED":
            flag.acknowledged_at = timezone.now()
        elif new_status == "RESOLVED":
            flag.resolved_at = timezone.now()

        flag.save()
        return Response(ComplianceFlagSerializer(flag).data)


class AcknowledgeFlagView(APIView):
    """Deprecated: use UpdateFlagStatusView instead."""
    permission_classes = [IsNCAUser]

    def patch(self, request, pk):
        try:
            flag = ComplianceFlag.objects.get(pk=pk)
        except ComplianceFlag.DoesNotExist:
            return Response({"detail": "Not found."}, status=404)
        flag.status = "ACKNOWLEDGED"
        flag.acknowledged_at = timezone.now()
        flag.save(update_fields=["status", "acknowledged_at"])
        return Response(ComplianceFlagSerializer(flag).data)


class ResolveFlagView(APIView):
    """Deprecated: use UpdateFlagStatusView instead."""
    permission_classes = [IsNCAUser]

    def patch(self, request, pk):
        try:
            flag = ComplianceFlag.objects.get(pk=pk)
        except ComplianceFlag.DoesNotExist:
            return Response({"detail": "Not found."}, status=404)
        flag.status = "RESOLVED"
        flag.resolved_at = timezone.now()
        flag.save(update_fields=["status", "resolved_at"])
        return Response(ComplianceFlagSerializer(flag).data)


class GenerateEmailView(APIView):
    permission_classes = [IsNCAUser]

    def post(self, request):
        template_type = request.data.get("template_type")
        expected_ids = request.data.get("expected_submission_ids", [])

        try:
            template = EmailTemplate.objects.get(template_type=template_type)
        except EmailTemplate.DoesNotExist:
            return Response({"detail": f"No template for type: {template_type}"}, status=400)

        created = []
        for eid in expected_ids:
            try:
                expected = ExpectedSubmission.objects.select_related("provider", "period").get(pk=eid)
            except ExpectedSubmission.DoesNotExist:
                continue

            contacts = expected.provider.contacts.filter(is_active=True, notify_on_reminder=True)
            recipients = [{"email": c.email, "name": c.name} for c in contacts]
            if not recipients:
                recipients = [{"email": expected.provider.primary_email, "name": expected.provider.registered_name}]

            # Simple placeholder substitution
            body = template.body
            subject = template.subject
            replacements = {
                "{{provider_name}}": expected.provider.registered_name,
                "{{form_name}}": expected.form_template.name,
                "{{period_name}}": expected.period.name,
                "{{due_date}}": expected.period.due_at.strftime("%d %B %Y"),
                "{{workflow_status}}": expected.workflow_status,
            }
            for k, v in replacements.items():
                body = body.replace(k, v)
                subject = subject.replace(k, v)

            log = EmailLog.objects.create(
                template=template, subject=subject, body=body,
                recipients=recipients, provider=expected.provider,
                expected_submission=expected, period=expected.period,
                generated_by=request.user, compliance_stage=template_type,
            )
            created.append(log.id)

        return Response({"generated": len(created), "email_ids": created}, status=201)


class EmailLogListView(generics.ListAPIView):
    queryset = EmailLog.objects.select_related("provider", "period", "generated_by").order_by("-generated_at")
    serializer_class = EmailLogSerializer
    filterset_fields = ["status", "provider", "compliance_stage"]


class MarkEmailSentView(APIView):
    permission_classes = [IsNCAUser]

    def patch(self, request, pk):
        try:
            log = EmailLog.objects.get(pk=pk)
        except EmailLog.DoesNotExist:
            return Response({"detail": "Not found."}, status=404)
        log.status = "SENT"
        log.sent_by = request.user
        log.sent_at = timezone.now()
        log.save(update_fields=["status", "sent_by", "sent_at"])
        return Response({"detail": "Marked as sent."})


class FlagCorrespondenceListView(generics.ListCreateAPIView):
    """List correspondence for a specific flag, or add a note."""
    permission_classes = [IsNCAUser]
    serializer_class = FlagCorrespondenceSerializer

    def get_queryset(self):
        flag_id = self.kwargs.get("flag_id")
        return FlagCorrespondence.objects.filter(flag_id=flag_id).select_related("created_by", "email_log")

    def perform_create(self, serializer):
        serializer.save(flag_id=self.kwargs.get("flag_id"), created_by=self.request.user)


class DraftEmailFromFlagView(APIView):
    """Draft an email directly from a flag with a specific template."""
    permission_classes = [IsNCAUser]

    def post(self, request, flag_id):
        try:
            flag = ComplianceFlag.objects.select_related("expected_submission", "expected_submission__provider", "expected_submission__form_template", "expected_submission__period", "provider").get(pk=flag_id)
        except ComplianceFlag.DoesNotExist:
            return Response({"detail": "Flag not found."}, status=404)

        template_type = request.data.get("template_type")
        try:
            template = EmailTemplate.objects.get(template_type=template_type)
        except EmailTemplate.DoesNotExist:
            return Response({"detail": f"No template for type: {template_type}"}, status=400)

        expected = flag.expected_submission
        contacts = expected.provider.contacts.filter(is_active=True, notify_on_reminder=True)
        recipients = [{"email": c.email, "name": c.name} for c in contacts]
        if not recipients:
            recipients = [{"email": expected.provider.primary_email, "name": expected.provider.registered_name}]

        body = template.body
        subject = template.subject
        replacements = {
            "{{provider_name}}": expected.provider.registered_name,
            "{{form_name}}": expected.form_template.name,
            "{{period_name}}": expected.period.name,
            "{{due_date}}": expected.period.due_at.strftime("%d %B %Y"),
            "{{workflow_status}}": expected.workflow_status,
        }
        for k, v in replacements.items():
            body = body.replace(k, v)
            subject = subject.replace(k, v)

        log = EmailLog.objects.create(
            template=template, subject=subject, body=body,
            recipients=recipients, provider=expected.provider,
            expected_submission=expected, period=expected.period,
            generated_by=request.user, compliance_stage=template_type,
        )

        FlagCorrespondence.objects.create(
            flag=flag,
            message_type="EMAIL_SENT",
            subject=subject,
            message=body,
            created_by=request.user,
            email_log=log,
        )

        return Response(EmailLogSerializer(log).data, status=201)
