from celery import shared_task
from django.db import transaction
from django.utils import timezone
from .models import DataRequest
from .serializers import add_event
from .services import generate_artifact


@shared_task(bind=True, max_retries=2)
def generate_data_request(self, request_id):
    try:
        with transaction.atomic():
            item = DataRequest.objects.select_for_update().select_related("reviewer", "requester").get(pk=request_id)
            if item.status == "READY":
                return {"status": "READY", "request_id": str(item.id)}
            if item.status not in {"APPROVED", "PREPARING", "GENERATION_FAILED"}:
                return {"status": "SKIPPED", "request_id": str(item.id)}
            old = item.status
            if item.status != "PREPARING":
                item.status = "PREPARING"
                item.save(update_fields=["status", "updated_at"])
            artifact = generate_artifact(item, item.reviewer)
            item.status = "READY"; item.completed_at = timezone.now(); item.projected_row_count = artifact.row_count
            item.save(update_fields=["status", "completed_at", "projected_row_count", "updated_at"])
            if not item.events.filter(event_type="FILE_READY").exists():
                add_event(item, item.reviewer, "FILE_READY", old, "READY", "Your approved file is ready to download.", notify=True)
            return {"status": "READY", "request_id": str(item.id), "artifact_id": artifact.id}
    except Exception as exc:
        with transaction.atomic():
            item = DataRequest.objects.select_for_update().select_related("reviewer").get(pk=request_id)
            old = item.status
            item.status = "GENERATION_FAILED"; item.save(update_fields=["status", "updated_at"])
            add_event(item, item.reviewer, "GENERATION_FAILED", old, "GENERATION_FAILED", "File generation failed. An administrator can retry.", {"error": str(exc)}, notify=True)
        raise
