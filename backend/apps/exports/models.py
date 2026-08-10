from django.db import models


class ExportLog(models.Model):
    EXPORT_TYPE_CHOICES = [
        ("CSV", "CSV"),
        ("XLSX", "Excel"),
        ("PDF", "PDF"),
    ]

    export_type = models.CharField(max_length=5, choices=EXPORT_TYPE_CHOICES)
    data_request_id = models.CharField(max_length=36, blank=True, db_index=True)
    filters = models.JSONField(default=dict)
    generated_by = models.ForeignKey("users.User", on_delete=models.PROTECT)
    generated_at = models.DateTimeField(auto_now_add=True)
    file_reference = models.CharField(max_length=500, blank=True)
    row_count = models.PositiveIntegerField(default=0)
    mime_type = models.CharField(max_length=100, blank=True)
    file_size = models.PositiveBigIntegerField(default=0)
    sha256 = models.CharField(max_length=64, blank=True)

    def __str__(self):
        return f"{self.export_type} export by {self.generated_by} at {self.generated_at}"

    class Meta:
        ordering = ["-generated_at"]
