from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from .models import FormTemplate, KMZUploadRequirement
from .serializers import FormTemplateListSerializer, FormTemplateDetailSerializer, KMZRequirementSerializer


class FormTemplateListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    queryset = FormTemplate.objects.filter(status="ACTIVE")
    serializer_class = FormTemplateListSerializer
    filterset_fields = ["provider_category", "frequency", "status"]


class FormTemplateDetailView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    queryset = FormTemplate.objects.prefetch_related(
        "sections__fields__options",
        "sections__grids__columns",
        "sections__grids__fixed_rows",
    )
    serializer_class = FormTemplateDetailSerializer


class KMZRequirementListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = KMZRequirementSerializer

    def get_queryset(self):
        return KMZUploadRequirement.objects.filter(
            form_template__form_code__in=["DC-DBS05", "DC-SUB03"]
        )
