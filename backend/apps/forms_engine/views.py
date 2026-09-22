import hashlib
import os
import threading
import uuid
from datetime import date

from django.conf import settings
from rest_framework import generics, status, serializers
from rest_framework.parsers import MultiPartParser, JSONParser
from apps.users.permissions import IsNCAUser, IsNCAEditor, IsNCAOrReadOnly
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    FormCodeCatalog, FormFamily, FormTemplate, FormSection, FormHeading, FormField, FormGrid,
    GridColumn, GridRow, SelectOption, KMZUploadRequirement, ValidationRule, FormRequirement, FormGapAssessment,
    FormWorkbookImport,
)
from .serializers import (
    FormTemplateListSerializer, FormTemplateDetailSerializer,
    FormSectionSerializer, FormHeadingSerializer, FormFieldSerializer, FormGridSerializer,
    GridColumnSerializer, GridRowSerializer, SelectOptionSerializer, KMZRequirementSerializer,
    FormFamilySerializer, ValidationRuleSerializer, FormRequirementSerializer, FormGapAssessmentSerializer,
    FormWorkbookImportSerializer, FormCodeCatalogSerializer,
)
from .workbook_import import (
    PARSER_VERSION, STREAMING_THRESHOLD_BYTES, create_template_from_import,
    normalize_form_code, process_workbook_import_record,
)
from .gaps import recalculate_form_gaps
from django.db import transaction
from django.db import models
from django.utils import timezone
from apps.audit.services import record_audit


def _schedule_workbook_import(import_id):
    if settings.DEBUG:
        threading.Thread(
            target=process_workbook_import_record,
            args=(import_id,),
            name=f"workbook-import-{import_id}",
            daemon=True,
        ).start()
        return
    from .tasks import process_workbook_import
    process_workbook_import.delay(import_id)


def locked(form):
    return form.approval_status == "APPROVED" or form.expectedsubmission_set.exists()


def reject_if_locked(form):
    if locked(form):
        raise serializers.ValidationError("Used form versions are immutable. Clone a new version.")


def audit_form_change(request, action, instance, *, after=None):
    record_audit(
        user=request.user, action=action, entity_type=type(instance).__name__, entity_id=instance.pk,
        after=after or {}, ip_address=request.META.get("REMOTE_ADDR"),
    )


# ── Form Templates ────────────────────────────────────────────────────────────

class FormTemplateListView(generics.ListCreateAPIView):
    permission_classes = [IsNCAOrReadOnly]
    queryset = FormTemplate.objects.all()
    filterset_fields = ["sector", "provider_category", "frequency", "status"]

    def get_serializer_class(self):
        return FormTemplateListSerializer

    def perform_create(self, serializer):
        form = serializer.save(prepared_by=self.request.user, status="DRAFT", approval_status="DRAFT")
        audit_form_change(self.request, "FORM_TEMPLATE_CREATED", form, after={"form_code": form.form_code, "version": form.version})


class FormWorkbookImportListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsNCAEditor]
    serializer_class = FormWorkbookImportSerializer
    parser_classes = [MultiPartParser, JSONParser]

    def get_queryset(self):
        return FormWorkbookImport.objects.select_related("created_by", "resulting_template")

    def create(self, request, *args, **kwargs):
        uploaded = request.FILES.get("file")
        if not uploaded:
            return Response({"detail": "Attach an .xlsx, .pdf, or .docx source file."}, status=400)
        if not uploaded.name.lower().endswith((".xlsx", ".pdf", ".docx")):
            return Response({"detail": "Only .xlsx, .pdf, and .docx source files are accepted."}, status=400)
        if uploaded.size > 20 * 1024 * 1024:
            return Response({"detail": "The workbook exceeds the 20 MB limit."}, status=400)
        required = ["form_code", "version"]
        missing = [field for field in required if not str(request.data.get(field, "")).strip()]
        if missing:
            return Response({"detail": f"Required fields: {', '.join(missing)}."}, status=400)
        try:
            form_code = normalize_form_code(request.data["form_code"])
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        catalog = FormCodeCatalog.objects.filter(code=form_code, is_active=True).first()
        if not catalog:
            return Response({"detail": "Select an available governed form code."}, status=400)
        version = request.data["version"].strip()
        if version != catalog.next_version:
            return Response({"detail": f"The next available version is {catalog.next_version}. Refresh and try again."}, status=409)
        storage_dir = os.path.join(settings.PRIVATE_UPLOAD_ROOT, "form-workbooks")
        os.makedirs(storage_dir, exist_ok=True)
        extension = os.path.splitext(uploaded.name)[1].lower()
        storage_name = f"{uuid.uuid4().hex}{extension}"
        storage_path = os.path.join("form-workbooks", storage_name)
        full_path = os.path.join(settings.PRIVATE_UPLOAD_ROOT, storage_path)
        digest = hashlib.sha256()
        with open(full_path, "wb") as destination:
            for chunk in uploaded.chunks():
                destination.write(chunk)
                digest.update(chunk)
        workbook_import = FormWorkbookImport.objects.create(
            form_code=form_code, name=catalog.name, version=version,
            sector=catalog.sector, provider_category=catalog.provider_category, frequency=catalog.frequency,
            file_name=os.path.basename(uploaded.name), file_size=uploaded.size, storage_path=storage_path,
            sha256=digest.hexdigest(), created_by=request.user, parser_version=PARSER_VERSION,
        )
        async_threshold = getattr(settings, "FORM_WORKBOOK_ASYNC_THRESHOLD_BYTES", STREAMING_THRESHOLD_BYTES)
        is_async = uploaded.size >= async_threshold
        if is_async:
            _schedule_workbook_import(workbook_import.id)
        else:
            process_workbook_import_record(workbook_import.id)
            workbook_import.refresh_from_db()
        record_audit(
            user=request.user, action="FORM_WORKBOOK_IMPORTED", entity_type="FormWorkbookImport", entity_id=workbook_import.id,
            after={"file_name": workbook_import.file_name, "sha256": workbook_import.sha256, "scan_status": workbook_import.scan_status, "parse_status": workbook_import.parse_status},
        )
        # The upload itself created a durable import record even when scanning or
        # parsing failed. Return that resource so the UI can open a diagnostic
        # preview instead of reducing a useful parser error to a generic 422.
        response_status = status.HTTP_202_ACCEPTED if is_async else status.HTTP_201_CREATED
        return Response(FormWorkbookImportSerializer(workbook_import).data, status=response_status)


class FormWorkbookImportDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsNCAEditor]
    serializer_class = FormWorkbookImportSerializer
    queryset = FormWorkbookImport.objects.select_related("created_by", "resulting_template")
    http_method_names = ["get", "patch", "head", "options"]

    def patch(self, request, *args, **kwargs):
        item = self.get_object()
        if item.parse_status != "READY":
            return Response({"detail": "Only a ready, unconfirmed import can be edited."}, status=409)
        return super().patch(request, *args, **kwargs)


class ReparseFormWorkbookImportView(APIView):
    permission_classes = [IsNCAEditor]

    def post(self, request, pk):
        item = generics.get_object_or_404(FormWorkbookImport, pk=pk)
        if item.resulting_template_id:
            return Response({"detail": "Confirmed imports are immutable."}, status=409)
        column_mappings = request.data.get("column_mappings")
        if not isinstance(column_mappings, dict):
            return Response({"detail": "column_mappings must be an object keyed by worksheet name."}, status=400)
        decisions = dict(item.mapping_decisions or {})
        decisions["column_mappings"] = column_mappings
        item.mapping_decisions = decisions
        item.parse_status = "PENDING"
        item.warnings = []
        item.save(update_fields=["mapping_decisions", "parse_status", "warnings", "updated_at"])
        async_threshold = getattr(settings, "FORM_WORKBOOK_ASYNC_THRESHOLD_BYTES", STREAMING_THRESHOLD_BYTES)
        is_async = item.file_size >= async_threshold
        if is_async:
            _schedule_workbook_import(item.id)
        else:
            process_workbook_import_record(item.id)
            item.refresh_from_db()
        return Response(
            FormWorkbookImportSerializer(item).data,
            status=status.HTTP_202_ACCEPTED if is_async else status.HTTP_200_OK,
        )


