from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.services import record_audit
from apps.users.models import User
from apps.users.permissions import IsNCAEditor, CanSendProviderCorrespondence
from .models import FeedbackItem, FeedbackNotification, SystemIssueEvent, SystemIssueTicket


def feedback_data(item):
    submitter = item.submitted_by
    return {
        "id": item.id,
        "submitted_by": submitter.id if submitter else None,
        "submitted_by_name": submitter.name if submitter else "Former user",
        "submitted_by_email": submitter.email if submitter else "",
        "organization": submitter.organization.name if submitter and submitter.organization else "",
        "category": item.category,
        "category_label": item.get_category_display(),
        "subject": item.subject,
        "message": item.message,
        "page_url": item.page_url,
        "submitted_at": item.submitted_at,
        "acknowledged": item.acknowledged,
        "acknowledged_at": item.acknowledged_at,
        "acknowledged_by_name": item.acknowledged_by.name if item.acknowledged_by else "",
    }


def ticket_data(ticket):
    return {
        "id": ticket.id, "title": ticket.title, "description": ticket.description,
        "severity": ticket.severity, "status": ticket.status, "page_url": ticket.page_url,
        "reported_by": ticket.reported_by_id, "reporter_name": ticket.reported_by.name if ticket.reported_by else "",
        "reported_at": ticket.reported_at, "assigned_to": ticket.assigned_to_id,
        "assigned_to_name": ticket.assigned_to.name if ticket.assigned_to else "",
        "assigned_team": ticket.assigned_team, "acknowledged_at": ticket.acknowledged_at,
        "sla_due_at": ticket.sla_due_at, "resolved_at": ticket.resolved_at,
        "resolution_note": ticket.resolution_note, "updated_at": ticket.updated_at,
        "history": [{"id": event.id, "event_type": event.event_type, "from_status": event.from_status,
            "to_status": event.to_status, "note": event.note, "actor": event.actor.name if event.actor else "System",
            "created_at": event.created_at} for event in ticket.events.all()],
    }


class FeedbackView(APIView):
    permission_classes = [CanSendProviderCorrespondence]

    def get(self, request):
        queryset = FeedbackItem.objects.select_related(
            "submitted_by__organization", "acknowledged_by"
        )
        if request.user.role not in {"NCA_ADMIN", "NCA_OFFICER"}:
            queryset = queryset.filter(submitted_by=request.user)
        return Response([feedback_data(item) for item in queryset])

    def post(self, request):
        data = request.data
        subject = data.get("subject", "").strip()
        message = data.get("message", "").strip()
        category = data.get("category", "GENERAL")
        if not subject or not message:
            return Response({"detail": "subject and message are required."}, status=400)
        if category not in dict(FeedbackItem.CATEGORY_CHOICES):
            return Response({"detail": "Invalid feedback category."}, status=400)
        item = FeedbackItem.objects.create(submitted_by=request.user, category=category,
            subject=subject, message=message, page_url=data.get("page_url", ""))
        support_email = getattr(settings, "FEEDBACK_EMAIL", None) or getattr(settings, "SUPPORT_EMAIL", None)
        if support_email:
            send_mail(subject=f"[NCA Feedback] {item.subject}", message=f"From: {request.user.email} ({request.user.role})\nCategory: {item.category}\n\n{item.message}",
                from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@nca.org.gh"), recipient_list=[support_email], fail_silently=True)
        record_audit(user=request.user, action="FEEDBACK_SUBMITTED", entity_type="FeedbackItem", entity_id=item.id)
        return Response(feedback_data(item), status=201)


class FeedbackAcknowledgeView(APIView):
    permission_classes = [IsNCAEditor]

    @transaction.atomic
    def post(self, request, pk):
        item = get_object_or_404(
            FeedbackItem.objects.select_for_update().select_related(
                "submitted_by__organization", "acknowledged_by"
            ),
            pk=pk,
        )
        if not item.acknowledged:
            item.acknowledged = True
            item.acknowledged_at = timezone.now()
            item.acknowledged_by = request.user
            item.save(update_fields=["acknowledged", "acknowledged_at", "acknowledged_by"])
            if item.submitted_by_id:
                FeedbackNotification.objects.get_or_create(
                    feedback=item,
                    recipient=item.submitted_by,
                    defaults={
                        "title": "Feedback received by NCA",
                        "message": f'NCA has received your feedback "{item.subject}".',
                    },
                )
            record_audit(
                user=request.user,
                action="FEEDBACK_ACKNOWLEDGED",
                entity_type="FeedbackItem",
                entity_id=item.id,
                before={"acknowledged": False},
                after={"acknowledged": True, "recipient": str(item.submitted_by_id or "")},
                ip_address=request.META.get("REMOTE_ADDR"),
            )
        return Response(feedback_data(item))


class SystemIssueView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = SystemIssueTicket.objects.select_related("reported_by", "assigned_to").prefetch_related("events")
        if request.user.role not in {"NCA_ADMIN", "NCA_OFFICER"}: qs = qs.filter(reported_by=request.user)
        else:
            for key in ("status", "severity", "assigned_team", "assigned_to"):
                if request.query_params.get(key): qs = qs.filter(**{key: request.query_params[key]})
        return Response([ticket_data(ticket) for ticket in qs])

    def post(self, request):
        data = request.data
        if not data.get("title", "").strip() or not data.get("description", "").strip():
            return Response({"detail": "title and description are required."}, status=400)
        ticket = SystemIssueTicket.objects.create(reported_by=request.user, title=data["title"].strip(),
            description=data["description"].strip(), severity=data.get("severity", "MEDIUM"), page_url=data.get("page_url", ""))
        SystemIssueEvent.objects.create(ticket=ticket, event_type="CREATED", to_status="OPEN", note="Issue reported.", actor=request.user)
        record_audit(user=request.user, action="SUPPORT_TICKET_CREATED", entity_type="SystemIssueTicket", entity_id=ticket.id)
        return Response(ticket_data(ticket), status=201)


class SystemIssueDetailView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, pk):
        qs = SystemIssueTicket.objects.select_related("reported_by", "assigned_to").prefetch_related("events")
        if request.user.role not in {"NCA_ADMIN", "NCA_OFFICER"}: qs = qs.filter(reported_by=request.user)
        return Response(ticket_data(get_object_or_404(qs, pk=pk)))


