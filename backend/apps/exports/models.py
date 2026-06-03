from django.db import models


class ExportLog(models.Model):
    EXPORT_TYPE_CHOICES = [
        ("CSV", "CSV"),
        ("PDF", "PDF"),
    ]

    export_type = models.CharField(max_length=5, choices=EXPORT_TYPE_CHOICES)
    filters = models.JSONField(default=dict)
    generated_by = models.ForeignKey("users.User", on_delete=models.PROTECT)
    generated_at = models.DateTimeField(auto_now_add=True)
    file_reference = models.CharField(max_length=500, blank=True)
    row_count = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.export_type} export by {self.generated_by} at {self.generated_at}"

    class Meta:
        ordering = ["-generated_at"]
