from celery import shared_task
from django.utils import timezone
from .models import DataRequest
from .serializers import add_event
from .services import generate_artifact


@shared_task(bind=True, max_retries=2)
def generate_data_request(self, request_id):
    item = DataRequest.objects.select_related("reviewer", "requester").get(pk=request_id)
    old = item.status; item.status = "PREPARING"; item.save(update_fields=["status", "updated_at"])
    try:
        artifact = generate_artifact(item, item.reviewer)
        item.status = "READY"; item.completed_at = timezone.now(); item.projected_row_count = artifact.row_count
        item.save(update_fields=["status", "completed_at", "projected_row_count", "updated_at"])
        add_event(item, item.reviewer, "FILE_READY", old, "READY", "Your approved file is ready to download.", notify=True)
    except Exception as exc:
        item.status = "GENERATION_FAILED"; item.save(update_fields=["status", "updated_at"])
        add_event(item, item.reviewer, "GENERATION_FAILED", old, "GENERATION_FAILED", "File generation failed. An administrator can retry.", {"error": str(exc)}, notify=True)
        raise
