from rest_framework import generics, status, serializers
from apps.users.permissions import IsNCAUser, IsNCAEditor, IsNCAOrReadOnly
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    FormFamily, FormTemplate, FormSection, FormField, FormGrid,
    GridColumn, GridRow, SelectOption, KMZUploadRequirement, ValidationRule, FormRequirement, FormGapAssessment,
)
from .serializers import (
    FormTemplateListSerializer, FormTemplateDetailSerializer,
    FormSectionSerializer, FormFieldSerializer, FormGridSerializer,
    GridColumnSerializer, GridRowSerializer, SelectOptionSerializer, KMZRequirementSerializer,
    FormFamilySerializer, ValidationRuleSerializer, FormRequirementSerializer, FormGapAssessmentSerializer,
)
from .gaps import recalculate_form_gaps
from django.db import transaction
from django.db import models
from django.utils import timezone
from apps.audit.services import record_audit


def locked(form):
    return form.approval_status == "APPROVED" or form.expectedsubmission_set.exists()


def reject_if_locked(form):
    if locked(form):
        raise serializers.ValidationError("Used form versions are immutable. Clone a new version.")


# ── Form Templates ────────────────────────────────────────────────────────────

class FormTemplateListView(generics.ListCreateAPIView):
    permission_classes = [IsNCAOrReadOnly]
    queryset = FormTemplate.objects.all()
    filterset_fields = ["sector", "provider_category", "frequency", "status"]

    def get_serializer_class(self):
        return FormTemplateListSerializer

    def perform_create(self, serializer):
        serializer.save(prepared_by=self.request.user, status="DRAFT", approval_status="DRAFT")


class FormTemplateDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsNCAOrReadOnly]
    queryset = FormTemplate.objects.prefetch_related(
        "sections__fields__options",
        "sections__grids__columns",
        "sections__grids__fixed_rows",
        "kmz_requirements",
    )
    http_method_names = ["get", "patch", "head", "options"]

    def get_serializer_class(self):
        if self.request.method == "GET":
            return FormTemplateDetailSerializer
        return FormTemplateListSerializer

    def patch(self, request, *args, **kwargs):
        if locked(self.get_object()): return Response({"detail": "Published form versions used by submissions are immutable. Clone a new version."}, status=409)
        return super().patch(request, *args, **kwargs)


class FormFamilyListCreate(generics.ListCreateAPIView):
    permission_classes = [IsNCAEditor]
    queryset = FormFamily.objects.all().order_by("code")
    serializer_class = FormFamilySerializer

    def perform_create(self, serializer):
        code=serializer.validated_data["code"]
        serializer.save(frequency_decision_status="PENDING_DECISION" if code=="DC-DBS05" else "APPROVED",
            canonical_frequency="" if code=="DC-DBS05" else serializer.validated_data.get("canonical_frequency", ""))


class ApproveFrequencyDecisionView(APIView):
    permission_classes = [IsNCAEditor]

    def post(self, request, pk):
        family = generics.get_object_or_404(FormFamily, pk=pk)
        frequency = request.data.get("canonical_frequency")
        reference = request.data.get("frequency_decision_reference", "").strip()
        source_owner = request.data.get("source_owner", "").strip()
        if frequency not in {"MONTHLY", "SEMI_ANNUAL", "ANNUAL"} or not reference or not source_owner:
            return Response({"detail": "canonical_frequency, source_owner and an approved decision reference are required."}, status=400)
        family.canonical_frequency = frequency
        family.frequency_decision_status = "APPROVED"
        family.frequency_decision_reference = reference
        family.source_owner = source_owner
        family.save(update_fields=["canonical_frequency", "frequency_decision_status", "frequency_decision_reference", "source_owner"])
        record_audit(user=request.user, action="FORM_FREQUENCY_DECISION_APPROVED", entity_type="FormFamily", entity_id=family.id, after={"frequency": frequency, "reference": reference})
        return Response(FormFamilySerializer(family).data)


class ValidationRuleListCreate(generics.ListCreateAPIView):
    permission_classes = [IsNCAEditor]
    serializer_class = ValidationRuleSerializer
    def get_queryset(self): return ValidationRule.objects.filter(form_template_id=self.kwargs["pk"])
    def get_serializer_context(self):
        context=super().get_serializer_context();context["form_template"]=generics.get_object_or_404(FormTemplate,pk=self.kwargs["pk"]);return context
    def perform_create(self, serializer):
        form=generics.get_object_or_404(FormTemplate, pk=self.kwargs["pk"])
        if locked(form): raise serializers.ValidationError("Used versions are immutable. Clone a new version.")
        target_field=serializer.validated_data.get("field");target_grid=serializer.validated_data.get("grid");rule_type=serializer.validated_data["rule_type"]
        version=(ValidationRule.objects.filter(form_template=form,field=target_field,grid=target_grid,rule_type=rule_type).order_by("-version").values_list("version",flat=True).first() or 0)+1
        serializer.save(form_template=form,version=version)


