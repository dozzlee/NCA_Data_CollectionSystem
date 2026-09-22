from datetime import timedelta

from django.utils import timezone
from rest_framework.test import APITestCase

from apps.forms_engine.models import FormField, FormSection, FormTemplate
from apps.providers.models import ProviderProfile
from apps.submissions.models import ExpectedSubmission, ReportingPeriod, Submission
from apps.users.models import Organization, User


class ExportCatalogueTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user("catalogue-admin@nca.test", "password", name="Admin", role="NCA_ADMIN")
        organization = Organization.objects.create(name="Catalogue Provider", org_type="PROVIDER")
        self.provider = ProviderProfile.objects.create(
            organization=organization, provider_code="CAT", registered_name="Catalogue Provider",
            sector="TELECOM", category="ISP", licence_type="ISP", licence_number="CAT-1",
            primary_email="catalogue@example.com", primary_phone="1",
        )
        self.form = FormTemplate.objects.create(
            form_code="CAT-FORM", name="Catalogue Form", sector="TELECOM", provider_category="ISP",
            frequency="MONTHLY", effective_from=timezone.localdate(), status="ACTIVE",
            approval_status="APPROVED", mapping_complete=True,
        )
        section = FormSection.objects.create(form_template=self.form, section_code="DATA", title="Data")
        FormField.objects.create(section=section, field_code="TOTAL", label="Total", field_type="number")
        self.period = ReportingPeriod.objects.create(
            name="September 2026", frequency="MONTHLY", year=2026, month=9,
            opens_at=timezone.now()-timedelta(days=5), due_at=timezone.now()+timedelta(days=20),
            status="ACTIVE", created_by=self.admin,
        )
        self.expected = ExpectedSubmission.objects.create(
            provider=self.provider, form_template=self.form, period=self.period, workflow_status="DRAFT",
        )
        Submission.objects.create(expected=self.expected, version=1)
        self.client.force_authenticate(self.admin)

    def test_catalogue_lists_forms_period_activity_and_summary(self):
        response = self.client.get("/api/v1/exports/catalogue/", {"period": self.period.id, "search": "Catalogue"})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["summary"]["forms"], 1)
        self.assertEqual(response.data["summary"]["forms_sent"], 1)
        self.assertEqual(response.data["forms"][0]["indicators"], 1)
        self.assertEqual(response.data["submissions"][0]["provider"], "Catalogue Provider")

    def test_catalogue_workbook_contains_forms_and_submission_summary(self):
        response = self.client.post(
            "/api/v1/exports/catalogue/xlsx/",
            {"period": self.period.id, "form_ids": [self.form.id], "expected_submission_ids": [self.expected.id]},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        self.assertGreater(len(response.content), 1000)
