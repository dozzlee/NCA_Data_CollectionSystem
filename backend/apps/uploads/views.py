import os
import hashlib
import magic
import uuid
from django.conf import settings
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser

from apps.audit.services import record_audit
from apps.forms_engine.models import KMZUploadRequirement, KMZ_ELIGIBLE_FORMS
from apps.submissions.access import get_submission_for_user
from apps.submissions.readiness import refresh_submission_completion
from apps.users.permissions import IsNCAEditor, IsProviderUser
from apps.submissions.provider_workspace import provider_can_edit
from .models import (
    SubmissionKMZUpload, SubmissionExcelBackup, SubmissionFieldAttachment,
    SubmissionExcelImport, SubmissionExcelImportMatch,
)
from .tasks import enqueue_excel_import, scan_private_upload
from .serializers import SubmissionExcelImportSerializer


ALLOWED_KMZ_TYPES = {"application/vnd.google-earth.kmz", "application/zip"}
ALLOWED_EXCEL_TYPES = {
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
}
ALLOWED_ATTACHMENT_EXTENSIONS = {".doc", ".docx", ".xls", ".xlsx", ".pdf"}
ALLOWED_ATTACHMENT_TYPES = {
    "application/msword", "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/pdf",
    "application/zip", "application/octet-stream",
}


def save_upload(file, subfolder, filename):
    upload_dir = os.path.join(settings.PRIVATE_UPLOAD_ROOT, subfolder)
    os.makedirs(upload_dir, exist_ok=True)
    path = os.path.join(upload_dir, filename)
    digest = hashlib.sha256()
    with open(path, "wb+") as dest:
        for chunk in file.chunks():
            dest.write(chunk)
            digest.update(chunk)
    return os.path.join(subfolder, filename), digest.hexdigest()


class KMZUploadView(APIView):
    parser_classes = [MultiPartParser]

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsProviderUser()]
        return [IsAuthenticated()]

    def get(self, request, pk):
        submission = get_submission_for_user(request.user, pk=pk)

        # Only show KMZ for fibre forms
        if submission.expected.form_template.form_code not in KMZ_ELIGIBLE_FORMS:
            return Response([])

        uploads = SubmissionKMZUpload.objects.filter(submission=submission)
        data = [
            {
                "id": u.id, "file_name": u.file_name, "file_size": u.file_size,
                "requirement_id": u.requirement_id, "review_status": u.review_status,
                "review_note": u.review_note, "uploaded_at": u.uploaded_at,
                "sha256": u.sha256, "scan_status": u.scan_status, "download_ready": u.scan_status == "CLEAN",
            }
            for u in uploads
        ]
        return Response(data)

    def post(self, request, pk):
        submission = get_submission_for_user(request.user, pk=pk)
        if not provider_can_edit(request.user, submission):
            return Response({"detail": "Your provider role cannot upload files at this workflow stage."}, status=403)
        if submission.expected.workflow_status == "CORRECTION_REQUESTED" and not submission.supersedes_id:
            return Response({"detail": "Upload to the linked correction version, not the official historical version."}, status=409)

        form_code = submission.expected.form_template.form_code
        if form_code not in KMZ_ELIGIBLE_FORMS:
            return Response(
                {"detail": f"KMZ uploads are only accepted for Domestic Fibre form DC-DBS05. This form is {form_code}."},
                status=400,
            )

        file = request.FILES.get("file")
        requirement_id = request.data.get("requirement_id")
        if not file or not requirement_id:
            return Response({"detail": "file and requirement_id are required."}, status=400)

        try:
            requirement = KMZUploadRequirement.objects.get(pk=requirement_id, form_template=submission.expected.form_template)
        except KMZUploadRequirement.DoesNotExist:
            return Response({"detail": "Invalid KMZ requirement."}, status=400)

        max_bytes = requirement.max_file_size_mb * 1024 * 1024
        if file.size > max_bytes:
            return Response({"detail": f"File exceeds {requirement.max_file_size_mb}MB limit."}, status=400)

        mime = magic.from_buffer(file.read(2048), mime=True)
        file.seek(0)
        if mime not in ALLOWED_KMZ_TYPES and not file.name.lower().endswith(".kmz"):
            return Response({"detail": "Only .kmz files are accepted."}, status=400)

        import uuid
        original_name = os.path.basename(file.name)
        filename = f"{uuid.uuid4()}_{original_name}"
        path, digest = save_upload(file, f"kmz/{submission.id}", filename)

        upload = SubmissionKMZUpload.objects.create(
            submission=submission,
            requirement=requirement,
            file_name=original_name,
            file_size=file.size,
            storage_path=path,
            uploaded_by=request.user,
            sha256=digest,
        )

        record_audit(user=request.user, action="KMZ_UPLOADED", entity_type="SubmissionKMZUpload", entity_id=upload.id,
            after={"file_name": original_name, "submission_id": pk, "sha256": digest})
        refresh_submission_completion(submission)
        scan_private_upload.delay("KMZ", upload.id)
        return Response({"id": upload.id, "file_name": upload.file_name, "review_status": upload.review_status}, status=201)