class FormRequirementListView(generics.ListAPIView):
    permission_classes = [IsNCAEditor]
    serializer_class = FormRequirementSerializer

    def get_queryset(self):
        return FormRequirement.objects.filter(family_id=self.kwargs["pk"])


class FormGapListCreateView(APIView):
    permission_classes = [IsNCAEditor]

    def get(self, request, pk):
        queryset = FormGapAssessment.objects.filter(form_template_id=pk).select_related("requirement", "owner", "resolved_by")
        if value := request.query_params.get("status"):
            queryset = queryset.filter(status=value)
        if value := request.query_params.get("severity"):
            queryset = queryset.filter(requirement__severity=value)
        return Response(FormGapAssessmentSerializer(queryset, many=True).data)

    def post(self, request, pk):
        form = generics.get_object_or_404(FormTemplate, pk=pk)
        requirement = generics.get_object_or_404(FormRequirement, pk=request.data.get("requirement"), family=form.family)
        assessment, created = FormGapAssessment.objects.update_or_create(
            form_template=form, requirement=requirement,
            defaults={"status": request.data.get("status", "MISSING"), "evidence": request.data.get("evidence", ""),
                "owner_id": request.data.get("owner") or None, "assessed_by": request.user, "assessed_at": timezone.now()},
        )
        record_audit(user=request.user, action="FORM_GAP_RECORDED", entity_type="FormGapAssessment", entity_id=assessment.id,
            after={"status": assessment.status, "requirement": requirement.requirement_key})
        return Response(FormGapAssessmentSerializer(assessment).data, status=201 if created else 200)


class RecalculateFormGapsView(APIView):
    permission_classes = [IsNCAEditor]

    def post(self, request, pk):
        form = generics.get_object_or_404(FormTemplate, pk=pk)
        assessments = recalculate_form_gaps(form, request.user)
        record_audit(user=request.user, action="FORM_GAPS_RECALCULATED", entity_type="FormTemplate", entity_id=form.id,
            after={"assessment_count": len(assessments)})
        return Response(FormGapAssessmentSerializer(assessments, many=True).data)


class ResolveFormGapView(APIView):
    permission_classes = [IsNCAEditor]

    def post(self, request, pk):
        assessment = generics.get_object_or_404(FormGapAssessment.objects.select_related("requirement"), pk=pk)
        note = request.data.get("resolution_note", "").strip()
        if not note:
            return Response({"detail": "Provide resolution evidence."}, status=400)
        assessment.resolution_note=note; assessment.resolved_by=request.user; assessment.resolved_at=timezone.now()
        assessment.save(update_fields=["resolution_note", "resolved_by", "resolved_at"])
        recalculate_form_gaps(assessment.form_template, request.user)
        assessment.refresh_from_db()
        record_audit(user=request.user, action="FORM_GAP_RESOLVED", entity_type="FormGapAssessment", entity_id=assessment.id,
            after={"status": assessment.status, "resolution_note": note})
        return Response(FormGapAssessmentSerializer(assessment).data)


