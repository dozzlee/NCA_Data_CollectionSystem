from datetime import timedelta
from django.utils import timezone
from rest_framework.test import APITestCase
from apps.users.models import User, NCADivision
from apps.forms_engine.models import FormTemplate, FormSection, FormField
from apps.providers.models import ProviderProfile
from apps.submissions.models import ReportingPeriod, ExpectedSubmission, Submission, SubmissionValue


class DataRequestWorkflowTests(APITestCase):
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
        self.assertNotIn("=123", str(response.data))

    def test_requester_isolation_and_admin_queue(self):
        request_id = self.create_request()
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get(f"/api/v1/data-requests/{request_id}/").status_code, 404)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.get(f"/api/v1/data-requests/{request_id}/").status_code, 200)

    def test_review_approval_and_private_download(self):
        request_id = self.create_request()
        self.client.force_authenticate(self.admin)
        due = (timezone.now()+timedelta(days=3)).isoformat()
        self.assertEqual(self.client.post(f"/api/v1/data-requests/{request_id}/start-review/", {"expected_delivery_at":due}, format="json").status_code, 200)
        approved = self.client.post(f"/api/v1/data-requests/{request_id}/approve/", {}, format="json")
        self.assertEqual(approved.status_code, 200, approved.data)
        self.assertEqual(approved.data["status"], "READY")
        self.assertIn("artifact", approved.data)
        self.assertEqual(approved.data["requesting_division"], "Research")
        self.assertEqual(approved.data["requester_grade_snapshot"], "Principal Manager")
        self.assertEqual(self.client.get(f"/api/v1/data-requests/{request_id}/download/").status_code, 200)
        self.client.force_authenticate(self.officer)
        self.assertEqual(self.client.get(f"/api/v1/data-requests/{request_id}/download/").status_code, 404)
        self.client.force_authenticate(self.viewer)
        self.assertEqual(self.client.get(f"/api/v1/data-requests/{request_id}/download/").status_code, 200)

    def test_reasons_are_required(self):
        request_id = self.create_request(); self.client.force_authenticate(self.admin)
        due = (timezone.now()+timedelta(days=3)).isoformat(); self.client.post(f"/api/v1/data-requests/{request_id}/start-review/", {"expected_delivery_at":due}, format="json")
        self.assertEqual(self.client.post(f"/api/v1/data-requests/{request_id}/reject/", {}, format="json").status_code, 400)
        self.assertEqual(self.client.post(f"/api/v1/data-requests/{request_id}/request-changes/", {}, format="json").status_code, 400)