class KMZDownloadView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk, uid):
        submission = get_submission_for_user(request.user, pk=pk)
        try:
            upload = SubmissionKMZUpload.objects.get(pk=uid, submission=submission)
        except SubmissionKMZUpload.DoesNotExist:
            return Response({"detail": "Not found."}, status=404)

        from django.http import FileResponse
        import os
        if upload.scan_status != "CLEAN":
            return Response({"detail": "File is quarantined until malware scanning succeeds."}, status=423)
        full_path = os.path.join(settings.PRIVATE_UPLOAD_ROOT, upload.storage_path)
        if not os.path.exists(full_path):
            return Response({"detail": "File not found on disk."}, status=404)
        record_audit(user=request.user,action="KMZ_DOWNLOADED",entity_type="SubmissionKMZUpload",entity_id=upload.id,ip_address=request.META.get("REMOTE_ADDR"))
        return FileResponse(open(full_path, "rb"), as_attachment=True, filename=upload.file_name)


class KMZReviewView(APIView):
    permission_classes = [IsNCAEditor]

    def patch(self, request, pk, uid):
        submission = get_submission_for_user(request.user, pk=pk)
        try:
            upload = SubmissionKMZUpload.objects.get(pk=uid, submission=submission)
        except SubmissionKMZUpload.DoesNotExist:
            return Response({"detail": "Not found."}, status=404)

        new_status = request.data.get("review_status")
        if new_status not in ("ACCEPTED", "REJECTED"):
            return Response({"detail": "review_status must be ACCEPTED or REJECTED."}, status=400)

        if upload.scan_status != "CLEAN":
            return Response({"detail": "A quarantined or unscanned file cannot be reviewed."}, status=409)
        upload.review_status = new_status
        upload.review_note = request.data.get("review_note", "")
        upload.reviewed_by = request.user; upload.reviewed_at = timezone.now()
        upload.save(update_fields=["review_status", "review_note", "reviewed_by", "reviewed_at"])

        record_audit(user=request.user, action=f"KMZ_{new_status}", entity_type="SubmissionKMZUpload", entity_id=upload.id,
            after={"review_status": new_status, "review_note": upload.review_note}, ip_address=request.META.get("REMOTE_ADDR"))
        return Response({"id": upload.id, "review_status": upload.review_status, "review_note": upload.review_note})


class ExcelBackupListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        submission = get_submission_for_user(request.user, pk=pk)
        backups = SubmissionExcelBackup.objects.filter(submission=submission).order_by("-uploaded_at")
        return Response([
            {
                "id": b.id, "file_name": b.file_name, "file_size": b.file_size,
                "uploaded_at": b.uploaded_at, "source_control_status": b.source_control_status,
                "sha256": b.sha256, "scan_status": b.scan_status, "download_ready": b.scan_status == "CLEAN",
            }
            for b in backups
        ])