class ConfirmFormWorkbookImportView(APIView):
    permission_classes = [IsNCAEditor]

    @transaction.atomic
    def post(self, request, pk):
        item = generics.get_object_or_404(FormWorkbookImport.objects.select_for_update(), pk=pk)
        if item.scan_status != "CLEAN" or item.parse_status not in {"READY", "CONFIRMED"}:
            return Response({"detail": "The workbook must be clean and successfully parsed before confirmation."}, status=409)
        blocking_codes = {warning.get("code") for warning in item.warnings if warning.get("severity") == "BLOCKING"}
        resolved_codes = set((item.mapping_decisions or {}).get("resolved_warning_codes", []))
        # A missing Indicator/Definition mapping is objective structural state,
        # not an advisory that can be dismissed. Reparse with a valid mapping
        # before confirmation instead of resolving this warning manually.
        structural_codes = {
            code for code in blocking_codes
            if code and code.startswith("MISSING_DEFINITION_COLUMNS_")
        }
        unresolved_codes = sorted(code for code in (blocking_codes - resolved_codes) | structural_codes if code)
        if unresolved_codes:
            return Response({"detail": "Resolve every blocking workbook warning before confirmation.", "warning_codes": unresolved_codes}, status=409)
        try:
            form = create_template_from_import(item, request.user)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=409)
        record_audit(user=request.user, action="FORM_WORKBOOK_CONFIRMED", entity_type="FormTemplate", entity_id=form.id, after={"workbook_import": item.id})
        return Response(FormTemplateDetailSerializer(form).data, status=201 if item.resulting_template_id == form.id else 200)


class FormTemplateDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsNCAOrReadOnly]
    queryset = FormTemplate.objects.prefetch_related(
        "sections__headings",
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
        response = super().patch(request, *args, **kwargs)
        audit_form_change(request, "FORM_TEMPLATE_UPDATED", self.get_object(), after={"changed_fields": sorted(request.data)})
        return response


class FormFamilyListCreate(generics.ListCreateAPIView):
    permission_classes = [IsNCAEditor]
    queryset = FormFamily.objects.all().order_by("code")
    serializer_class = FormFamilySerializer

    def perform_create(self, serializer):
        code=serializer.validated_data["code"]
        family = serializer.save(frequency_decision_status="PENDING_DECISION" if code=="DC-DBS05" else "APPROVED",
            canonical_frequency="" if code=="DC-DBS05" else serializer.validated_data.get("canonical_frequency", ""))
        audit_form_change(self.request, "FORM_FAMILY_CREATED", family, after={"code": family.code})


class FormCodeCatalogListView(generics.ListAPIView):
    permission_classes = [IsNCAEditor]
    serializer_class = FormCodeCatalogSerializer
    queryset = FormCodeCatalog.objects.filter(is_active=True).order_by("sort_order", "code")


class ApproveFrequencyDecisionView(APIView):
    permission_classes = [IsNCAEditor]

    def post(self, request, pk):
        family = generics.get_object_or_404(FormFamily, pk=pk)
        frequency = request.data.get("canonical_frequency")
        reference = request.data.get("frequency_decision_reference", "").strip()
        source_owner = request.data.get("source_owner", "").strip()
        if frequency not in {"MONTHLY", "QUARTERLY", "SEMI_ANNUAL", "ANNUAL"} or not reference or not source_owner:
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
        source=generics.get_object_or_404(FormTemplate.objects.prefetch_related("sections__headings","sections__fields__options","sections__grids__columns","sections__grids__fixed_rows"), pk=pk)
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
        heading_map = {}
        for section in source.sections.all():
            new_section=FormSection.objects.create(form_template=clone,section_code=section.section_code,title=section.title,instructions=section.instructions,sort_order=section.sort_order,kmz_upload_required=section.kmz_upload_required)
            section_map[section.id] = new_section
            for heading in section.headings.all():
                heading_map[heading.id] = FormHeading.objects.create(
                    section=new_section, heading_code=heading.heading_code, title=heading.title,
                    level=heading.level, sort_order=heading.sort_order, source_row=heading.source_row,
                )
            for field in section.fields.all():
                new_field=FormField.objects.create(section=new_section,heading=heading_map.get(field.heading_id),field_code=field.field_code,label=field.label,field_type=field.field_type,unit=field.unit,is_required=field.is_required,help_text=field.help_text,formula=field.formula,conditional_on_value=field.conditional_on_value,sort_order=field.sort_order,export_name=field.export_name)
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
        if request.user.role != "NCA_ADMIN":
            return Response({"detail":"Only an NCA Admin can publish a template. Officers can prepare and submit drafts for approval."},status=403)
        if not form.mapping_complete or not form.source_reference or len(form.source_sha256)!=64: return Response({"detail":"Complete the source map, source reference and SHA-256 before approval."},status=409)
        section_11_applicable = form.mapping_basis == "PRD_SECTION_11"
        if section_11_applicable:
            recalculate_form_gaps(form, request.user)
        if section_11_applicable and form.gap_assessments.filter(requirement__severity__in=["BLOCKER", "HIGH"], status__in=["MISSING", "PARTIAL"]).exists():
            return Response({"detail":"Resolve all blocker/high Section 11 gaps before publication."},status=409)
        if not form.prepared_by_id or not form.sections.filter(models.Q(fields__isnull=False)|models.Q(grids__columns__isnull=False)).exists(): return Response({"detail":"A maker and at least one mapped data point are required."},status=409)
        if form.family.frequency_decision_status!="APPROVED" or not form.family.canonical_frequency: return Response({"detail":"Canonical frequency decision is pending."},status=409)
        # Admin-created templates may be self-published. Officer-created templates
        # are necessarily checked by an Admin because this endpoint is Admin-only.
        form.family.versions.exclude(pk=form.pk).filter(status="ACTIVE").update(status="ARCHIVED")
        form.approval_status="APPROVED";form.approved_by=request.user;form.approved_at=timezone.now();form.status="ACTIVE";form.published_at=timezone.now();form.save()
        record_audit(user=request.user,action="FORM_VERSION_APPROVED",entity_type="FormTemplate",entity_id=form.id)
        return Response(FormTemplateDetailSerializer(form).data)


class PublicationChecksView(APIView):
    permission_classes=[IsNCAEditor]
    def get(self,request,pk):
        form=generics.get_object_or_404(FormTemplate.objects.select_related("family").prefetch_related("sections__fields","sections__grids__columns","validation_rules"),pk=pk)
        section_11_applicable = form.mapping_basis == "PRD_SECTION_11"
        if section_11_applicable:
            recalculate_form_gaps(form, request.user)
        checks={
            "source_reference":bool(form.source_reference), "source_sha256":len(form.source_sha256)==64,
            "mapping_complete":form.mapping_complete, "frequency_decision":bool(form.family_id and form.family.frequency_decision_status=="APPROVED"),
            "has_sections":form.sections.exists(), "has_data_points":form.sections.filter(models.Q(fields__isnull=False)|models.Q(grids__columns__isnull=False)).exists(),
            "maker_identified":bool(form.prepared_by_id),
        }
        if section_11_applicable:
            checks["section_11_gaps_clear"] = not form.gap_assessments.filter(
                requirement__severity__in=["BLOCKER", "HIGH"], status__in=["MISSING", "PARTIAL"],
            ).exists()
        return Response({
            "can_publish":all(checks.values()), "checks":checks,
            "section_11_applicable":section_11_applicable,
            "publication_basis":"PRD_SECTION_11" if section_11_applicable else form.mapping_basis,
            "preview":FormTemplateDetailSerializer(form).data,
        })


def _assignment_preview(form, provider_ids, *, mode, period=None, override_reason="", lock=False):
    from apps.providers.models import ProviderProfile, ProviderFormAssignment
    from apps.submissions.models import PeriodFormAssignment
    from apps.users.models import User

    selected_ids = set(map(int, provider_ids))
    providers = ProviderProfile.objects.filter(status="ACTIVE").order_by("registered_name")
    if lock:
        providers = providers.select_for_update()
    rows = []
    for provider in providers:
        has_data_entry = bool(provider.organization_id and User.objects.filter(
            organization_id=provider.organization_id, role="PROVIDER_DATA_ENTRY", is_active=True,
        ).exists())
        has_approver = bool(provider.organization_id and User.objects.filter(
            organization_id=provider.organization_id, role="PROVIDER_APPROVER", is_active=True,
        ).exists())
        ready = has_data_entry and has_approver
        mismatch = provider.sector != form.sector or provider.category != form.provider_category
        if mode == "MANUAL":
            duplicate = bool(period and PeriodFormAssignment.objects.filter(period=period, form_template=form, provider=provider).exists())
        else:
            duplicate = ProviderFormAssignment.objects.filter(
                provider=provider, form_family=form.family,
                effective_to__isnull=True, obligation__in=["REQUIRED", "OPTIONAL"],
            ).exists()
        blocking_reason = ""
        if not has_data_entry and not has_approver:
            blocking_reason = "Add active Data Entry and Provider Approver accounts before sending."
        elif not has_data_entry:
            blocking_reason = "Add an active Provider Data Entry account before sending."
        elif not has_approver:
            blocking_reason = "Add an active Provider Approver account before sending."
        elif duplicate:
            blocking_reason = "This exact form version has already been sent for the selected period."
        elif mismatch and not override_reason.strip():
            blocking_reason = "An additional assignment reason is required."
        rows.append({
            "provider_id": provider.id, "provider_name": provider.registered_name,
            "provider_sector": provider.sector, "provider_category": provider.category,
            "selected": provider.id in selected_ids,
            "has_data_entry": has_data_entry, "has_approver": has_approver, "ready": ready,
            "mismatch": mismatch, "duplicate": duplicate, "blocking_reason": blocking_reason,
            "can_assign": ready and not duplicate and (not mismatch or bool(override_reason.strip())),
        })
    missing_ids = selected_ids - {row["provider_id"] for row in rows}
    return rows, missing_ids


class FormAssignmentPreviewView(APIView):
    permission_classes = [IsNCAEditor]

    def get(self, request, pk):
        from apps.submissions.models import ReportingPeriod
        form = generics.get_object_or_404(FormTemplate.objects.select_related("family"), pk=pk)
        provider_ids = [value for value in request.query_params.get("provider_ids", "").split(",") if value.isdigit()]
        mode = request.query_params.get("mode", "RECURRING").upper()
        if mode not in {"RECURRING", "MANUAL"}:
            return Response({"detail": "mode must be RECURRING or MANUAL."}, status=400)
        period = generics.get_object_or_404(ReportingPeriod, pk=request.query_params.get("period")) if mode == "MANUAL" and request.query_params.get("period") else None
        if period and period.status != "ACTIVE":
            return Response({"detail": "Forms can only be sent to an active reporting period."}, status=409)
        if period and period.frequency != form.frequency:
            return Response({"detail": "The form frequency must match the reporting period."}, status=409)
        rows, missing_ids = _assignment_preview(form, provider_ids, mode=mode, period=period, override_reason=request.query_params.get("override_reason", ""))
        selected_rows = [row for row in rows if row["selected"]]
        return Response({
            "form_template": form.id, "mode": mode, "period": period.id if period else None,
            "due_at": period.due_at if period else None, "providers": rows,
            "missing_provider_ids": sorted(missing_ids),
            "summary": {
                "selected": len(provider_ids), "assignable": sum(row["can_assign"] for row in selected_rows),
                "mismatches": sum(row["mismatch"] for row in selected_rows),
                "duplicates": sum(row["duplicate"] for row in selected_rows),
                "not_ready": sum(not row["ready"] for row in selected_rows),
                "blocked": sum(not row["can_assign"] and not row["duplicate"] for row in selected_rows) + len(missing_ids),
            },
        })


class FormAssignmentListCreateView(APIView):
    permission_classes = [IsNCAEditor]

    def get(self, request, pk):
        from apps.providers.models import ProviderFormAssignment
        from apps.submissions.models import PeriodFormAssignment
        form = generics.get_object_or_404(FormTemplate.objects.select_for_update().select_related("family"), pk=pk)
        recurring = ProviderFormAssignment.objects.filter(form_family=form.family).select_related("provider", "confirmed_by")
        manual = PeriodFormAssignment.objects.filter(form_template=form).select_related("provider", "period", "assigned_by")
        return Response({
            "recurring": [{
                "id": item.id, "provider_id": item.provider_id, "provider_name": item.provider.registered_name,
                "effective_from": item.effective_from, "effective_to": item.effective_to,
                "obligation": item.obligation, "source_reference": item.source_reference,
            } for item in recurring],
            "manual": [{
                "id": item.id, "provider_id": item.provider_id, "provider_name": item.provider.registered_name,
                "period_id": item.period_id, "period_name": item.period.name,
                "override_reason": item.mismatch_override_reason, "created_at": item.created_at,
            } for item in manual],
        })

    @transaction.atomic
    def post(self, request, pk):
        from apps.providers.models import ProviderProfile, ProviderFormAssignment
        from apps.submissions.models import ReportingPeriod, PeriodFormAssignment, ExpectedSubmission
        form = generics.get_object_or_404(FormTemplate.objects.select_related("family"), pk=pk)
        if form.status != "ACTIVE" or form.approval_status != "APPROVED":
            return Response({"detail": "Only an active, approved form can be assigned."}, status=409)
        raw_provider_ids = request.data.get("provider_ids", [])
        if not isinstance(raw_provider_ids, list) or not raw_provider_ids:
            return Response({"detail": "Select at least one provider."}, status=400)
        try:
            provider_ids = list(dict.fromkeys(int(value) for value in raw_provider_ids))
        except (TypeError, ValueError):
            return Response({"detail": "provider_ids must contain provider record IDs."}, status=400)
        mode = str(request.data.get("mode", "RECURRING")).upper()
        if mode not in {"RECURRING", "MANUAL"}:
            return Response({"detail": "mode must be RECURRING or MANUAL."}, status=400)
        override_reason = str(request.data.get("override_reason", "")).strip()
        message_subject = str(request.data.get("message_subject", "")).strip()
        message_body = str(request.data.get("message_body", "")).strip()
        period = None
        if mode == "MANUAL":
            period = generics.get_object_or_404(ReportingPeriod.objects.select_for_update(), pk=request.data.get("period_id"))
            if period.status != "ACTIVE":
                return Response({"detail": "Forms can only be sent to an active reporting period."}, status=409)
            if period.frequency != form.frequency:
                return Response({"detail": "The form frequency must match the reporting period."}, status=409)
        rows, missing_ids = _assignment_preview(form, provider_ids, mode=mode, period=period, override_reason=override_reason, lock=True)
        selected_rows = [row for row in rows if row["selected"]]
        if missing_ids:
            return Response({"detail": "One or more selected providers are unavailable.", "missing_provider_ids": sorted(missing_ids)}, status=400)
        not_ready = [row for row in selected_rows if not row["ready"]]
        if not_ready:
            return Response({
                "detail": "Every selected provider must have active Data Entry and Provider Approver accounts before a form can be sent.",
                "blocked": len(not_ready), "providers": not_ready,
            }, status=409)
        mismatches = [row for row in selected_rows if row["mismatch"]]
        if mismatches and not override_reason:
            return Response({"detail": "An additional assignment reason is required for one or more selected providers.", "mismatches": mismatches}, status=409)
        obligations_created, duplicates, recurring_schedules_created = 0, 0, 0
        obligation_references = []
        recurring_references = []
        providers = {item.id: item for item in ProviderProfile.objects.filter(pk__in=provider_ids)}
        for row in selected_rows:
            provider = providers[row["provider_id"]]
            if row["duplicate"]:
                duplicates += 1
                continue
            if mode == "RECURRING":
                effective_from = request.data.get("effective_from") or date.today().isoformat()
                effective_to = request.data.get("effective_to") or None
                assignment = ProviderFormAssignment.objects.create(
                    provider=provider, form_family=form.family, obligation="REQUIRED",
                    effective_from=effective_from, effective_to=effective_to,
                    source_reference=f"Form Builder assignment by {request.user.email}" + (f"; mismatch override: {override_reason}" if row["mismatch"] else ""),
                    confirmed_by=request.user,
                )
                recurring_schedules_created += 1
                recurring_references.append({
                    "provider_id": provider.id,
                    "provider_name": provider.registered_name,
                    "assignment_id": assignment.id,
                    "effective_from": assignment.effective_from,
                    "effective_to": assignment.effective_to,
                })
                record_audit(user=request.user, action="FORM_RECURRING_ASSIGNMENT_CREATED", entity_type="ProviderFormAssignment", entity_id=assignment.id, after={"form": form.id, "provider": provider.id, "override_reason": override_reason if row["mismatch"] else ""})
            else:
                assignment = PeriodFormAssignment.objects.create(
                    period=period, form_template=form, provider=provider,
                    mismatch_override_reason=override_reason if row["mismatch"] else "", assigned_by=request.user,
                )
                expected, _ = ExpectedSubmission.create_from_assignment(
                    provider=provider, form_template=form, period=period,
                    manual_assignment=assignment, actor=request.user,
                    message_subject=message_subject,
                    message_body=message_body,
                )
                submission = expected.versions.order_by("version").first()
                assignment_event = submission.timeline_events.filter(event_type="FORM_ASSIGNED").order_by("-id").first()
                obligations_created += 1
                obligation_references.append({
                    "provider_id": provider.id, "provider_name": provider.registered_name,
                    "assignment_id": assignment.id, "expected_submission_id": expected.id,
                    "submission_id": submission.id,
                    "event_id": assignment_event.id if assignment_event else None,
                    "period_id": period.id, "period_name": period.name,
                    "due_at": expected.effective_due_at,
                })
                record_audit(user=request.user, action="FORM_MANUAL_ASSIGNMENT_CREATED", entity_type="PeriodFormAssignment", entity_id=assignment.id, after={"form": form.id, "provider": provider.id, "period": period.id, "override_reason": assignment.mismatch_override_reason})
        return Response({
            "created": obligations_created + recurring_schedules_created,
            "existing": duplicates,
            "obligations_created": obligations_created,
            "duplicates": duplicates,
            "recurring_schedules_created": recurring_schedules_created,
            "blocked": 0, "mode": mode,
            "delivery_type": "IMMEDIATE" if mode == "MANUAL" else "SCHEDULED",
            "obligations": obligation_references,
            "recurring_schedules": recurring_references,
        }, status=201 if obligations_created or recurring_schedules_created else 200)


# ── Sections ──────────────────────────────────────────────────────────────────

class SectionListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsNCAEditor]
    serializer_class = FormSectionSerializer

    def get_queryset(self):
        return FormSection.objects.filter(
            form_template_id=self.kwargs["pk"]
        ).prefetch_related("headings", "fields__options", "grids__columns", "grids__fixed_rows")

    def perform_create(self, serializer):
        form = generics.get_object_or_404(FormTemplate, pk=self.kwargs["pk"])
        reject_if_locked(form)
        max_order = FormSection.objects.filter(form_template=form).count()
        section = serializer.save(form_template=form, sort_order=max_order + 1)
        audit_form_change(self.request, "FORM_SECTION_CREATED", section, after={"form_template_id": form.id})


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
        section = serializer.save()
        audit_form_change(self.request, "FORM_SECTION_UPDATED", section, after={"changed_fields": sorted(serializer.validated_data)})

    def perform_destroy(self, instance):
        reject_if_locked(instance.form_template)
        audit_form_change(self.request, "FORM_SECTION_DELETED", instance, after={"form_template_id": instance.form_template_id})
        instance.delete()


