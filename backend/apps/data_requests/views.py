import os
from django.db import transaction
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from apps.forms_engine.models import FormTemplate
from apps.providers.models import ProviderProfile
from apps.submissions.models import ReportingPeriod, ExpectedSubmission
from apps.users.permissions import IsDataRequester, IsSystemAdmin
from apps.audit.services import record_audit
from .models import DataRequest, DataRequestNotification
from .serializers import DataRequestSerializer, NotificationSerializer, add_event
from .services import build_manifest
from .tasks import generate_data_request


@api_view(["GET"])
@permission_classes([IsDataRequester])
def catalog(request):
    forms = FormTemplate.objects.filter(status="ACTIVE").prefetch_related("sections__fields", "sections__grids__columns")
    if query := request.query_params.get("search"):
        from django.db.models import Q
        forms = forms.filter(Q(form_code__icontains=query) | Q(name__icontains=query) | Q(instructions__icontains=query))
    for parameter, lookup in (("form", "id"), ("sector", "sector"), ("provider_category", "provider_category"), ("frequency", "frequency")):
        if value := request.query_params.get(parameter): forms = forms.filter(**{lookup: value})
    if period_id := request.query_params.get("period"):
        forms = forms.filter(expectedsubmission__period_id=period_id, expectedsubmission__workflow_status="APPROVED").distinct()
    form_items = []
    for form in forms:
        sections = []
        for section in form.sections.all():
            sections.append({"id": section.id, "code": section.section_code, "title": section.title, "description": section.instructions,
                "fields": [{"id": f.id, "code": f.field_code, "label": f.label, "type": f.field_type, "unit": f.unit, "description": f.help_text, "required": f.is_required} for f in section.fields.all()],
                "grids": [{"id": g.id, "code": g.grid_code, "title": g.title, "description": g.instructions, "row_mode": g.row_mode,
                    "columns": [{"id": c.id, "code": c.column_code, "label": c.label, "type": c.field_type, "unit": c.unit, "description": "", "required": c.is_required} for c in g.columns.all()]} for g in section.grids.all()]})
        period_ids = list(ExpectedSubmission.objects.filter(form_template=form, workflow_status="APPROVED").values_list("period_id", flat=True).distinct())
        form_items.append({"id": form.id, "code": form.form_code, "name": form.name, "description": form.instructions,
            "sector": form.sector, "provider_category": form.provider_category, "frequency": form.frequency, "version": form.version,
            "available_period_ids": period_ids, "sections": sections})
    periods = [{"id": p.id, "name": p.name, "frequency": p.frequency, "year": p.year, "month": p.month} for p in ReportingPeriod.objects.all()]
    providers = [{"id": p.id, "provider_id": str(p.provider_id), "name": p.registered_name, "trade_name": p.trade_name, "sector": p.sector, "category": p.category} for p in ProviderProfile.objects.filter(status="ACTIVE")]
    return Response({"forms": form_items, "periods": periods, "providers": providers,
        "sectors": sorted({f["sector"] for f in form_items} | {p["sector"] for p in providers}),
        "provider_categories": sorted({f["provider_category"] for f in form_items} | {p["category"] for p in providers}),
        "frequencies": sorted({f["frequency"] for f in form_items})})


class RequestListCreate(generics.ListCreateAPIView):
    serializer_class = DataRequestSerializer
    def get_queryset(self):
        qs = DataRequest.objects.select_related("requester", "reviewer", "artifact").prefetch_related("events")
        if self.request.user.role == "NCA_VIEWER": return qs.filter(requester=self.request.user)
        if self.request.user.role == "NCA_ADMIN":
            for key in ("status", "requester", "requester_email", "requesting_division", "requested_format"):
                if self.request.query_params.get(key): qs = qs.filter(**{key: self.request.query_params[key]})
            if value := self.request.query_params.get("expected_delivery_from"): qs=qs.filter(expected_delivery_at__gte=value)
            if value := self.request.query_params.get("expected_delivery_to"): qs=qs.filter(expected_delivery_at__lte=value)
            return qs
        return qs.none()
    def get_permissions(self):
        return [(IsDataRequester if self.request.method == "POST" else (IsSystemAdmin if self.request.user.role == "NCA_ADMIN" else IsDataRequester))()]