class ExcelBackupUploadView(APIView):
    permission_classes = [IsProviderUser]
    parser_classes = [MultiPartParser]

    def post(self, request, pk):
        submission = get_submission_for_user(request.user, pk=pk)
        if not provider_can_edit(request.user, submission):
            return Response({"detail": "Your provider role cannot upload files at this workflow stage."}, status=403)
        if submission.expected.workflow_status == "CORRECTION_REQUESTED" and not submission.supersedes_id:
            return Response({"detail": "Upload to the linked correction version, not the official historical version."}, status=409)

        file = request.FILES.get("file")
        if not file:
            return Response({"detail": "file is required."}, status=400)

        mime = magic.from_buffer(file.read(2048), mime=True)
        file.seek(0)
        if mime not in ALLOWED_EXCEL_TYPES and not file.name.lower().endswith((".xlsx", ".xls")):
            return Response({"detail": "Only .xlsx or .xls files are accepted for Excel backup."}, status=400)

        max_bytes = settings.MAX_EXCEL_BACKUP_MB * 1024 * 1024 if hasattr(settings, 'MAX_EXCEL_BACKUP_MB') else 50 * 1024 * 1024
        if file.size > max_bytes:
            return Response({"detail": "File exceeds 50MB limit."}, status=400)

        import uuid
        original_name = os.path.basename(file.name)
        filename = f"{uuid.uuid4()}_{original_name}"
        path, digest = save_upload(file, f"excel_backup/{submission.id}", filename)

        previous = SubmissionExcelBackup.objects.filter(
            submission=submission, source_control_status="STORED"
        )
        superseded_ids = list(previous.values_list("id", flat=True))
        previous.update(source_control_status="SUPERSEDED")
        backup = SubmissionExcelBackup.objects.create(
            submission=submission,
            file_name=original_name,
            file_size=file.size,
            storage_path=path,
            uploaded_by=request.user,
            sha256=digest,
        )
        scan_private_upload.delay("EXCEL", backup.id)
        record_audit(user=request.user,action="EXCEL_BACKUP_UPLOADED",entity_type="SubmissionExcelBackup",entity_id=backup.id,
            after={"sha256":digest,"superseded_backup_ids":superseded_ids})
        return Response({"id": backup.id, "file_name": backup.file_name, "note": "Stored for source control only. Not analyzed."}, status=201)


class ExcelBackupDownloadView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self,request,pk,bid):
        submission=get_submission_for_user(request.user,pk=pk)
        try: backup=SubmissionExcelBackup.objects.get(pk=bid,submission=submission)
        except SubmissionExcelBackup.DoesNotExist: return Response({"detail":"Not found."},status=404)
        if backup.scan_status!="CLEAN": return Response({"detail":"File is quarantined until malware scanning succeeds."},status=423)
        from django.http import FileResponse
        full_path=os.path.join(settings.PRIVATE_UPLOAD_ROOT,backup.storage_path)
        if not os.path.exists(full_path): return Response({"detail":"File not found on disk."},status=404)
        record_audit(user=request.user,action="EXCEL_BACKUP_DOWNLOADED",entity_type="SubmissionExcelBackup",entity_id=backup.id)
        return FileResponse(open(full_path,"rb"),as_attachment=True,filename=backup.file_name)