# ── Fields ────────────────────────────────────────────────────────────────────

class HeadingListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsNCAEditor]
    serializer_class = FormHeadingSerializer

    def get_queryset(self):
        return FormHeading.objects.filter(
            section_id=self.kwargs["sid"], section__form_template_id=self.kwargs["pk"],
        )

    def perform_create(self, serializer):
        section = generics.get_object_or_404(
            FormSection, pk=self.kwargs["sid"], form_template_id=self.kwargs["pk"],
        )
        reject_if_locked(section.form_template)
        next_order = max(
            list(section.headings.values_list("sort_order", flat=True))
            + list(section.fields.values_list("sort_order", flat=True))
            + list(section.grids.values_list("sort_order", flat=True))
            + [0]
        ) + 1
        heading = serializer.save(section=section, sort_order=serializer.validated_data.get("sort_order") or next_order)
        audit_form_change(self.request, "FORM_HEADING_CREATED", heading, after={"section_id": section.id})


class HeadingDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsNCAEditor]
    serializer_class = FormHeadingSerializer
    http_method_names = ["get", "patch", "delete", "head", "options"]

    def get_object(self):
        return generics.get_object_or_404(
            FormHeading, pk=self.kwargs["hid"], section_id=self.kwargs["sid"],
            section__form_template_id=self.kwargs["pk"],
        )

    def perform_update(self, serializer):
        reject_if_locked(serializer.instance.section.form_template)
        heading = serializer.save()
        audit_form_change(self.request, "FORM_HEADING_UPDATED", heading, after={"changed_fields": sorted(serializer.validated_data)})

    def perform_destroy(self, instance):
        reject_if_locked(instance.section.form_template)
        audit_form_change(self.request, "FORM_HEADING_DELETED", instance, after={"section_id": instance.section_id})
        instance.delete()


class FieldListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsNCAEditor]
    serializer_class = FormFieldSerializer

    def get_queryset(self):
        return FormField.objects.filter(
            section_id=self.kwargs["sid"], section__form_template_id=self.kwargs["pk"],
        )

    def perform_create(self, serializer):
        section = generics.get_object_or_404(
            FormSection, pk=self.kwargs["sid"], form_template_id=self.kwargs["pk"],
        )
        reject_if_locked(section.form_template)
        heading = serializer.validated_data.get("heading")
        if heading and heading.section_id != section.id:
            raise serializers.ValidationError({"heading": "The heading must belong to this section."})
        max_order = FormField.objects.filter(section=section).count()
        field = serializer.save(section=section, sort_order=max_order + 1)
        if field.field_type == "boolean" and not field.options.exists():
            SelectOption.objects.bulk_create([
                SelectOption(field=field, value="Yes", label="Yes", sort_order=1),
                SelectOption(field=field, value="No",  label="No",  sort_order=2),
            ])
        audit_form_change(self.request, "FORM_FIELD_CREATED", field, after={"section_id": section.id, "field_type": field.field_type})


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
        heading = serializer.validated_data.get("heading")
        if heading and heading.section_id != serializer.instance.section_id:
            raise serializers.ValidationError({"heading": "The heading must belong to this section."})
        field = serializer.save()
        audit_form_change(self.request, "FORM_FIELD_UPDATED", field, after={"changed_fields": sorted(serializer.validated_data)})

    def perform_destroy(self, instance):
        reject_if_locked(instance.section.form_template)
        audit_form_change(self.request, "FORM_FIELD_DELETED", instance, after={"section_id": instance.section_id})
        instance.delete()


class FieldOptionListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsNCAEditor]
    serializer_class = SelectOptionSerializer

    def get_queryset(self):
        return SelectOption.objects.filter(field_id=self.kwargs["fid"])

    def perform_create(self, serializer):
        field = generics.get_object_or_404(FormField, pk=self.kwargs["fid"])
        reject_if_locked(field.section.form_template)
        option = serializer.save(field=field, sort_order=field.options.count() + 1)
        audit_form_change(self.request, "FORM_OPTION_CREATED", option, after={"field_id": field.id})


class FieldOptionDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsNCAEditor]
    serializer_class = SelectOptionSerializer
    http_method_names = ["patch", "delete", "head", "options"]

    def get_object(self):
        return generics.get_object_or_404(SelectOption, pk=self.kwargs["oid"], field_id=self.kwargs["fid"])

    def perform_update(self, serializer):
        reject_if_locked(serializer.instance.field.section.form_template)
        option = serializer.save()
        audit_form_change(self.request, "FORM_OPTION_UPDATED", option, after={"changed_fields": sorted(serializer.validated_data)})

    def perform_destroy(self, instance):
        reject_if_locked(instance.field.section.form_template)
        audit_form_change(self.request, "FORM_OPTION_DELETED", instance, after={"field_id": instance.field_id})
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
        grid = serializer.save(section=section, sort_order=max_order + 1)
        audit_form_change(self.request, "FORM_GRID_CREATED", grid, after={"section_id": section.id})


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
        grid = serializer.save()
        audit_form_change(self.request, "FORM_GRID_UPDATED", grid, after={"changed_fields": sorted(serializer.validated_data)})

    def perform_destroy(self, instance):
        reject_if_locked(instance.section.form_template)
        audit_form_change(self.request, "FORM_GRID_DELETED", instance, after={"section_id": instance.section_id})
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
            column = serializer.save(grid=grid, sort_order=max_order + 1)
            audit_form_change(request, "FORM_GRID_COLUMN_CREATED", column, after={"grid_id": grid.id})
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
        column = serializer.save()
        audit_form_change(self.request, "FORM_GRID_COLUMN_UPDATED", column, after={"changed_fields": sorted(serializer.validated_data)})

    def perform_destroy(self, instance):
        reject_if_locked(instance.grid.section.form_template)
        audit_form_change(self.request, "FORM_GRID_COLUMN_DELETED", instance, after={"grid_id": instance.grid_id})
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
        audit_form_change(request, "FORM_GRID_ROW_CREATED", row, after={"grid_id": grid.id})
        return Response({"id": row.id, "row_label": row.row_label, "sort_order": row.sort_order}, status=201)


class GridRowDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsNCAEditor]
    serializer_class = GridRowSerializer
    http_method_names = ["patch", "delete", "head", "options"]

    def get_object(self):
        return generics.get_object_or_404(GridRow, pk=self.kwargs["rid"], grid_id=self.kwargs["gid"])

    def perform_update(self, serializer):
        reject_if_locked(serializer.instance.grid.section.form_template)
        row = serializer.save()
        audit_form_change(self.request, "FORM_GRID_ROW_UPDATED", row, after={"changed_fields": sorted(serializer.validated_data)})

    def perform_destroy(self, instance):
        reject_if_locked(instance.grid.section.form_template)
        audit_form_change(self.request, "FORM_GRID_ROW_DELETED", instance, after={"grid_id": instance.grid_id})
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
