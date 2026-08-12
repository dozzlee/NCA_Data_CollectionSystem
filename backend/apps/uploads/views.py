import os
import hashlib
import magic
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
from apps.users.permissions import IsNCAEditor, IsProviderDataEntry
from .models import SubmissionKMZUpload, SubmissionExcelBackup
from .tasks import scan_private_upload


ALLOWED_KMZ_TYPES = {"application/vnd.google-earth.kmz", "application/zip"}
ALLOWED_EXCEL_TYPES = {
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
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
            return [IsProviderDataEntry()]
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
        if submission.expected.workflow_status not in ("DRAFT", "PROVIDER_CHANGES_REQUESTED", "CORRECTION_REQUESTED"):
            return Response({"detail": "Uploads are only allowed while the submission is editable."}, status=400)
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
    permission_classes = [IsProviderDataEntry]
    parser_classes = [MultiPartParser]

    def post(self, request, pk):
        submission = get_submission_for_user(request.user, pk=pk)
        if submission.expected.workflow_status not in ("DRAFT", "PROVIDER_CHANGES_REQUESTED", "CORRECTION_REQUESTED"):
            return Response({"detail": "Uploads are only allowed while the submission is editable."}, status=400)
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
