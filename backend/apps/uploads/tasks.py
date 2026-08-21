import os
from celery import shared_task
from django.conf import settings
from django.utils import timezone
from apps.audit.services import record_audit
from .models import SubmissionKMZUpload, SubmissionExcelBackup, SubmissionFieldAttachment
from .scanner import scan_path


@shared_task(bind=True, max_retries=3)
def scan_private_upload(self, model_name, object_id):
    models = {"KMZ": SubmissionKMZUpload, "EXCEL": SubmissionExcelBackup, "ATTACHMENT": SubmissionFieldAttachment}
    model = models[model_name]
    upload=model.objects.select_related("uploaded_by").get(pk=object_id)
    try:
        result=scan_path(os.path.join(settings.PRIVATE_UPLOAD_ROOT,upload.storage_path))
        upload.scan_status=result["status"];upload.scan_engine=result["engine"];upload.scan_details=result["details"];upload.scanned_at=timezone.now();upload.save()
        record_audit(user=upload.uploaded_by,action=f"PRIVATE_UPLOAD_SCAN_{result['status']}",entity_type=model.__name__,entity_id=upload.id,after=result)
        return result
    except Exception as exc:
        upload.scan_status="ERROR";upload.scan_engine="clamav";upload.scan_details=str(exc);upload.scanned_at=timezone.now();upload.save()
        record_audit(user=upload.uploaded_by,action="PRIVATE_UPLOAD_SCAN_ERROR",entity_type=model.__name__,entity_id=upload.id,after={"error":str(exc)})
        raise self.retry(exc=exc)
