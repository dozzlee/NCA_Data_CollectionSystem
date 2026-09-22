from datetime import timedelta
from django.utils import timezone
from rest_framework.test import APITestCase
from apps.users.models import User, NCADivision
from apps.forms_engine.models import FormTemplate, FormSection, FormField
from apps.providers.models import ProviderProfile
from apps.submissions.models import ReportingPeriod, ExpectedSubmission, Submission, SubmissionValue
from apps.exports.models import ExportLog
from .models import DataRequest, DataRequestEvent, DataRequestNotification
from .tasks import generate_data_request


class DataRequestWorkflowTests(APITestCase):
    def test_admin_can_approve_dataset_with_attachment(self):
        import tempfile
        from django.core.files.uploadedfile import SimpleUploadedFile
        from django.test import override_settings
        request_id = self.create_request()
        DataRequest.objects.filter(pk=request_id).update(status="UNDER_REVIEW")
        self.client.force_authenticate(self.admin)
        with tempfile.TemporaryDirectory() as root, override_settings(PRIVATE_EXPORT_ROOT=root, MALWARE_SCANNER_REQUIRED=False):
            response = self.client.post(
                f"/api/v1/data-requests/{request_id}/approve/",
                {"delivery_mode": "DATASET_AND_ATTACHMENT", "file": SimpleUploadedFile("notes.pdf", b"%PDF-1.4 notes")},
                format="multipart",
            )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["status"], "APPROVED")
        self.assertEqual(response.data["approval_manifest"]["delivery_mode"], "DATASET_AND_ATTACHMENT")
        self.assertEqual(response.data["approval_manifest"]["delivery_attachment"]["filename"], "notes.pdf")

    def test_admin_upload_releases_extract_without_matching_submissions(self):
        import tempfile
        from django.core.files.uploadedfile import SimpleUploadedFile
        from django.test import override_settings
        request_id = self.create_request()
        DataRequest.objects.filter(pk=request_id).update(status="UNDER_REVIEW", scope={"form_template_ids": [], "period_ids": []})
        url = f"/api/v1/data-requests/{request_id}/approve/"
        self.client.force_authenticate(self.viewer)
        self.assertEqual(self.client.post(url, {}, format="multipart").status_code, 403)
        self.client.force_authenticate(self.admin)
        with tempfile.TemporaryDirectory() as root, override_settings(PRIVATE_EXPORT_ROOT=root, MALWARE_SCANNER_REQUIRED=False):
            response = self.client.post(url, {"file": SimpleUploadedFile("extract.csv", b"indicator,value\nSubscribers,50\n", content_type="text/csv"), "note": "Requested indicators only."}, format="multipart")
            self.assertEqual(response.status_code, 200, response.data)
            self.assertEqual(response.data["status"], "READY")
            self.assertEqual(response.data["artifact"]["filename"], "extract.csv")
            self.client.force_authenticate(self.other)
            self.assertEqual(self.client.get(f"/api/v1/data-requests/{request_id}/download/").status_code, 404)
            self.client.force_authenticate(self.viewer)
            download = self.client.get(f"/api/v1/data-requests/{request_id}/download/")
            self.assertEqual(download.status_code, 200)
            self.assertIn(b"Subscribers,50", b"".join(download.streaming_content))
            download.close()

    def test_admin_attachment_must_match_requested_format(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        request_id = self.create_request()
        DataRequest.objects.filter(pk=request_id).update(status="UNDER_REVIEW", requested_format="PDF")
        self.client.force_authenticate(self.admin)
        response = self.client.post(
            f"/api/v1/data-requests/{request_id}/approve/",
            {"file": SimpleUploadedFile("extract.xlsx", b"not-a-pdf")},
            format="multipart",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("requires a PDF file", response.data["detail"])

    def setUp(self):
        self.admin = User.objects.create_user("admin-request-test@nca.org.gh", "long-test-password", name="Admin", role="NCA_ADMIN")
        self.officer = User.objects.create_user("officer-request-test@nca.org.gh", "long-test-password", name="Officer", role="NCA_OFFICER")
        division = NCADivision.objects.create(code="research", name="Research")
        self.viewer = User.objects.create_user("viewer-request-test@nca.org.gh", "long-test-password", name="Viewer", role="NCA_VIEWER", division=division, grade="Principal Manager")
        self.other = User.objects.create_user("other-viewer@nca.org.gh", "long-test-password", name="Other", role="NCA_VIEWER", division=division, grade="Manager")
        self.form = FormTemplate.objects.create(form_code="DC-ISP06", name="ISP data", sector="TELECOM", provider_category="ISP", frequency="ANNUAL", effective_from="2024-01-01", status="ACTIVE")
        section = FormSection.objects.create(form_template=self.form, section_code="main", title="Main")
        self.field = FormField.objects.create(section=section, field_code="revenue", label="Revenue", field_type="number")
        self.provider = ProviderProfile.objects.create(registered_name="Test ISP", sector="TELECOM", category="ISP", licence_type="ISP", licence_number="T-001", primary_email="test@example.com", primary_phone="1")
        self.period = ReportingPeriod.objects.create(name="2025", frequency="ANNUAL", year=2025, opens_at=timezone.now()-timedelta(days=30), due_at=timezone.now()+timedelta(days=30), status="ACTIVE", created_by=self.admin)
        expected = ExpectedSubmission.objects.create(provider=self.provider, form_template=self.form, period=self.period, workflow_status="APPROVED")
        submission = Submission.objects.create(expected=expected, version=1, completion_pct=100)
        SubmissionValue.objects.create(submission=submission, field=self.field, value="=123", value_status="PROVIDED", updated_by=self.admin)
        self.body = {"title":"Simple request","requesting_division":"Research","purpose":"Policy analysis","requested_format":"CSV","scope":{"form_template_ids":[self.form.id],"period_ids":[self.period.id],"all_fields":True,"field_ids":[],"grid_column_ids":[],"provider_scope":"ALL","sector":"","provider_category":"","provider_ids":[]}}

    def create_request(self):
        self.client.force_authenticate(self.viewer)
        response = self.client.post("/api/v1/data-requests/", self.body, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        return response.data["id"]

    def test_catalog_is_metadata_only(self):
        self.client.force_authenticate(self.viewer)
        response = self.client.get("/api/v1/data-catalog/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["forms"][0]["sections"][0]["fields"][0]["label"], "Revenue")
        self.assertEqual(response.data["forms"][0]["applicable_provider_ids"], [self.provider.id])
        self.assertEqual(response.data["forms"][0]["applicable_provider_ids_by_period"][str(self.period.id)], [self.provider.id])
        self.assertNotIn("=123", str(response.data))

    def test_new_and_resubmitted_requests_notify_admins(self):
        request_id = self.create_request()
        self.assertTrue(DataRequestNotification.objects.filter(
            request_id=request_id, recipient=self.admin, title="Submitted",
        ).exists())
        DataRequest.objects.filter(pk=request_id).update(status="CHANGES_REQUESTED")
        self.client.force_authenticate(self.viewer)
        response = self.client.post(f"/api/v1/data-requests/{request_id}/resubmit/", {}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(DataRequestNotification.objects.filter(
            request_id=request_id, recipient=self.admin, title="Resubmitted",
        ).exists())

    def test_requester_isolation_and_admin_queue(self):
        request_id = self.create_request()
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get(f"/api/v1/data-requests/{request_id}/").status_code, 404)
        self.client.force_authenticate(self.admin)
        admin_response = self.client.get(f"/api/v1/data-requests/{request_id}/")
        self.assertEqual(admin_response.status_code, 200)
        self.assertEqual(admin_response.data["dataset_names"], ["ISP data"])
        self.assertEqual(admin_response.data["period_names"], ["2025"])
        self.assertEqual(admin_response.data["provider_names"], ["Test ISP"])
        self.client.force_authenticate(self.officer)
        officer_response = self.client.get(f"/api/v1/data-requests/{request_id}/")
        self.assertEqual(officer_response.status_code, 200)
        self.assertEqual(officer_response.data["dataset_names"], ["ISP data"])

    def test_review_approval_and_private_download(self):
        request_id = self.create_request()
        self.client.force_authenticate(self.admin)
        due = (timezone.now()+timedelta(days=3)).isoformat()
        self.assertEqual(self.client.post(f"/api/v1/data-requests/{request_id}/start-review/", {"expected_delivery_at":due}, format="json").status_code, 200)
        with self.captureOnCommitCallbacks(execute=True):
            approved = self.client.post(f"/api/v1/data-requests/{request_id}/approve/", {}, format="json")
        self.assertEqual(approved.status_code, 200, approved.data)
        self.assertEqual(approved.data["status"], "APPROVED")
        ready = self.client.get(f"/api/v1/data-requests/{request_id}/")
        self.assertEqual(ready.data["status"], "READY")
        self.assertIn("artifact", ready.data)
        self.assertEqual(approved.data["requesting_division"], "Research")
        self.assertEqual(approved.data["requester_grade_snapshot"], "Principal Manager")
        self.assertEqual(self.client.get(f"/api/v1/data-requests/{request_id}/download/").status_code, 200)
        self.client.force_authenticate(self.officer)
        self.assertEqual(self.client.get(f"/api/v1/data-requests/{request_id}/download/").status_code, 200)
        self.client.force_authenticate(self.viewer)
        self.assertEqual(self.client.get(f"/api/v1/data-requests/{request_id}/download/").status_code, 200)

    def test_reasons_are_required(self):
        request_id = self.create_request(); self.client.force_authenticate(self.admin)
        due = (timezone.now()+timedelta(days=3)).isoformat(); self.client.post(f"/api/v1/data-requests/{request_id}/start-review/", {"expected_delivery_at":due}, format="json")
        self.assertEqual(self.client.post(f"/api/v1/data-requests/{request_id}/reject/", {}, format="json").status_code, 400)
        self.assertEqual(self.client.post(f"/api/v1/data-requests/{request_id}/request-changes/", {}, format="json").status_code, 400)

    def test_requester_can_edit_only_after_changes_and_resubmit(self):
        request_id = self.create_request()
        self.client.force_authenticate(self.admin)
        due = (timezone.now()+timedelta(days=3)).isoformat()
        self.client.post(f"/api/v1/data-requests/{request_id}/start-review/", {"expected_delivery_at":due}, format="json")
        changed = self.client.post(f"/api/v1/data-requests/{request_id}/request-changes/", {"note":"Clarify the policy purpose."}, format="json")
        self.assertEqual(changed.status_code, 200)
        self.client.force_authenticate(self.viewer)
        updated = self.client.patch(f"/api/v1/data-requests/{request_id}/", {
            **self.body, "title": "Updated request", "purpose": "Clarified policy analysis",
        }, format="json")
        self.assertEqual(updated.status_code, 200, updated.data)
        resubmitted = self.client.post(f"/api/v1/data-requests/{request_id}/resubmit/", {}, format="json")
        self.assertEqual(resubmitted.status_code, 200)
        self.assertEqual(resubmitted.data["status"], "SUBMITTED")
        self.assertEqual(resubmitted.data["decision_note"], "")
        self.assertEqual(DataRequestEvent.objects.filter(request_id=request_id, event_type="RESUBMITTED").count(), 1)

    def test_admin_can_adjust_delivery_and_requester_is_notified(self):
        request_id = self.create_request()
        self.client.force_authenticate(self.admin)
        first_due = timezone.now()+timedelta(days=3)
        self.client.post(f"/api/v1/data-requests/{request_id}/start-review/", {"expected_delivery_at":first_due.isoformat()}, format="json")
        second_due = timezone.now()+timedelta(days=5)
        adjusted = self.client.post(f"/api/v1/data-requests/{request_id}/adjust-delivery/", {"expected_delivery_at":second_due.isoformat()}, format="json")
        self.assertEqual(adjusted.status_code, 200, adjusted.data)
        self.assertEqual(DataRequestEvent.objects.filter(request_id=request_id, event_type="DELIVERY_DATE_CHANGED").count(), 1)
        self.assertTrue(DataRequestNotification.objects.filter(request_id=request_id, recipient=self.viewer, title="Delivery Date Changed").exists())

    def test_generation_is_idempotent_and_retry_cannot_be_queued_twice(self):
        request_id = self.create_request()
        item = DataRequest.objects.get(pk=request_id)
        item.status = "APPROVED"
        item.reviewer = self.admin
        item.approval_manifest = {"submission_ids":[Submission.objects.get(expected__form_template=self.form).id], "field_ids":[self.field.id], "grid_column_ids":[]}
        item.save()
        generate_data_request.run(str(item.id))
        first_log_count = ExportLog.objects.filter(data_request_id=str(item.id)).count()
        generate_data_request.run(str(item.id))
        self.assertEqual(ExportLog.objects.filter(data_request_id=str(item.id)).count(), first_log_count)
        self.assertEqual(DataRequestEvent.objects.filter(request=item, event_type="FILE_READY").count(), 1)
        item.refresh_from_db()
        item.status = "GENERATION_FAILED"
        item.save(update_fields=["status", "updated_at"])
        self.client.force_authenticate(self.admin)
        first = self.client.post(f"/api/v1/data-requests/{item.id}/retry-generation/", {}, format="json")
        second = self.client.post(f"/api/v1/data-requests/{item.id}/retry-generation/", {}, format="json")
        self.assertEqual(first.status_code, 202)
        self.assertEqual(second.status_code, 409)
