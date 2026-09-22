from rest_framework import serializers

from .models import SubmissionExcelImport, SubmissionExcelImportMatch


class SubmissionExcelImportMatchSerializer(serializers.ModelSerializer):
    target_label = serializers.SerializerMethodField()

    def get_target_label(self, obj):
        if obj.field_id:
            return obj.field.label
        if obj.grid_id and obj.grid_column_id:
            return f"{obj.grid.title} / {obj.grid_column.label}"
        return ""

    class Meta:
        model = SubmissionExcelImportMatch
        fields = [
            "id", "source_locator", "source_sheet", "source_row", "source_column",
            "indicator_code", "indicator_name", "definition", "source_data_type", "raw_value",
            "converted_value", "status", "score", "evidence", "target_type", "target_key",
            "field", "grid", "grid_row_id", "grid_column", "target_label", "current_value",
            "will_overwrite", "user_confirmed", "decision_note",
        ]


class SubmissionExcelImportSerializer(serializers.ModelSerializer):
    file_name = serializers.CharField(source="backup.file_name", read_only=True)
    file_size = serializers.IntegerField(source="backup.file_size", read_only=True)
    sha256 = serializers.CharField(source="backup.sha256", read_only=True)
    scan_status = serializers.CharField(source="backup.scan_status", read_only=True)
    uploader_name = serializers.CharField(source="uploaded_by.name", read_only=True)
    matches = serializers.SerializerMethodField()
    matches_meta = serializers.SerializerMethodField()

    def _page(self, obj):
        cached = getattr(self, "_matches_page_cache", None)
        if cached and cached[0] == obj.pk:
            return cached[1], cached[2]
        if not self.context.get("include_matches", False):
            result = (obj.matches.none(), {"count": 0, "page": 1, "page_size": 0, "pages": 0})
            self._matches_page_cache = (obj.pk, *result)
            return result
        request = self.context.get("request")
        params = getattr(request, "query_params", getattr(request, "GET", {}))
        try:
            page = max(int(params.get("page", 1)), 1)
            page_size = min(max(int(params.get("page_size", 50)), 1), 100)
        except (TypeError, ValueError):
            page, page_size = 1, 50
        rows = obj.matches.select_related("field", "grid", "grid_column")
        status_filter = params.get("status", "") if request else ""
        if status_filter:
            rows = rows.filter(status=status_filter)
        count = rows.count()
        start = (page - 1) * page_size
        result = (rows[start:start + page_size], {
            "count": count, "page": page, "page_size": page_size,
            "pages": (count + page_size - 1) // page_size,
        })
        self._matches_page_cache = (obj.pk, *result)
        return result

    def get_matches(self, obj):
        rows, _ = self._page(obj)
        return SubmissionExcelImportMatchSerializer(rows, many=True).data

    def get_matches_meta(self, obj):
        _, meta = self._page(obj)
        return meta

    class Meta:
        model = SubmissionExcelImport
        fields = [
            "id", "submission", "status", "parser_version", "matcher_version", "layout_fingerprint",
            "source_revision", "summary", "errors", "imported_manifest", "mapping_profile",
            "uploaded_by", "uploader_name", "confirmed_by", "confirmed_at", "resulting_revision",
            "file_name", "file_size", "sha256", "scan_status", "created_at", "updated_at", "matches", "matches_meta",
        ]
