import csv
import io
from datetime import date

from django.db import transaction
from django.http import HttpResponse
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.services import record_audit
from apps.forms_engine.models import FormFamily
from apps.submissions.models import ExpectedSubmission
from apps.users.permissions import IsNCAEditor, IsNCAOperationsOrProvider
from .models import ProviderProfile, ProviderContact, ProviderFormAssignment
from .serializers import (
    ProviderProfileSerializer,
    ProviderProfileListSerializer,
    ProviderContactSerializer,
    ProviderFormAssignmentSerializer,
)


class ProviderListView(generics.ListCreateAPIView):
    """
    GET  — any authenticated user (providers can look up their own org).
    POST — NCA staff only. Providers cannot self-register or add other providers.
    """
    filterset_fields = ["sector", "category", "status"]
    search_fields = ["registered_name", "trade_name", "licence_number", "primary_email"]
    ordering_fields = ["registered_name", "category", "status", "created_at"]
    ordering = ["registered_name"]

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsNCAEditor()]
        return [IsNCAOperationsOrProvider()]

    def get_queryset(self):
        qs = ProviderProfile.objects.prefetch_related("contacts").all()
        # Provider users can only see their own organisation's profile
        user = self.request.user
        if user.is_provider and user.organization:
            qs = qs.filter(organization=user.organization)
        return qs

    def get_serializer_class(self):
        if self.request.method == "GET":
            return ProviderProfileListSerializer
        return ProviderProfileSerializer


class ProviderDetailView(generics.RetrieveUpdateAPIView):
    """
    GET   — any authenticated user (providers scoped to own org above).
    PATCH — NCA staff only.
    """
    serializer_class = ProviderProfileSerializer
    http_method_names = ["get", "patch", "head", "options"]

    def get_permissions(self):
        if self.request.method == "PATCH":
            return [IsNCAEditor()]
        return [IsNCAOperationsOrProvider()]

    def get_queryset(self):
        queryset = ProviderProfile.objects.prefetch_related("contacts").all()
        if self.request.user.is_provider and self.request.user.organization_id:
            queryset = queryset.filter(organization_id=self.request.user.organization_id)
        return queryset


class ProviderContactListView(generics.ListCreateAPIView):
    """
    GET  — any authenticated user.
    POST — NCA staff only.
    """
    serializer_class = ProviderContactSerializer

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsNCAEditor()]
        return [IsNCAOperationsOrProvider()]

    def get_queryset(self):
        providers = ProviderProfile.objects.all()
        if self.request.user.is_provider and self.request.user.organization_id:
            providers = providers.filter(organization_id=self.request.user.organization_id)
        provider = generics.get_object_or_404(providers, pk=self.kwargs["pk"])
        return ProviderContact.objects.filter(provider=provider)

    def perform_create(self, serializer):
        provider = generics.get_object_or_404(ProviderProfile, pk=self.kwargs["pk"])
        serializer.save(provider=provider)


class ProviderContactDetailView(generics.RetrieveUpdateAPIView):
    """
    GET   — any authenticated user.
    PATCH — NCA staff only.
    """
    serializer_class = ProviderContactSerializer
    http_method_names = ["get", "patch", "head", "options"]

    def get_permissions(self):
        if self.request.method == "PATCH":
            return [IsNCAEditor()]
        return [IsNCAOperationsOrProvider()]

    def get_queryset(self):
        providers = ProviderProfile.objects.all()
        if self.request.user.is_provider and self.request.user.organization_id:
            providers = providers.filter(organization_id=self.request.user.organization_id)
        provider = generics.get_object_or_404(providers, pk=self.kwargs["pk"])
        return ProviderContact.objects.filter(provider=provider)

    def get_object(self):
        return generics.get_object_or_404(
            ProviderContact, pk=self.kwargs["cid"], provider_id=self.kwargs["pk"]
        )


class ProviderFormAssignmentListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsNCAEditor]
    serializer_class = ProviderFormAssignmentSerializer
    queryset = ProviderFormAssignment.objects.select_related("provider", "form_family", "confirmed_by")
    filterset_fields = ["provider", "form_family", "obligation"]
    search_fields = ["provider__registered_name", "form_family__code", "source_reference"]

    def perform_create(self, serializer):
        assignment = serializer.save(confirmed_by=self.request.user)
        record_audit(user=self.request.user, action="PROVIDER_FORM_ASSIGNMENT_CONFIRMED", entity_type="ProviderFormAssignment", entity_id=assignment.id,
            after={"provider": str(assignment.provider.provider_id), "form_code": assignment.form_family.code, "obligation": assignment.obligation})


class ProviderFormAssignmentImportTemplateView(APIView):
    permission_classes = [IsNCAEditor]

    def get(self, request):
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="provider-form-assignments-template.csv"'
        response.write("\ufeff")
        writer = csv.writer(response)
        writer.writerow(["provider_id", "form_code", "obligation", "effective_from", "effective_to", "source_reference"])
        return response


class ProviderFormAssignmentImportView(APIView):
    permission_classes = [IsNCAEditor]

    def post(self, request):
        uploaded = request.FILES.get("file")
        if not uploaded:
            return Response({"detail": "Attach a CSV file."}, status=400)
        try:
            text = uploaded.read().decode("utf-8-sig")
        except UnicodeDecodeError:
            return Response({"detail": "CSV must use UTF-8 encoding."}, status=400)
        reader = csv.DictReader(io.StringIO(text))
        required = {"provider_id", "form_code", "obligation", "effective_from", "effective_to", "source_reference"}
        if set(reader.fieldnames or []) != required:
            return Response({"detail": "CSV headers must exactly match the official import template."}, status=400)
        normalized, errors, seen = [], [], set()
        for row_number, row in enumerate(reader, start=2):
            try:
                provider = ProviderProfile.objects.get(provider_id=row["provider_id"].strip())
                family = FormFamily.objects.get(code=row["form_code"].strip())
                obligation = row["obligation"].strip().upper()
                if obligation not in dict(ProviderFormAssignment.OBLIGATIONS):
                    raise ValueError("obligation must be REQUIRED, OPTIONAL or EXEMPT")
                effective_from = date.fromisoformat(row["effective_from"].strip())
                effective_to = date.fromisoformat(row["effective_to"].strip()) if row["effective_to"].strip() else None
                source_reference = row["source_reference"].strip()
                if not source_reference:
                    raise ValueError("source_reference is required")
                key = (provider.id, family.id, effective_from)
                if key in seen:
                    raise ValueError("duplicate provider, form and effective_from in this file")
                seen.add(key)
                payload = {"provider": provider.id, "form_family": family.id, "obligation": obligation,
                    "effective_from": effective_from, "effective_to": effective_to, "source_reference": source_reference}
                serializer = ProviderFormAssignmentSerializer(data=payload)
                serializer.is_valid(raise_exception=True)
                normalized.append((serializer, provider, family, payload))
            except Exception as exc:
                detail = getattr(exc, "detail", None) or str(exc)
                errors.append({"row": row_number, "detail": detail})
        if errors:
            return Response({"valid": False, "rows": len(normalized) + len(errors), "errors": errors}, status=400)
        dry_run = str(request.data.get("dry_run", "true")).lower() not in {"false", "0", "no"}
        if dry_run:
            return Response({"valid": True, "dry_run": True, "rows": len(normalized), "assignments": [
                {"provider_id": str(provider.provider_id), "provider_name": provider.registered_name, "form_code": family.code,
                 "obligation": payload["obligation"], "effective_from": payload["effective_from"], "effective_to": payload["effective_to"],
                 "source_reference": payload["source_reference"]} for _, provider, family, payload in normalized
            ]})
        with transaction.atomic():
            created = [serializer.save(confirmed_by=request.user) for serializer, _, _, _ in normalized]
            record_audit(user=request.user, action="PROVIDER_FORM_ASSIGNMENTS_IMPORTED", entity_type="ProviderFormAssignmentImport", entity_id=uploaded.name,
                after={"count": len(created)})
        return Response({"valid": True, "dry_run": False, "created": len(created)}, status=status.HTTP_201_CREATED)