class CloneFormVersionView(APIView):
    permission_classes = [IsNCAEditor]
    @transaction.atomic
    def post(self, request, pk):
        source=generics.get_object_or_404(FormTemplate.objects.prefetch_related("sections__fields__options","sections__grids__columns","sections__grids__fixed_rows"), pk=pk)
        version=request.data.get("version", "").strip()
        if not version: return Response({"detail":"version is required."},status=400)
        if FormTemplate.objects.filter(family=source.family,version=version).exists(): return Response({"detail":"This family/version already exists."},status=409)
        clone=FormTemplate.objects.create(family=source.family,form_code=source.form_code,name=source.name,sector=source.sector,
            provider_category=source.provider_category,frequency=source.frequency,version=version,effective_from=request.data.get("effective_from",source.effective_from),
            status="DRAFT",kmz_required=source.kmz_required,excel_backup_enabled=source.excel_backup_enabled,instructions=source.instructions,
            source_reference=source.source_reference,source_sha256=source.source_sha256,mapping_basis=source.mapping_basis,prepared_by=request.user)
        field_map = {}
        grid_map = {}
        section_map = {}
        for section in source.sections.all():
            new_section=FormSection.objects.create(form_template=clone,section_code=section.section_code,title=section.title,instructions=section.instructions,sort_order=section.sort_order,kmz_upload_required=section.kmz_upload_required)
            section_map[section.id] = new_section
            for field in section.fields.all():
                new_field=FormField.objects.create(section=new_section,field_code=field.field_code,label=field.label,field_type=field.field_type,unit=field.unit,is_required=field.is_required,help_text=field.help_text,formula=field.formula,conditional_on_value=field.conditional_on_value,sort_order=field.sort_order,export_name=field.export_name)
                field_map[field.id] = new_field
                SelectOption.objects.bulk_create([SelectOption(field=new_field,value=o.value,label=o.label,sort_order=o.sort_order) for o in field.options.all()])
            for grid in section.grids.all():
                new_grid=FormGrid.objects.create(section=new_section,grid_code=grid.grid_code,title=grid.title,row_mode=grid.row_mode,min_rows=grid.min_rows,sort_order=grid.sort_order,instructions=grid.instructions)
                grid_map[grid.id] = new_grid
                GridColumn.objects.bulk_create([GridColumn(grid=new_grid,column_code=c.column_code,label=c.label,field_type=c.field_type,unit=c.unit,is_required=c.is_required,sort_order=c.sort_order) for c in grid.columns.all()])
                GridRow.objects.bulk_create([GridRow(grid=new_grid,row_label=r.row_label,sort_order=r.sort_order) for r in grid.fixed_rows.all()])
        for old_id, new_field in field_map.items():
            old_field = FormField.objects.get(pk=old_id)
            if old_field.conditional_on_field_id in field_map:
                new_field.conditional_on_field = field_map[old_field.conditional_on_field_id]
                new_field.save(update_fields=["conditional_on_field"])
        for requirement in source.kmz_requirements.all():
            KMZUploadRequirement.objects.create(
                form_template=clone, section=section_map.get(requirement.section_id), category=requirement.category,
                description=requirement.description, is_required=requirement.is_required, max_file_size_mb=requirement.max_file_size_mb,
            )
        for rule in source.validation_rules.all():
            parameters = dict(rule.parameters)
            for key in ("when_field", "left_field", "right_field", "equals_field"):
                if parameters.get(key) in field_map:
                    parameters[key] = field_map[parameters[key]].id
            ValidationRule.objects.create(
                form_template=clone, field=field_map.get(rule.field_id), grid=grid_map.get(rule.grid_id),
                rule_type=rule.rule_type, severity=rule.severity, parameters=parameters, message=rule.message,
                version=rule.version, is_active=rule.is_active, sort_order=rule.sort_order,
            )
        record_audit(user=request.user,action="FORM_VERSION_CLONED",entity_type="FormTemplate",entity_id=clone.id,after={"source_id":source.id,"version":version})
        return Response(FormTemplateDetailSerializer(clone).data,status=201)


class ApproveFormVersionView(APIView):
    permission_classes=[IsNCAEditor]
    def post(self,request,pk):
        form=generics.get_object_or_404(FormTemplate.objects.select_related("family"),pk=pk)
        if not form.mapping_complete or not form.source_reference or len(form.source_sha256)!=64: return Response({"detail":"Complete the source map, source reference and SHA-256 before approval."},status=409)
        recalculate_form_gaps(form, request.user)
        if form.gap_assessments.filter(requirement__severity__in=["BLOCKER", "HIGH"], status__in=["MISSING", "PARTIAL"]).exists():
            return Response({"detail":"Resolve all blocker/high Section 11 gaps before publication."},status=409)
        if not form.prepared_by_id or not form.sections.filter(models.Q(fields__isnull=False)|models.Q(grids__columns__isnull=False)).exists(): return Response({"detail":"A maker and at least one mapped data point are required."},status=409)
        if form.family.frequency_decision_status!="APPROVED" or not form.family.canonical_frequency: return Response({"detail":"Canonical frequency decision is pending."},status=409)
        if form.prepared_by_id==request.user.id: return Response({"detail":"Maker/checker approval requires a different Admin."},status=409)
        form.family.versions.exclude(pk=form.pk).filter(status="ACTIVE").update(status="ARCHIVED")
        form.approval_status="APPROVED";form.approved_by=request.user;form.approved_at=timezone.now();form.status="ACTIVE";form.published_at=timezone.now();form.save()
        record_audit(user=request.user,action="FORM_VERSION_APPROVED",entity_type="FormTemplate",entity_id=form.id)
        return Response(FormTemplateDetailSerializer(form).data)


