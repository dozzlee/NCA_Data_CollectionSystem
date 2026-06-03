from rest_framework import generics
from .models import FormTemplate, KMZUploadRequirement
from .serializers import FormTemplateListSerializer, FormTemplateDetailSerializer, KMZRequirementSerializer


class FormTemplateListView(generics.ListAPIView):
    queryset = FormTemplate.objects.filter(status="ACTIVE")
    serializer_class = FormTemplateListSerializer
    filterset_fields = ["provider_category", "frequency", "status"]


class FormTemplateDetailView(generics.RetrieveAPIView):
    queryset = FormTemplate.objects.prefetch_related(
        "sections__fields__options",
        "sections__grids__columns",
        "sections__grids__fixed_rows",
    )
    serializer_class = FormTemplateDetailSerializer


class KMZRequirementListView(generics.ListAPIView):
    serializer_class = KMZRequirementSerializer

    def get_queryset(self):
        return KMZUploadRequirement.objects.filter(
            form_template__form_code__in=["DC-DBS05", "DC-SUB03"]
        )
