from rest_framework import serializers
from .models import GeneratedReport, ReportPreparation, ReportTemplate


class ReportTemplateSerializer(serializers.ModelSerializer):
    latest_period = serializers.SerializerMethodField()
    class Meta:
        model = ReportTemplate
        fields = ["id", "report_type", "name", "version", "effective_year", "effective_quarter", "filename_pattern", "source_reference", "status", "latest_period"]
    def get_latest_period(self, obj):
        latest = obj.preparations.order_by("-year", "-quarter").first()
        return (f"Q{latest.quarter} {latest.year}" if latest and latest.quarter else str(latest.year)) if latest else None


class ReportPreparationSerializer(serializers.ModelSerializer):
    template_name = serializers.CharField(source="template.name", read_only=True)
    template_version = serializers.IntegerField(source="template.version", read_only=True)
    class Meta:
        model = ReportPreparation
        fields = ["id", "report_type", "year", "quarter", "status", "manifest", "template_name", "template_version", "created_at", "expires_at"]


class GeneratedReportSerializer(serializers.ModelSerializer):
    report_type = serializers.CharField(source="preparation.report_type", read_only=True)
    year = serializers.IntegerField(source="preparation.year", read_only=True)
    quarter = serializers.IntegerField(source="preparation.quarter", read_only=True)
    template_version = serializers.IntegerField(source="preparation.template.version", read_only=True)
    generated_by_name = serializers.CharField(source="generated_by.name", read_only=True)
    class Meta:
        model = GeneratedReport
        fields = ["id", "report_type", "year", "quarter", "template_version", "status", "filename", "file_size", "sha256", "validation_result", "error_message", "generated_by_name", "created_at", "completed_at"]