class FieldAttachmentView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser]

    def get(self, request, pk, field_id=None):
        submission = get_submission_for_user(request.user, pk=pk)
        uploads = SubmissionFieldAttachment.objects.filter(submission=submission, is_current=True)
        if field_id is not None:
            uploads = uploads.filter(field_id=field_id)
        return Response([{
            "id": item.id, "field_id": item.field_id, "file_name": item.file_name,
            "file_size": item.file_size, "mime_type": item.mime_type, "sha256": item.sha256,
            "scan_status": item.scan_status, "uploaded_at": item.uploaded_at,
            "download_ready": item.scan_status == "CLEAN",
        } for item in uploads])

    def post(self, request, pk, field_id=None):
        submission = get_submission_for_user(request.user, pk=pk)
        if not provider_can_edit(request.user, submission):
            return Response({"detail": "Your provider role cannot upload files at this workflow stage."}, status=403)
        from apps.forms_engine.models import FormField
        field = FormField.objects.filter(pk=field_id, section__form_template=submission.expected.form_template, field_type="attachment").first()
        if not field:
            return Response({"detail": "The selected indicator is not an attachment field."}, status=400)
        file = request.FILES.get("file")
        if not file:
            return Response({"detail": "file is required."}, status=400)
        extension = os.path.splitext(file.name)[1].lower()
        mime = magic.from_buffer(file.read(4096), mime=True); file.seek(0)
        if extension not in ALLOWED_ATTACHMENT_EXTENSIONS or mime not in ALLOWED_ATTACHMENT_TYPES:
            return Response({"detail": "Only Word (.doc/.docx), Excel (.xls/.xlsx), or PDF files are accepted."}, status=400)
        if file.size > 20 * 1024 * 1024:
            return Response({"detail": "Attachment exceeds the 20 MB limit."}, status=400)
        import uuid
        original_name = os.path.basename(file.name)
        path, digest = save_upload(file, f"field_attachments/{submission.id}", f"{uuid.uuid4()}_{original_name}")
        SubmissionFieldAttachment.objects.filter(submission=submission, field=field, is_current=True).update(is_current=False)
        item = SubmissionFieldAttachment.objects.create(submission=submission, field=field, file_name=original_name,
            file_size=file.size, mime_type=mime, storage_path=path, sha256=digest, uploaded_by=request.user)
        record_audit(user=request.user, action="FIELD_ATTACHMENT_UPLOADED", entity_type="SubmissionFieldAttachment",
            entity_id=item.id, after={"submission_id": submission.id, "field_id": field.id, "file_name": original_name, "sha256": digest})
        scan_private_upload.delay("ATTACHMENT", item.id)
        return Response({"id": item.id, "field_id": field.id, "file_name": original_name, "scan_status": item.scan_status}, status=201)


class FieldAttachmentDownloadView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk, uid):
        submission = get_submission_for_user(request.user, pk=pk)
        item = SubmissionFieldAttachment.objects.filter(pk=uid, submission=submission).first()
        if not item:
            return Response({"detail": "Attachment not found."}, status=404)
        if item.scan_status != "CLEAN":
            return Response({"detail": "File is quarantined until malware scanning succeeds."}, status=423)
        full_path = os.path.join(settings.PRIVATE_UPLOAD_ROOT, item.storage_path)
        if not os.path.exists(full_path):
            return Response({"detail": "File not found on disk."}, status=404)
        from django.http import FileResponse
        record_audit(user=request.user, action="FIELD_ATTACHMENT_DOWNLOADED", entity_type="SubmissionFieldAttachment", entity_id=item.id)
        return FileResponse(open(full_path, "rb"), as_attachment=True, filename=item.file_name, content_type=item.mime_type)


def _excel_import_for_user(user, import_id):
    item = SubmissionExcelImport.objects.select_related(
        "submission__expected__provider", "submission__expected__form_template", "backup", "uploaded_by",
    ).prefetch_related("matches__field", "matches__grid", "matches__grid_column").filter(pk=import_id).first()
    if not item:
        return None
    # Reuse the canonical tenant/role access check; it raises a consistent 404
    # for submissions outside the caller's scope.
    get_submission_for_user(user, pk=item.submission_id)
    return item


