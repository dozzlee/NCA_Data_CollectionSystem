import os
import threading
from celery import shared_task
from django.conf import settings
from django.db import close_old_connections
from django.utils import timezone
from apps.audit.services import record_audit
from .models import SubmissionKMZUpload, SubmissionExcelBackup, SubmissionFieldAttachment, SubmissionExcelImport
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


@shared_task(bind=True, max_retries=3)
def process_excel_import(self, import_id):
    """Scan, parse and match an XLSX import without exposing the private file."""
    item = SubmissionExcelImport.objects.select_related("backup", "uploaded_by", "submission__expected__form_template").get(pk=import_id)
    try:
        result = scan_path(os.path.join(settings.PRIVATE_UPLOAD_ROOT, item.backup.storage_path))
        backup = item.backup
        backup.scan_status = result["status"]
        backup.scan_engine = result["engine"]
        backup.scan_details = result["details"]
        backup.scanned_at = timezone.now()
        backup.save(update_fields=["scan_status", "scan_engine", "scan_details", "scanned_at"])
        record_audit(user=item.uploaded_by, action=f"EXCEL_IMPORT_SCAN_{result['status']}", entity_type="SubmissionExcelImport", entity_id=item.id, after=result)
        if result["status"] != "CLEAN":
            item.status = "FAILED"
            item.errors = [{"code": "SCAN_FAILED", "message": result["details"]}]
            item.save(update_fields=["status", "errors", "updated_at"])
            return result
        item.status = "PARSING"
        item.save(update_fields=["status", "updated_at"])
        from .excel_imports import parse_and_match
        parse_and_match(item)
        record_audit(user=item.uploaded_by, action="EXCEL_IMPORT_PARSED", entity_type="SubmissionExcelImport", entity_id=item.id, after={"summary": item.summary})
        return {"status": "READY", "import_id": item.id}
    except Exception as exc:
        item.status = "FAILED"
        item.errors = [{"code": "PROCESSING_FAILED", "message": str(exc)}]
        item.save(update_fields=["status", "errors", "updated_at"])
        record_audit(user=item.uploaded_by, action="EXCEL_IMPORT_FAILED", entity_type="SubmissionExcelImport", entity_id=item.id, after={"error": str(exc)})
        raise self.retry(exc=exc)


def enqueue_excel_import(import_id):
    """Queue parsing without keeping the upload HTTP request open.

    Celery's eager development mode normally executes ``delay`` inline. Large
    workbooks can then outlive the frontend proxy request and surface as the
    unhelpful browser error "Failed to fetch" even though the file was saved.
    Use a short-lived background thread only for local eager mode; deployed
    environments continue to use the configured Celery worker.
    """
    if settings.CELERY_TASK_ALWAYS_EAGER:
        def run():
            close_old_connections()
            try:
                process_excel_import.apply(args=[import_id], throw=False)
            finally:
                close_old_connections()

        threading.Thread(
            target=run,
            name=f"excel-import-{import_id}",
            daemon=True,
        ).start()
        return
    process_excel_import.delay(import_id)
