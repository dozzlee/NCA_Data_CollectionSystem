from rest_framework import generics, status
from apps.users.permissions import IsNCAUser, IsSystemAdmin, IsNCAOrReadOnly
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    FormTemplate, FormSection, FormField, FormGrid,
    GridColumn, GridRow, SelectOption, KMZUploadRequirement,
)
from .serializers import (
    FormTemplateListSerializer, FormTemplateDetailSerializer,
    FormSectionSerializer, FormFieldSerializer, FormGridSerializer,
    GridColumnSerializer, KMZRequirementSerializer,
)


# ── Form Templates ────────────────────────────────────────────────────────────

class FormTemplateListView(generics.ListCreateAPIView):
    permission_classes = [IsNCAOrReadOnly]
    queryset = FormTemplate.objects.all()
    filterset_fields = ["provider_category", "frequency", "status"]

    def get_serializer_class(self):
        return FormTemplateListSerializer


class FormTemplateDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsNCAOrReadOnly]
    queryset = FormTemplate.objects.prefetch_related(
        "sections__fields__options",
        "sections__grids__columns",
        "sections__grids__fixed_rows",
    )
    http_method_names = ["get", "patch", "head", "options"]

    def get_serializer_class(self):
        if self.request.method == "GET":
            return FormTemplateDetailSerializer
        return FormTemplateListSerializer


# ── Sections ──────────────────────────────────────────────────────────────────

class SectionListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsSystemAdmin]
    serializer_class = FormSectionSerializer

    def get_queryset(self):
        return FormSection.objects.filter(
            form_template_id=self.kwargs["pk"]
        ).prefetch_related("fields__options", "grids__columns", "grids__fixed_rows")

    def perform_create(self, serializer):
        form = generics.get_object_or_404(FormTemplate, pk=self.kwargs["pk"])
        max_order = FormSection.objects.filter(form_template=form).count()
        serializer.save(form_template=form, sort_order=max_order + 1)


class SectionDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsSystemAdmin]
    serializer_class = FormSectionSerializer
    http_method_names = ["get", "patch", "delete", "head", "options"]

    def get_object(self):
        return generics.get_object_or_404(
            FormSection, pk=self.kwargs["sid"], form_template_id=self.kwargs["pk"]
        )


# ── Fields ────────────────────────────────────────────────────────────────────

class FieldListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsSystemAdmin]
    serializer_class = FormFieldSerializer

    def get_queryset(self):
        return FormField.objects.filter(section_id=self.kwargs["sid"])

    def perform_create(self, serializer):
        section = generics.get_object_or_404(FormSection, pk=self.kwargs["sid"])
        max_order = FormField.objects.filter(section=section).count()
        field = serializer.save(section=section, sort_order=max_order + 1)
        if field.field_type in ("select", "boolean") and not field.options.exists():
            SelectOption.objects.bulk_create([
                SelectOption(field=field, value="Yes", label="Yes", sort_order=1),
                SelectOption(field=field, value="No",  label="No",  sort_order=2),
            ])


class FieldDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsSystemAdmin]
    serializer_class = FormFieldSerializer
    http_method_names = ["get", "patch", "delete", "head", "options"]

    def get_object(self):
        return generics.get_object_or_404(FormField, pk=self.kwargs["fid"])


# ── Grids ─────────────────────────────────────────────────────────────────────

class GridListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsSystemAdmin]
    serializer_class = FormGridSerializer

    def get_queryset(self):
        return FormGrid.objects.filter(section_id=self.kwargs["sid"]).prefetch_related("columns", "fixed_rows")

    def perform_create(self, serializer):
        section = generics.get_object_or_404(FormSection, pk=self.kwargs["sid"])
        max_order = FormGrid.objects.filter(section=section).count()
        serializer.save(section=section, sort_order=max_order + 1)


class GridDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsSystemAdmin]
    serializer_class = FormGridSerializer
    http_method_names = ["get", "patch", "delete", "head", "options"]

    def get_object(self):
        return generics.get_object_or_404(FormGrid, pk=self.kwargs["gid"])


class GridColumnCreateView(APIView):
    permission_classes = [IsSystemAdmin]

    def post(self, request, gid):
        grid = generics.get_object_or_404(FormGrid, pk=gid)
        max_order = GridColumn.objects.filter(grid=grid).count()
        serializer = GridColumnSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(grid=grid, sort_order=max_order + 1)
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)


class GridRowCreateView(APIView):
    permission_classes = [IsSystemAdmin]

    def post(self, request, gid):
        grid = generics.get_object_or_404(FormGrid, pk=gid)
        if grid.row_mode != "FIXED":
            return Response({"detail": "Only FIXED grids accept pre-populated rows."}, status=400)
        max_order = GridRow.objects.filter(grid=grid).count()
        row = GridRow.objects.create(
            grid=grid,
            row_label=request.data.get("row_label", ""),
            sort_order=max_order + 1,
        )
        return Response({"id": row.id, "row_label": row.row_label, "sort_order": row.sort_order}, status=201)


# ── KMZ Requirements ──────────────────────────────────────────────────────────

class KMZRequirementListView(generics.ListAPIView):
    serializer_class = KMZRequirementSerializer

    def get_queryset(self):
        return KMZUploadRequirement.objects.filter(
            form_template__form_code__in=["DC-DBS05", "DC-SUB03"]
        )


# ── Period: Assign templates & providers ──────────────────────────────────────

class PeriodAssignTemplatesView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        from apps.submissions.models import ReportingPeriod
        period = generics.get_object_or_404(ReportingPeriod, pk=pk)
        template_ids = request.data.get("template_ids", [])
        period.applicable_form_templates.set(template_ids)
        return Response({"detail": "Form templates updated.", "count": len(template_ids)})


class PeriodAssignProvidersView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        from apps.submissions.models import ReportingPeriod
        period = generics.get_object_or_404(ReportingPeriod, pk=pk)
        provider_ids = request.data.get("provider_ids", [])
        period.assigned_providers.set(provider_ids)
        return Response({"detail": "Providers updated.", "count": len(provider_ids)})