class SubmissionExcelImportListCreateView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser]

    def get(self, request, pk):
        submission = get_submission_for_user(request.user, pk=pk)
        items = SubmissionExcelImport.objects.filter(submission=submission).select_related("backup", "uploaded_by")
        return Response(SubmissionExcelImportSerializer(items, many=True, context={"include_matches": False}).data)

    def post(self, request, pk):
        submission = get_submission_for_user(request.user, pk=pk)
        if not request.user.is_provider or not provider_can_edit(request.user, submission):
            return Response({"detail": "Your provider role cannot import Excel data at this workflow stage."}, status=403)
        upload = request.FILES.get("file")
        if not upload:
            return Response({"detail": "file is required."}, status=400)
        if not upload.name.lower().endswith(".xlsx"):
            return Response({"detail": "Only .xlsx workbooks are accepted for form import."}, status=400)
        mime = magic.from_buffer(upload.read(4096), mime=True); upload.seek(0)
        if mime not in {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "application/zip", "application/octet-stream"}:
            return Response({"detail": "The uploaded file is not a valid .xlsx workbook."}, status=400)
        max_bytes = getattr(settings, "MAX_EXCEL_BACKUP_MB", 50) * 1024 * 1024
        if upload.size > max_bytes:
            return Response({"detail": f"File exceeds the {getattr(settings, 'MAX_EXCEL_BACKUP_MB', 50)} MB limit."}, status=400)
        original_name = os.path.basename(upload.name)
        path, digest = save_upload(upload, f"excel_backup/{submission.id}", f"{uuid.uuid4()}_{original_name}")
        backup = SubmissionExcelBackup.objects.create(
            submission=submission, file_name=original_name, file_size=upload.size,
            storage_path=path, uploaded_by=request.user, sha256=digest,
        )
        item = SubmissionExcelImport.objects.create(
            submission=submission, backup=backup, uploaded_by=request.user,
            source_revision=submission.revision,
        )
        record_audit(
            user=request.user, action="EXCEL_IMPORT_UPLOADED", entity_type="SubmissionExcelImport", entity_id=item.id,
            after={"submission_id": submission.id, "file_name": original_name, "sha256": digest, "source_revision": submission.revision},
        )
        enqueue_excel_import(item.id)
        return Response(SubmissionExcelImportSerializer(item, context={"include_matches": False}).data, status=201)


class SubmissionExcelImportDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        item = _excel_import_for_user(request.user, pk)
        if not item:
            return Response({"detail": "Import not found."}, status=404)
        return Response(SubmissionExcelImportSerializer(
            item, context={"request": request, "include_matches": True},
        ).data)


class SubmissionExcelImportMatchesView(APIView):
    permission_classes = [IsProviderUser]

    def patch(self, request, pk):
        item = _excel_import_for_user(request.user, pk)
        if not item:
            return Response({"detail": "Import not found."}, status=404)
        if not provider_can_edit(request.user, item.submission):
            return Response({"detail": "This import is no longer editable."}, status=403)
        if item.status != "READY":
            return Response({"detail": "Mappings can be changed only after parsing is complete."}, status=409)
        decisions = request.data.get("matches", [])
        if not isinstance(decisions, list):
            return Response({"detail": "matches must be a list."}, status=400)
        from apps.forms_engine.models import FormField, FormGrid, GridColumn, GridRow
        from .excel_imports import _convert
        for decision in decisions:
            match = item.matches.filter(pk=decision.get("id")).first()
            if not match:
                return Response({"detail": "A selected import row does not belong to this import."}, status=400)
            if decision.get("action") == "SKIP":
                match.status = "SKIPPED"; match.user_confirmed = True
                match.decision_note = str(decision.get("note") or "Explicitly skipped by uploader")
                match.save(update_fields=["status", "user_confirmed", "decision_note"])
                continue
            target_type = decision.get("target_type")
            target = None
            if target_type == "FIELD":
                field = FormField.objects.filter(pk=decision.get("field"), section__form_template=item.submission.expected.form_template).first()
                if field:
                    target = {"target_type": "FIELD", "target_key": f"field:{field.section.section_code}:{field.field_code}".lower(),
                              "field": field, "grid": None, "grid_column": None, "grid_row_id": "", "field_type": field.field_type,
                              "options": list(field.options.values_list("value", flat=True))}
            elif target_type == "GRID_CELL":
                grid = FormGrid.objects.filter(pk=decision.get("grid"), section__form_template=item.submission.expected.form_template).first()
                column = GridColumn.objects.filter(pk=decision.get("grid_column"), grid=grid).first() if grid else None
                row_id = str(decision.get("grid_row_id") or "")
                row = GridRow.objects.filter(pk=row_id, grid=grid).first() if row_id.isdigit() and grid else None
                if grid and column and row_id and (grid.row_mode == "REPEATABLE" or row):
                    row_label = row.row_label if row else row_id
                    target = {"target_type": "GRID_CELL", "target_key": f"grid:{grid.section.section_code}:{grid.grid_code}:{row_label}:{column.column_code}".lower(),
                              "field": None, "grid": grid, "grid_column": column, "grid_row_id": row_id,
                              "field_type": column.field_type, "options": []}
            if not target:
                return Response({"detail": "Select a valid target belonging to this form."}, status=400)
            duplicate = item.matches.filter(status="MATCHED", target_key=target["target_key"]).exclude(pk=match.pk).exists()
            if duplicate:
                return Response({"detail": "Another workbook indicator is already mapped to that form target."}, status=409)
            converted, error = _convert(match.raw_value, target)
            if error:
                return Response({"detail": error}, status=400)
            current = ""
            if target["field"]:
                current = item.submission.values.filter(field=target["field"]).values_list("value", flat=True).first() or ""
            else:
                current = item.submission.values.filter(grid=target["grid"], grid_row_id=target["grid_row_id"], grid_column=target["grid_column"]).values_list("value", flat=True).first() or ""
            match.status = "MATCHED"; match.target_type = target_type; match.target_key = target["target_key"]
            match.field = target["field"]; match.grid = target["grid"]; match.grid_column = target["grid_column"]
            match.grid_row_id = target["grid_row_id"]; match.converted_value = converted
            match.current_value = current; match.will_overwrite = bool(current and current != converted)
            match.user_confirmed = True; match.decision_note = str(decision.get("note") or "Confirmed by uploader")
            match.save()
        return Response(SubmissionExcelImportSerializer(item).data)


