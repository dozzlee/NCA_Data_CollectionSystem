from django.db.models import Count, Q
from rest_framework import generics

from .models import ProviderProfile
from .serializers import ProviderProfileSerializer


class ProviderProfileListView(generics.ListAPIView):
    serializer_class = ProviderProfileSerializer
    filterset_fields = ["category", "status"]
    search_fields = ["registered_name", "trade_name", "licence_number", "primary_email"]
    ordering_fields = ["registered_name", "category", "status", "licence_expiry_date"]

    def get_queryset(self):
        return (
            ProviderProfile.objects.select_related("organization")
            .annotate(
                contact_count=Count("contacts", distinct=True),
                expected_count=Count("expected_submissions", distinct=True),
                overdue_count=Count(
                    "expected_submissions",
                    filter=Q(expected_submissions__due_state="OVERDUE"),
                    distinct=True,
                ),
                open_count=Count(
                    "expected_submissions",
                    filter=Q(expected_submissions__due_state__in=["OPEN", "DUE_SOON", "DUE_TODAY"]),
                    distinct=True,
                ),
            )
            .order_by("registered_name")
        )


class ProviderProfileDetailView(generics.RetrieveAPIView):
    serializer_class = ProviderProfileSerializer

    def get_queryset(self):
        return ProviderProfile.objects.select_related("organization").annotate(
            contact_count=Count("contacts", distinct=True),
            expected_count=Count("expected_submissions", distinct=True),
            overdue_count=Count(
                "expected_submissions",
                filter=Q(expected_submissions__due_state="OVERDUE"),
                distinct=True,
            ),
            open_count=Count(
                "expected_submissions",
                filter=Q(expected_submissions__due_state__in=["OPEN", "DUE_SOON", "DUE_TODAY"]),
                distinct=True,
            ),
        )
