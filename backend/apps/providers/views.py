from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from apps.users.permissions import IsNCAUser, IsSystemAdmin, IsNCAOrReadOnly
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
    filterset_fields = ["category", "status"]
    search_fields = ["registered_name", "trade_name", "licence_number", "primary_email"]
    ordering_fields = ["registered_name", "category", "status", "created_at"]
    ordering = ["registered_name"]

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsSystemAdmin()]
        return [IsAuthenticated()]

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
    permission_classes = [IsSystemAdmin]
    queryset = ProviderProfile.objects.prefetch_related("contacts").all()
    serializer_class = ProviderProfileSerializer
    http_method_names = ["get", "patch", "head", "options"]


class ProviderContactListView(generics.ListCreateAPIView):
    """
    GET  — any authenticated user.
    POST — NCA staff only.
    """
    serializer_class = ProviderContactSerializer

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsSystemAdmin()]
        return [IsAuthenticated()]

    def get_queryset(self):
        return ProviderContact.objects.filter(provider_id=self.kwargs["pk"])

    def perform_create(self, serializer):
        provider = generics.get_object_or_404(ProviderProfile, pk=self.kwargs["pk"])
        serializer.save(provider=provider)


class ProviderContactDetailView(generics.RetrieveUpdateAPIView):
    """
    GET   — any authenticated user.
    PATCH — NCA staff only.
    """
    permission_classes = [IsSystemAdmin]
    serializer_class = ProviderContactSerializer
    http_method_names = ["get", "patch", "head", "options"]

    def get_queryset(self):
        return ProviderContact.objects.filter(provider_id=self.kwargs["pk"])

    def get_object(self):
        return generics.get_object_or_404(
            ProviderContact, pk=self.kwargs["cid"], provider_id=self.kwargs["pk"]
        )