class SubmissionExcelImportConfirmView(APIView):
    permission_classes = [IsProviderUser]

    def post(self, request, pk):
        item = _excel_import_for_user(request.user, pk)
        if not item:
            return Response({"detail": "Import not found."}, status=404)
        try:
            confirmation_key = uuid.UUID(str(request.data.get("confirmation_key") or uuid.uuid4()))
        except (TypeError, ValueError):
            return Response({"detail": "confirmation_key must be a UUID."}, status=400)
        try:
            from .excel_imports import confirm_import
            item, replayed = confirm_import(
                item, request.user, confirmation_key=confirmation_key,
                overwrite_ids=request.data.get("overwrite_match_ids", []),
                allow_unresolved=bool(request.data.get("allow_unresolved", False)),
            )
        except PermissionError as exc:
            return Response({"detail": str(exc)}, status=403)
        except RuntimeError as exc:
            return Response({"code": "STALE_IMPORT_PREVIEW", "detail": str(exc)}, status=409)
        except (ValueError, TypeError) as exc:
            return Response({"detail": str(exc)}, status=400)
        record_audit(
            user=request.user, action="EXCEL_IMPORT_CONFIRMED", entity_type="SubmissionExcelImport", entity_id=item.id,
            after={"submission_id": item.submission_id, "resulting_revision": item.resulting_revision,
                   "imported_manifest": item.imported_manifest, "replayed": replayed},
        )
        return Response({**SubmissionExcelImportSerializer(item).data, "replayed": replayed})


class SubmissionExcelImportReparseView(APIView):
    permission_classes = [IsProviderUser]

    def post(self, request, pk):
        item = _excel_import_for_user(request.user, pk)
        if not item:
            return Response({"detail": "Import not found."}, status=404)
        if not provider_can_edit(request.user, item.submission):
            return Response({"detail": "This submission is not editable."}, status=403)
        if item.status == "IMPORTED":
            return Response({"detail": "A confirmed import is immutable."}, status=409)
        item.source_revision = item.submission.revision
        item.status = "PARSING"
        item.errors = []
        item.save(update_fields=["source_revision", "status", "errors", "updated_at"])
        enqueue_excel_import(item.id)
        return Response(SubmissionExcelImportSerializer(item).data)
