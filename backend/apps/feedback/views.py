from django.conf import settings
from django.core.mail import send_mail
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import FeedbackItem, SystemIssueTicket


class FeedbackView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = request.data
        item = FeedbackItem.objects.create(
            submitted_by=request.user,
            category=data.get("category", "GENERAL"),
            subject=data.get("subject", ""),
            message=data.get("message", ""),
            page_url=data.get("page_url", ""),
        )
        support_email = getattr(settings, "FEEDBACK_EMAIL", None) or getattr(settings, "SUPPORT_EMAIL", None)
        if support_email:
            send_mail(
                subject=f"[NCA Feedback] {item.subject}",
                message=f"From: {request.user.email} ({request.user.role})\nCategory: {item.category}\n\n{item.message}",
                from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@nca.org.gh"),
                recipient_list=[support_email],
                fail_silently=True,
            )
        return Response({"id": item.id, "detail": "Feedback submitted. Thank you."}, status=201)


class SystemIssueView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = request.data
        ticket = SystemIssueTicket.objects.create(
            reported_by=request.user,
            title=data.get("title", ""),
            description=data.get("description", ""),
            severity=data.get("severity", "MEDIUM"),
            page_url=data.get("page_url", ""),
        )
        support_email = getattr(settings, "SUPPORT_EMAIL", None)
        if support_email:
            send_mail(
                subject=f"[NCA Issue/{ticket.severity}] {ticket.title}",
                message=f"Reported by: {request.user.email}\nSeverity: {ticket.severity}\nPage: {ticket.page_url}\n\n{ticket.description}",
                from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@nca.org.gh"),
                recipient_list=[support_email],
                fail_silently=True,
            )
        return Response({"id": ticket.id, "detail": "Issue reported. The team has been notified."}, status=201)