class PublicationChecksView(APIView):
    permission_classes=[IsNCAEditor]
    def get(self,request,pk):
        form=generics.get_object_or_404(FormTemplate.objects.select_related("family").prefetch_related("sections__fields","sections__grids__columns","validation_rules"),pk=pk)
        recalculate_form_gaps(form, request.user)
        checks={
            "source_reference":bool(form.source_reference), "source_sha256":len(form.source_sha256)==64,
            "mapping_complete":form.mapping_complete, "frequency_decision":bool(form.family_id and form.family.frequency_decision_status=="APPROVED"),
            "has_sections":form.sections.exists(), "has_data_points":form.sections.filter(models.Q(fields__isnull=False)|models.Q(grids__columns__isnull=False)).exists(),
            "maker_identified":bool(form.prepared_by_id),
            "section_11_gaps_clear":not form.gap_assessments.filter(requirement__severity__in=["BLOCKER", "HIGH"], status__in=["MISSING", "PARTIAL"]).exists(),
        }
        return Response({"can_publish":all(checks.values()),"checks":checks,"preview":FormTemplateDetailSerializer(form).data})


# ── Sections ──────────────────────────────────────────────────────────────────

class SectionListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsNCAEditor]
    serializer_class = FormSectionSerializer

    def get_queryset(self):
        return FormSection.objects.filter(
            form_template_id=self.kwargs["pk"]
        ).prefetch_related("fields__options", "grids__columns", "grids__fixed_rows")

    def perform_create(self, serializer):
        form = generics.get_object_or_404(FormTemplate, pk=self.kwargs["pk"])
        reject_if_locked(form)
        max_order = FormSection.objects.filter(form_template=form).count()
        serializer.save(form_template=form, sort_order=max_order + 1)


class SectionDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsNCAEditor]
    serializer_class = FormSectionSerializer
    http_method_names = ["get", "patch", "delete", "head", "options"]

    def get_object(self):
        return generics.get_object_or_404(
            FormSection, pk=self.kwargs["sid"], form_template_id=self.kwargs["pk"]
        )

    def perform_update(self, serializer):
        reject_if_locked(serializer.instance.form_template)
        serializer.save()

    def perform_destroy(self, instance):
        reject_if_locked(instance.form_template)
        instance.delete()


# ── Fields ────────────────────────────────────────────────────────────────────

class FieldListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsNCAEditor]
    serializer_class = FormFieldSerializer

    def get_queryset(self):
        return FormField.objects.filter(section_id=self.kwargs["sid"])

    def perform_create(self, serializer):
        section = generics.get_object_or_404(FormSection, pk=self.kwargs["sid"])
        reject_if_locked(section.form_template)
        max_order = FormField.objects.filter(section=section).count()
        field = serializer.save(section=section, sort_order=max_order + 1)
        if field.field_type == "boolean" and not field.options.exists():
            SelectOption.objects.bulk_create([
                SelectOption(field=field, value="Yes", label="Yes", sort_order=1),
                SelectOption(field=field, value="No",  label="No",  sort_order=2),
            ])


class FieldDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsNCAEditor]
    serializer_class = FormFieldSerializer
    http_method_names = ["get", "patch", "delete", "head", "options"]

    def get_object(self):
        return generics.get_object_or_404(
            FormField, pk=self.kwargs["fid"], section_id=self.kwargs["sid"],
            section__form_template_id=self.kwargs["pk"],
        )

    def perform_update(self, serializer):
        reject_if_locked(serializer.instance.section.form_template)
        serializer.save()

    def perform_destroy(self, instance):
        reject_if_locked(instance.section.form_template)
        instance.delete()


class FieldOptionListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsNCAEditor]
    serializer_class = SelectOptionSerializer

    def get_queryset(self):
        return SelectOption.objects.filter(field_id=self.kwargs["fid"])

    def perform_create(self, serializer):
        field = generics.get_object_or_404(FormField, pk=self.kwargs["fid"])
        reject_if_locked(field.section.form_template)
        serializer.save(field=field, sort_order=field.options.count() + 1)


class FieldOptionDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsNCAEditor]
    serializer_class = SelectOptionSerializer
    http_method_names = ["patch", "delete", "head", "options"]

    def get_object(self):
        return generics.get_object_or_404(SelectOption, pk=self.kwargs["oid"], field_id=self.kwargs["fid"])

    def perform_update(self, serializer):
        reject_if_locked(serializer.instance.field.section.form_template)
        serializer.save()

    def perform_destroy(self, instance):
        reject_if_locked(instance.field.section.form_template)
        instance.delete()


# ── Grids ─────────────────────────────────────────────────────────────────────

class GridListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsNCAEditor]
    serializer_class = FormGridSerializer

    def get_queryset(self):
        return FormGrid.objects.filter(section_id=self.kwargs["sid"]).prefetch_related("columns", "fixed_rows")

    def perform_create(self, serializer):
        section = generics.get_object_or_404(FormSection, pk=self.kwargs["sid"])
        reject_if_locked(section.form_template)
        max_order = FormGrid.objects.filter(section=section).count()
        serializer.save(section=section, sort_order=max_order + 1)


class GridDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsNCAEditor]
    serializer_class = FormGridSerializer
    http_method_names = ["get", "patch", "delete", "head", "options"]

    def get_object(self):
        return generics.get_object_or_404(
            FormGrid, pk=self.kwargs["gid"], section_id=self.kwargs["sid"],
            section__form_template_id=self.kwargs["pk"],
        )

    def perform_update(self, serializer):
        reject_if_locked(serializer.instance.section.form_template)
        serializer.save()

    def perform_destroy(self, instance):
        reject_if_locked(instance.section.form_template)
        instance.delete()


class GridColumnCreateView(APIView):
    permission_classes = [IsNCAEditor]

    def post(self, request, gid):
        grid = generics.get_object_or_404(FormGrid, pk=gid)
        if locked(grid.section.form_template):
            return Response({"detail": "Used form versions are immutable. Clone a new version."}, status=409)
        max_order = GridColumn.objects.filter(grid=grid).count()
        serializer = GridColumnSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(grid=grid, sort_order=max_order + 1)
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)


class GridColumnDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsNCAEditor]
    serializer_class = GridColumnSerializer
    http_method_names = ["patch", "delete", "head", "options"]

    def get_object(self):
        return generics.get_object_or_404(GridColumn, pk=self.kwargs["cid"], grid_id=self.kwargs["gid"])

    def perform_update(self, serializer):
        reject_if_locked(serializer.instance.grid.section.form_template)
        serializer.save()

    def perform_destroy(self, instance):
        reject_if_locked(instance.grid.section.form_template)
        instance.delete()


class GridRowCreateView(APIView):
    permission_classes = [IsNCAEditor]

    def post(self, request, gid):
        grid = generics.get_object_or_404(FormGrid, pk=gid)
        if locked(grid.section.form_template):
            return Response({"detail": "Used form versions are immutable. Clone a new version."}, status=409)
        if grid.row_mode != "FIXED":
            return Response({"detail": "Only FIXED grids accept pre-populated rows."}, status=400)
        max_order = GridRow.objects.filter(grid=grid).count()
        row = GridRow.objects.create(
            grid=grid,
            row_label=request.data.get("row_label", ""),
            sort_order=max_order + 1,
        )
        return Response({"id": row.id, "row_label": row.row_label, "sort_order": row.sort_order}, status=201)


class GridRowDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsNCAEditor]
    serializer_class = GridRowSerializer
    http_method_names = ["patch", "delete", "head", "options"]

    def get_object(self):
        return generics.get_object_or_404(GridRow, pk=self.kwargs["rid"], grid_id=self.kwargs["gid"])

    def perform_update(self, serializer):
        reject_if_locked(serializer.instance.grid.section.form_template)
        serializer.save()

    def perform_destroy(self, instance):
        reject_if_locked(instance.grid.section.form_template)
        instance.delete()


# ── KMZ Requirements ──────────────────────────────────────────────────────────

class KMZRequirementListView(generics.ListAPIView):
    serializer_class = KMZRequirementSerializer

    def get_queryset(self):
        return KMZUploadRequirement.objects.filter(form_template__form_code="DC-DBS05")


# ── Period: Assign templates & providers ──────────────────────────────────────

class PeriodAssignTemplatesView(APIView):
    permission_classes = [IsNCAEditor]

    def post(self, request, pk):
        from apps.submissions.models import ReportingPeriod
        period = generics.get_object_or_404(ReportingPeriod, pk=pk)
        template_ids = request.data.get("template_ids", [])
        period.applicable_form_templates.set(template_ids)
        return Response({"detail": "Form templates updated.", "count": len(template_ids)})


class PeriodAssignProvidersView(APIView):
    permission_classes = [IsNCAEditor]

    def post(self, request, pk):
        from apps.submissions.models import ReportingPeriod
        period = generics.get_object_or_404(ReportingPeriod, pk=pk)
        provider_ids = request.data.get("provider_ids", [])
        period.assigned_providers.set(provider_ids)
        return Response({"detail": "Providers updated.", "count": len(provider_ids)})
