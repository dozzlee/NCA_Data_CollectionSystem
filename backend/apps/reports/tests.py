from datetime import date, timedelta
from tempfile import TemporaryDirectory
import uuid

from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.forms_engine.models import FormField, FormSection, FormTemplate
from apps.providers.models import ProviderProfile
from apps.submissions.models import ExpectedSubmission, ReportingPeriod, Submission, SubmissionValue
from apps.users.models import User
from .models import GeneratedReport, ReportPreparation, ReportPublicationMetadata, ReportTemplate
from .services import active_template, period_context


class ReportWorkflowTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user("reports-admin@nca.test", "password", name="Reports Admin", role="NCA_ADMIN")
        self.officer = User.objects.create_user("reports-officer@nca.test", "password", name="Reports Officer", role="NCA_OFFICER")
        self.viewer = User.objects.create_user("reports-viewer@nca.test", "password", name="Reports Viewer", role="NCA_VIEWER")
        self.provider_user = User.objects.create_user("reports-provider@nca.test", "password", name="Provider", role="PROVIDER_APPROVER")

    def test_period_context_uses_exact_quarter_and_historical_windows(self):
        q1 = period_context("QUARTERLY_BULLETIN", 2026, 1)
        self.assertEqual(q1["months"], [1, 2, 3])
        self.assertEqual(q1["previous_period"], "Q4 2025")
        self.assertEqual(q1["rolling_five_quarters"], ["Q1 2025", "Q2 2025", "Q3 2025", "Q4 2025", "Q1 2026"])
        annual = period_context("CIR", 2026, None)
        self.assertEqual(annual["historical_years"], [2022, 2023, 2024, 2025, 2026])

    def test_only_admins_and_officers_can_access_reports(self):
        for user, expected in ((self.admin, 200), (self.officer, 200), (self.viewer, 403), (self.provider_user, 403)):
            self.client.force_authenticate(user)
            self.assertEqual(self.client.get("/api/v1/reports/definitions/").status_code, expected)

    def test_current_sparse_database_is_reported_as_insufficient(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post("/api/v1/reports/prepare/", {"report_type": "QUARTERLY_BULLETIN", "year": 2026, "quarter": 2}, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["status"], "MISSING_DATA")
        self.assertTrue(response.data["manifest"]["missing"])
        blocked = self.client.post(f"/api/v1/reports/preparations/{response.data['id']}/generate/", {"idempotency_key": str(uuid.uuid4())}, format="json")
        self.assertEqual(blocked.status_code, 409)

    def test_active_family_template_applies_to_every_selected_period(self):
        quarterly = ReportTemplate.objects.get(
            report_type="QUARTERLY_BULLETIN", status="ACTIVE"
        )
        annual = ReportTemplate.objects.get(report_type="CIR", status="ACTIVE")

        self.assertEqual(active_template("QUARTERLY_BULLETIN", 2025, 2), quarterly)
        self.assertEqual(active_template("QUARTERLY_BULLETIN", 2030, 4), quarterly)
        self.assertEqual(active_template("CIR", 2024), annual)
        self.assertEqual(active_template("CIR", 2030), annual)

        self.client.force_authenticate(self.admin)
        response = self.client.post(
            "/api/v1/reports/prepare/",
            {"report_type": "QUARTERLY_BULLETIN", "year": 2025, "quarter": 2},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["template_version"], quarterly.version)
        self.assertEqual(response.data["manifest"]["context"]["period_label"], "Q2 2025")

    def _complete_fixture(self):
        ReportTemplate.objects.filter(report_type="QUARTERLY_BULLETIN", status="ACTIVE").update(status="ARCHIVED")
        template = ReportTemplate.objects.create(
            report_type="QUARTERLY_BULLETIN", name="Quarterly Statistical Bulletin on Communications in Ghana",
            version=90, effective_year=2026, effective_quarter=1, filename_pattern="Q{quarter}_{year}_Statistical_Bulletin.pdf",
            source_reference="Q1_2026_Statistical_Bulletin.pdf", source_sha256="a" * 64,
            immutable_blocks=["AUTHORISED IMMUTABLE WORDING"], status="ACTIVE",
            field_mappings=[{"key":"subscribers", "section":"Mobile Network Services", "location":"Table 1", "label":"Subscribers", "form_code":"REPORT-MNO", "field_code":"SUBSCRIBERS", "provider_category":"MNO", "period_aggregation":"PERIOD_END", "provider_aggregation":"SUM", "window":"CURRENT", "decimal_places":0, "required":True}],
        )
        form = FormTemplate.objects.create(form_code="REPORT-MNO", name="Report MNO", sector="TELECOM", provider_category="MNO", frequency="MONTHLY", effective_from=date(2026, 1, 1), status="ACTIVE")
        section = FormSection.objects.create(form_template=form, section_code="MAIN", title="Main")
        field = FormField.objects.create(section=section, field_code="SUBSCRIBERS", label="Subscribers", field_type="number")
        provider = ProviderProfile.objects.create(registered_name="Report Mobile", sector="TELECOM", category="MNO", licence_type="MNO", licence_number="REPORT-1", primary_email="reports@example.com", primary_phone="1")
        for month, value in ((1, "10"), (2, "20"), (3, "30")):
            period = ReportingPeriod.objects.create(name=f"{month}/2026", frequency="MONTHLY", year=2026, month=month, opens_at=timezone.now()-timedelta(days=30), due_at=timezone.now()-timedelta(days=1), status="CLOSED", created_by=self.admin)
            expected = ExpectedSubmission.objects.create(provider=provider, form_template=form, period=period, workflow_status="APPROVED")
            submission = Submission.objects.create(expected=expected, version=1, regulatory_status="APPROVED", submitted_at=timezone.now(), completion_pct=100)
            SubmissionValue.objects.create(submission=submission, field=field, value=value, value_status="PROVIDED", updated_by=self.admin)
        ReportPublicationMetadata.objects.create(report_type="QUARTERLY_BULLETIN", year=2026, quarter=1, volume=11, issue=1, updated_by=self.admin)
        return template

    def test_ready_report_generation_is_idempotent_and_downloadable(self):
        self._complete_fixture(); self.client.force_authenticate(self.officer)
        prepared = self.client.post("/api/v1/reports/prepare/", {"report_type":"QUARTERLY_BULLETIN", "year":2026, "quarter":1}, format="json")
        self.assertEqual(prepared.status_code, 201, prepared.data)
        self.assertEqual(prepared.data["status"], "READY")
        key = str(uuid.uuid4())
        with TemporaryDirectory() as root, override_settings(PRIVATE_EXPORT_ROOT=root):
            first = self.client.post(f"/api/v1/reports/preparations/{prepared.data['id']}/generate/", {"idempotency_key":key}, format="json")
            second = self.client.post(f"/api/v1/reports/preparations/{prepared.data['id']}/generate/", {"idempotency_key":key}, format="json")
            self.assertEqual(first.status_code, 201, first.data)
            self.assertEqual(first.data["id"], second.data["id"])
            self.assertEqual(first.data["filename"], "Q1_2026_Statistical_Bulletin.pdf")
            self.assertEqual(GeneratedReport.objects.count(), 1)
            download = self.client.get(f"/api/v1/reports/history/{first.data['id']}/download/")
            self.assertEqual(download.status_code, 200)
            self.assertEqual(download["Content-Type"], "application/pdf")
            download.close()

    def test_changed_approved_value_makes_preparation_stale(self):
        self._complete_fixture(); self.client.force_authenticate(self.admin)
        prepared = self.client.post("/api/v1/reports/prepare/", {"report_type":"QUARTERLY_BULLETIN", "year":2026, "quarter":1}, format="json")
        value = SubmissionValue.objects.filter(field__field_code="SUBSCRIBERS").first(); value.value = "999"; value.save(update_fields=["value", "updated_at"])
        response = self.client.post(f"/api/v1/reports/preparations/{prepared.data['id']}/generate/", {"idempotency_key":str(uuid.uuid4())}, format="json")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(ReportPreparation.objects.get(pk=prepared.data["id"]).status, "STALE")