class RequestDetail(generics.RetrieveUpdateAPIView):
    serializer_class = DataRequestSerializer
    def get_queryset(self):
        qs = DataRequest.objects.select_related("requester", "reviewer", "artifact").prefetch_related("events")
        return qs if self.request.user.role == "NCA_ADMIN" else qs.filter(requester=self.request.user)
    def get_permissions(self): return [(IsSystemAdmin if self.request.user.role == "NCA_ADMIN" else IsDataRequester)()]
    def patch(self, request, *args, **kwargs):
        item = self.get_object()
        if request.user.role != "NCA_VIEWER" or item.status != "CHANGES_REQUESTED": return Response({"detail": "This request cannot be edited now."}, status=409)
        return super().patch(request, *args, **kwargs)


def admin_item(request, pk):
    return get_object_or_404(DataRequest.objects.select_for_update(), pk=pk)


@api_view(["POST"])
@permission_classes([IsSystemAdmin])
@transaction.atomic
def start_review(request, pk):
    item = admin_item(request, pk)
    if item.status != "SUBMITTED": return Response({"detail": "Only submitted requests can enter review."}, status=409)
    due = request.data.get("expected_delivery_at")
    if not due: return Response({"detail": "Choose an expected delivery date."}, status=400)
    due_value = parse_datetime(due) if isinstance(due, str) else due
    if not due_value or due_value <= timezone.now(): return Response({"detail": "Expected delivery must be a future date."}, status=400)
    old=item.status; item.status="UNDER_REVIEW"; item.reviewer=request.user; item.expected_delivery_at=due_value; item.save()
    add_event(item, request.user, "REVIEW_STARTED", old, item.status, "Review started. We will keep you updated.", {"expected_delivery_at": due_value.isoformat()}, True)
    return Response(DataRequestSerializer(item).data)


@api_view(["POST"])
@permission_classes([IsSystemAdmin])
@transaction.atomic
def adjust_delivery(request, pk):
    item=admin_item(request,pk)
    if item.status != "UNDER_REVIEW": return Response({"detail":"Delivery can only be adjusted during review."},status=409)
    due=parse_datetime(request.data.get("expected_delivery_at", ""))
    if not due or due <= timezone.now(): return Response({"detail":"Expected delivery must be a future date."},status=400)
    old_due=item.expected_delivery_at;item.expected_delivery_at=due;item.save(update_fields=["expected_delivery_at","updated_at"])
    add_event(item,request.user,"DELIVERY_DATE_CHANGED",item.status,item.status,"Expected delivery date changed.",
        {"previous":old_due.isoformat() if old_due else None,"expected_delivery_at":due.isoformat()},True)
    return Response(DataRequestSerializer(item).data)


@transaction.atomic
def decision(request, pk, target, event, require_note=False):
    item = admin_item(request, pk); note = request.data.get("note", "").strip()
    if item.status != "UNDER_REVIEW": return Response({"detail": "This decision is only available during review."}, status=409)
    if require_note and not note: return Response({"detail": "Please provide a reason."}, status=400)
    old=item.status; item.status=target; item.decision_note=note; item.reviewer=request.user
    if target == "APPROVED":
        try: item.approval_manifest=build_manifest(item)
        except ValueError as exc: return Response({"detail": str(exc)}, status=400)
        item.approved_at=timezone.now()
    item.save(); add_event(item, request.user, event, old, target, note or event.replace("_", " ").title(), notify=True)
    if target == "APPROVED": generate_data_request.delay(str(item.id))
    return Response(DataRequestSerializer(DataRequest.objects.get(pk=item.pk)).data)