class SystemIssueActionView(APIView):
    permission_classes = [IsNCAEditor]
    def post(self, request, pk):
        ticket = get_object_or_404(SystemIssueTicket.objects.select_related("reported_by", "assigned_to"), pk=pk)
        action = request.data.get("action")
        before = ticket.status
        note = request.data.get("note", "").strip()
        if action == "ASSIGN":
            assignee = get_object_or_404(User, pk=request.data.get("assigned_to"), role__in=["NCA_ADMIN", "NCA_OFFICER"])
            ticket.assigned_to = assignee; ticket.assigned_team = request.data.get("assigned_team", "")
            event_type = "ASSIGNED"
        elif action == "ACKNOWLEDGE":
            ticket.acknowledged_at = timezone.now(); ticket.status = "IN_PROGRESS"; event_type = "ACKNOWLEDGED"
        elif action == "SET_SLA":
            due = parse_datetime(request.data.get("sla_due_at", ""))
            if not due or due <= timezone.now(): return Response({"detail": "A future sla_due_at is required."}, status=400)
            ticket.sla_due_at = due; event_type = "SLA_SET"
        elif action == "UPDATE":
            if not note: return Response({"detail": "An update note is required."}, status=400)
            event_type = "REQUESTER_UPDATE"
        elif action == "RESOLVE":
            if not note: return Response({"detail": "A resolution note is required."}, status=400)
            ticket.status = "RESOLVED"; ticket.resolved_at = timezone.now(); ticket.resolution_note = note; event_type = "RESOLVED"
        elif action == "CLOSE":
            if ticket.status != "RESOLVED": return Response({"detail": "Resolve the ticket before closing it."}, status=409)
            ticket.status = "CLOSED"; event_type = "CLOSED"
        else:
            return Response({"detail": "Unsupported action."}, status=400)
        ticket.save()
        SystemIssueEvent.objects.create(ticket=ticket, event_type=event_type, from_status=before, to_status=ticket.status, note=note, actor=request.user)
        record_audit(user=request.user, action=f"SUPPORT_TICKET_{event_type}", entity_type="SystemIssueTicket", entity_id=ticket.id,
            before={"status": before}, after={"status": ticket.status, "note": note})
        return Response(ticket_data(SystemIssueTicket.objects.prefetch_related("events").get(pk=ticket.pk)))
