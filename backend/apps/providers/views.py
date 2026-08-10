from rest_framework import generics
from apps.users.permissions import IsSystemAdmin, IsNCAOperationsOrProvider
from .models import ProviderProfile, ProviderContact
from .serializers import (
    ProviderProfileSerializer,
    ProviderProfileListSerializer,
    ProviderContactSerializer,
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
            return [IsSystemAdmin()]
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
            return [IsSystemAdmin()]
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
            return [IsSystemAdmin()]
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
            return [IsSystemAdmin()]
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
