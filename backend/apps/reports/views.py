import os
import uuid
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.services import record_audit
from apps.users.permissions import IsNCAEditor
from .models import GeneratedReport, ReportPreparation, ReportTemplate
from .serializers import GeneratedReportSerializer, ReportPreparationSerializer, ReportTemplateSerializer
from .services import generate_report, period_context, prepare_report


class ReportDefinitionListView(APIView):
    permission_classes = [IsNCAEditor]
    def get(self, request):
        rows = ReportTemplate.objects.filter(status="ACTIVE").order_by("report_type")
        return Response({"results": ReportTemplateSerializer(rows, many=True).data})


class ReportPeriodsView(APIView):
    permission_classes = [IsNCAEditor]
    def get(self, request):
        report_type = request.query_params.get("report_type")
        from apps.submissions.models import ReportingPeriod
        years = sorted(set(ReportingPeriod.objects.values_list("year", flat=True)), reverse=True)
        return Response({"report_type": report_type, "years": years, "quarters": [1, 2, 3, 4] if report_type == "QUARTERLY_BULLETIN" else []})


class ReportPrepareView(APIView):
    permission_classes = [IsNCAEditor]
    def post(self, request):
        report_type = request.data.get("report_type"); year = request.data.get("year"); quarter = request.data.get("quarter")
        if report_type not in dict(ReportTemplate.REPORT_TYPES): return Response({"detail": "Choose a valid report type."}, status=400)
        try: year = int(year)
        except (TypeError, ValueError): return Response({"detail": "Year is required."}, status=400)
        if report_type == "QUARTERLY_BULLETIN":
            try: quarter = int(quarter); period_context(report_type, year, quarter)
            except (TypeError, ValueError): return Response({"detail": "Quarter must be between 1 and 4."}, status=400)
        else: quarter = None
        try: row = prepare_report(report_type=report_type, year=year, quarter=quarter, user=request.user)
        except ValueError as exc: return Response({"detail": str(exc)}, status=409)
        record_audit(user=request.user, action="REPORT_PREPARED", entity_type="ReportPreparation", entity_id=row.id,
            after={"report_type": report_type, "year": year, "quarter": quarter, "status": row.status})
        return Response(ReportPreparationSerializer(row).data, status=201)


class ReportPreparationDetailView(APIView):
    permission_classes = [IsNCAEditor]
    def get(self, request, pk): return Response(ReportPreparationSerializer(get_object_or_404(ReportPreparation, pk=pk)).data)


class ReportGenerateView(APIView):
    permission_classes = [IsNCAEditor]
    def post(self, request, pk):
        preparation = get_object_or_404(ReportPreparation, pk=pk)
        try: key = uuid.UUID(str(request.data.get("idempotency_key")))
        except (ValueError, TypeError): return Response({"detail": "A valid idempotency_key is required."}, status=400)
        try: result = generate_report(preparation, request.user, key)
        except ValueError as exc: return Response({"detail": str(exc)}, status=409)
        record_audit(user=request.user, action="REPORT_GENERATED", entity_type="GeneratedReport", entity_id=result.id,
            after={"report_type": preparation.report_type, "year": preparation.year, "quarter": preparation.quarter, "template_version": preparation.template.version, "validation_passed": True})
        return Response(GeneratedReportSerializer(result).data, status=201)


class GeneratedReportListView(APIView):
    permission_classes = [IsNCAEditor]
    def get(self, request): return Response({"results": GeneratedReportSerializer(GeneratedReport.objects.select_related("preparation__template", "generated_by"), many=True).data})


class GeneratedReportDownloadView(APIView):
    permission_classes = [IsNCAEditor]
    def get(self, request, pk):
        row = get_object_or_404(GeneratedReport, pk=pk, status="READY")
        if not row.private_path or not os.path.exists(row.private_path): return Response({"detail": "The report file is unavailable."}, status=404)
        record_audit(user=request.user, action="REPORT_DOWNLOADED", entity_type="GeneratedReport", entity_id=row.id, after={"filename": row.filename})
        return FileResponse(open(row.private_path, "rb"), content_type="application/pdf", as_attachment=True, filename=row.filename)

