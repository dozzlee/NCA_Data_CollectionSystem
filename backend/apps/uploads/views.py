import os
import magic
from django.conf import settings
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser

from apps.audit.models import AuditEvent
from apps.forms_engine.models import KMZUploadRequirement, KMZ_ELIGIBLE_FORMS
from apps.submissions.models import Submission
from .models import SubmissionKMZUpload, SubmissionExcelBackup


ALLOWED_KMZ_TYPES = {"application/vnd.google-earth.kmz", "application/zip"}
ALLOWED_EXCEL_TYPES = {
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
}


def save_upload(file, subfolder, filename):
    upload_dir = os.path.join(settings.MEDIA_ROOT, subfolder)
    os.makedirs(upload_dir, exist_ok=True)
    path = os.path.join(upload_dir, filename)
    with open(path, "wb+") as dest:
        for chunk in file.chunks():
            dest.write(chunk)
    return os.path.join(subfolder, filename)


class KMZUploadView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser]

    def get(self, request, pk):
        try:
            submission = Submission.objects.get(pk=pk)
        except Submission.DoesNotExist:
            return Response({"detail": "Not found."}, status=404)

        # Only show KMZ for fibre forms
        if submission.expected.form_template.form_code not in KMZ_ELIGIBLE_FORMS:
            return Response([])

        uploads = SubmissionKMZUpload.objects.filter(submission=submission)
        data = [
            {
                "id": u.id, "file_name": u.file_name, "file_size": u.file_size,
                "requirement_id": u.requirement_id, "review_status": u.review_status,
                "review_note": u.review_note, "uploaded_at": u.uploaded_at,
            }
            for u in uploads
        ]
        return Response(data)

    def post(self, request, pk):
        try:
            submission = Submission.objects.get(pk=pk)
        except Submission.DoesNotExist:
            return Response({"detail": "Not found."}, status=404)

        form_code = submission.expected.form_template.form_code
        if form_code not in KMZ_ELIGIBLE_FORMS:
            return Response(
                {"detail": f"KMZ uploads are only accepted for fibre forms (DC-DBS05, DC-SUB03). This form is {form_code}."},
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
        filename = f"{uuid.uuid4()}_{file.name}"
        path = save_upload(file, f"kmz/{submission.id}", filename)

        upload = SubmissionKMZUpload.objects.create(
            submission=submission,
            requirement=requirement,
            file_name=file.name,
            file_size=file.size,
            storage_path=path,
            uploaded_by=request.user,
        )

        AuditEvent.objects.create(
            user=request.user, user_email=request.user.email, role=request.user.role,
            organization=request.user.organization.name if request.user.organization else "",
            action="KMZ_UPLOADED", entity_type="SubmissionKMZUpload", entity_id=str(upload.id),
            after_value={"file_name": file.name, "submission_id": pk},
        )
        return Response({"id": upload.id, "file_name": upload.file_name, "review_status": upload.review_status}, status=201)


class KMZDownloadView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk, uid):
        try:
            submission = Submission.objects.get(pk=pk)
            upload = SubmissionKMZUpload.objects.get(pk=uid, submission=submission)
        except (Submission.DoesNotExist, SubmissionKMZUpload.DoesNotExist):
            return Response({"detail": "Not found."}, status=404)

        from django.http import FileResponse
        import os
        full_path = os.path.join(settings.MEDIA_ROOT, upload.storage_path)
        if not os.path.exists(full_path):
            return Response({"detail": "File not found on disk."}, status=404)
        return FileResponse(open(full_path, "rb"), as_attachment=True, filename=upload.file_name)


class KMZReviewView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk, uid):
        try:
            submission = Submission.objects.get(pk=pk)
            upload = SubmissionKMZUpload.objects.get(pk=uid, submission=submission)
        except (Submission.DoesNotExist, SubmissionKMZUpload.DoesNotExist):
            return Response({"detail": "Not found."}, status=404)

        new_status = request.data.get("review_status")
        if new_status not in ("ACCEPTED", "REJECTED"):
            return Response({"detail": "review_status must be ACCEPTED or REJECTED."}, status=400)

        upload.review_status = new_status
        upload.review_note = request.data.get("review_note", "")
        upload.save(update_fields=["review_status", "review_note"])

        AuditEvent.objects.create(
            user=request.user, user_email=request.user.email, role=request.user.role,
            organization=request.user.organization.name if request.user.organization else "",
            action=f"KMZ_{new_status}", entity_type="SubmissionKMZUpload", entity_id=str(upload.id),
            after_value={"review_status": new_status, "review_note": upload.review_note},
            ip_address=request.META.get("REMOTE_ADDR"),
        )
        return Response({"id": upload.id, "review_status": upload.review_status, "review_note": upload.review_note})


class ExcelBackupListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            submission = Submission.objects.get(pk=pk)
        except Submission.DoesNotExist:
            return Response({"detail": "Not found."}, status=404)
        backups = SubmissionExcelBackup.objects.filter(submission=submission).order_by("-uploaded_at")
        return Response([
            {
                "id": b.id, "file_name": b.file_name, "file_size": b.file_size,
                "uploaded_at": b.uploaded_at, "source_control_status": b.source_control_status,
            }
            for b in backups
        ])


class ExcelBackupUploadView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser]

    def post(self, request, pk):
        try:
            submission = Submission.objects.get(pk=pk)
        except Submission.DoesNotExist:
            return Response({"detail": "Not found."}, status=404)

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
        filename = f"{uuid.uuid4()}_{file.name}"
        path = save_upload(file, f"excel_backup/{submission.id}", filename)

        backup = SubmissionExcelBackup.objects.create(
            submission=submission,
            file_name=file.name,
            file_size=file.size,
            storage_path=path,
            uploaded_by=request.user,
        )
        return Response({"id": backup.id, "file_name": backup.file_name, "note": "Stored for source control only. Not analyzed."}, status=201)
