from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ProviderProfile, ProviderContact
from .serializers import (
    ProviderProfileSerializer,
    ProviderProfileListSerializer,
    ProviderContactSerializer,
)
from apps.users.permissions import IsNCAAdmin, IsNCAUser


class ProviderListView(generics.ListCreateAPIView):
    filterset_fields = ["category", "status"]
    search_fields = ["registered_name", "trade_name", "licence_number", "primary_email"]
    ordering_fields = ["registered_name", "category", "status", "created_at"]
    ordering = ["registered_name"]

    def get_queryset(self):
        return ProviderProfile.objects.prefetch_related("contacts").all()

    def get_permissions(self):
        return [(IsNCAAdmin if self.request.method == "POST" else IsNCAUser)()]

    def get_serializer_class(self):
        if self.request.method == "GET":
            return ProviderProfileListSerializer
        return ProviderProfileSerializer


class ProviderDetailView(generics.RetrieveUpdateAPIView):
    queryset = ProviderProfile.objects.prefetch_related("contacts").all()
    serializer_class = ProviderProfileSerializer
    http_method_names = ["get", "patch", "head", "options"]

    def get_permissions(self):
        return [(IsNCAAdmin if self.request.method == "PATCH" else IsNCAUser)()]


class ProviderContactListView(generics.ListCreateAPIView):
    serializer_class = ProviderContactSerializer

    def get_queryset(self):
        return ProviderContact.objects.filter(provider_id=self.kwargs["pk"])

    def perform_create(self, serializer):
        provider = generics.get_object_or_404(ProviderProfile, pk=self.kwargs["pk"])
        serializer.save(provider=provider)

    def get_permissions(self):
        return [(IsNCAAdmin if self.request.method == "POST" else IsNCAUser)()]


class ProviderContactDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsNCAAdmin]
    serializer_class = ProviderContactSerializer
    http_method_names = ["get", "patch", "head", "options"]

    def get_queryset(self):
        return ProviderContact.objects.filter(provider_id=self.kwargs["pk"])

    def get_object(self):
        return generics.get_object_or_404(
            ProviderContact, pk=self.kwargs["cid"], provider_id=self.kwargs["pk"]
        )