@api_view(["POST"])
@permission_classes([IsSystemAdmin])
def request_changes(request, pk): return decision(request, pk, "CHANGES_REQUESTED", "CHANGES_REQUESTED", True)
@api_view(["POST"])
@permission_classes([IsSystemAdmin])
def approve(request, pk): return decision(request, pk, "APPROVED", "APPROVED")
@api_view(["POST"])
@permission_classes([IsSystemAdmin])
def reject(request, pk): return decision(request, pk, "REJECTED", "REJECTED", True)


@api_view(["POST"])
@permission_classes([IsDataRequester])
def resubmit(request, pk):
    item=get_object_or_404(DataRequest, pk=pk, requester=request.user)
    if item.status != "CHANGES_REQUESTED": return Response({"detail": "Only requests needing changes can be resubmitted."}, status=409)
    old=item.status; item.status="SUBMITTED"; item.decision_note=""; item.save(); add_event(item, request.user, "RESUBMITTED", old, item.status, "Updated request resubmitted.")
    return Response(DataRequestSerializer(item).data)


@api_view(["POST"])
@permission_classes([IsDataRequester])
def withdraw(request, pk):
    item=get_object_or_404(DataRequest, pk=pk, requester=request.user)
    if item.status not in {"SUBMITTED", "UNDER_REVIEW", "CHANGES_REQUESTED"}: return Response({"detail": "This request can no longer be withdrawn."}, status=409)
    old=item.status; item.status="WITHDRAWN"; item.save(); add_event(item, request.user, "WITHDRAWN", old, item.status, "Request withdrawn.")
    return Response(DataRequestSerializer(item).data)


@api_view(["POST"])
@permission_classes([IsSystemAdmin])
def retry(request, pk):
    item=get_object_or_404(DataRequest, pk=pk)
    if item.status != "GENERATION_FAILED": return Response({"detail": "Only failed files can be retried."}, status=409)
    generate_data_request.delay(str(item.id)); return Response({"detail": "Generation restarted."}, status=202)


@api_view(["GET"])
def download(request, pk):
    item=get_object_or_404(DataRequest.objects.select_related("artifact"), pk=pk)
    if request.user.role != "NCA_ADMIN" and item.requester_id != request.user.id: return Response({"detail": "Not found."}, status=404)
    if item.status != "READY" or not hasattr(item, "artifact") or item.artifact.is_expired: return Response({"detail": "This file is not available."}, status=409)
    if not os.path.exists(item.artifact.private_path): return Response({"detail":"The private artifact is missing; contact support."},status=410)
    add_event(item, request.user, "DOWNLOADED", item.status, item.status, "File downloaded.")
    record_audit(user=request.user,action="DATA_REQUEST_DOWNLOADED",entity_type="DataRequestArtifact",entity_id=item.artifact.id,
        after={"request_id":str(item.id),"sha256":item.artifact.sha256},ip_address=request.META.get("REMOTE_ADDR"))
    return FileResponse(open(item.artifact.private_path, "rb"), as_attachment=True, filename=item.artifact.filename, content_type=item.artifact.mime_type)


@api_view(["GET"])
@permission_classes([IsDataRequester])
def notifications(request):
    qs=DataRequestNotification.objects.filter(recipient=request.user); return Response({"unread_count": qs.filter(read_at__isnull=True).count(), "results": NotificationSerializer(qs, many=True).data})
@api_view(["POST"])
@permission_classes([IsDataRequester])
def mark_notification(request, pk):
    item=get_object_or_404(DataRequestNotification, pk=pk, recipient=request.user); item.read_at=timezone.now(); item.save(update_fields=["read_at"]); return Response(status=204)
@api_view(["POST"])
@permission_classes([IsDataRequester])
def mark_all_notifications(request):
    DataRequestNotification.objects.filter(recipient=request.user, read_at__isnull=True).update(read_at=timezone.now()); return Response(status=204)
