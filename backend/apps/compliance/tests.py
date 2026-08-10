from datetime import timedelta

from django.utils import timezone
from rest_framework.test import APITestCase

from apps.forms_engine.models import FormTemplate
from apps.providers.models import ProviderProfile
from apps.submissions.models import ExpectedSubmission, ReportingPeriod
from apps.users.models import Organization, User

from .models import ComplianceFlag, EmailLog, EmailTemplate


class ComplianceWorkflowTests(APITestCase):
    def setUp(self):
        self.org_a = Organization.objects.create(name="Provider A", org_type="PROVIDER")
        self.org_b = Organization.objects.create(name="Provider B", org_type="PROVIDER")
        self.provider_a = ProviderProfile.objects.create(
            organization=self.org_a,
            registered_name="Provider A",
            sector="TELECOM",
            category="MNO",
            licence_type="MNO",
            licence_number="A-1",
            primary_email="a@example.com",
            primary_phone="1",
        )
        self.provider_b = ProviderProfile.objects.create(
            organization=self.org_b,
            registered_name="Provider B",
            sector="TELECOM",
            category="MNO",
            licence_type="MNO",
            licence_number="B-1",
            primary_email="b@example.com",
            primary_phone="2",
        )
        self.admin = User.objects.create_user(
            "admin@nca.test",
            "StrongPassword123!",
            name="Admin",
            role="NCA_ADMIN",
        )
        self.entry_a = User.objects.create_user(
            "entry@a.test",
            "StrongPassword123!",
            name="Entry A",
            role="PROVIDER_DATA_ENTRY",
            organization=self.org_a,
        )
        self.entry_b = User.objects.create_user(
            "entry@b.test",
            "StrongPassword123!",
            name="Entry B",
            role="PROVIDER_DATA_ENTRY",
            organization=self.org_b,
        )
        self.form = FormTemplate.objects.create(
            form_code="MNO-MONTHLY",
            name="Monthly",
            sector="TELECOM",
            provider_category="MNO",
            frequency="MONTHLY",
            effective_from=timezone.localdate(),
            status="ACTIVE",
        )
        self.period = ReportingPeriod.objects.create(
            name="July 2026",
            frequency="MONTHLY",
            year=2026,
            month=7,
            opens_at=timezone.now() - timedelta(days=1),
            due_at=timezone.now() + timedelta(days=7),
            status="ACTIVE",
            created_by=self.admin,
        )
        self.expected_a = ExpectedSubmission.objects.create(
            provider=self.provider_a,
            form_template=self.form,
            period=self.period,
            workflow_status="DRAFT",
            due_state="DUE_SOON",
        )
        self.expected_b = ExpectedSubmission.objects.create(
            provider=self.provider_b,
            form_template=self.form,
            period=self.period,
            workflow_status="DRAFT",
            due_state="DUE_SOON",
        )
        self.flag_a = ComplianceFlag.objects.create(
            expected_submission=self.expected_a,
            provider=self.provider_a,
            flag_type="MISSING_DATA",
            description="Two required fields are missing.",
            missing_field_count=2,
            completion_percentage=50,
        )
        self.flag_b = ComplianceFlag.objects.create(
            expected_submission=self.expected_b,
            provider=self.provider_b,
            flag_type="MISSING_DATA",
            description="One required field is missing.",
            missing_field_count=1,
            completion_percentage=75,
        )
        self.template = EmailTemplate.objects.create(
            template_type="MISSING_FIELDS",
            subject="Missing data for {{provider_name}}",
            body="{{provider_name}} has missing data for {{form_name}}.",
            placeholders=["provider_name", "form_name"],
            status="APPROVED",
        )

    def test_admin_can_list_acknowledge_resolve_and_generate_email(self):
        self.client.force_authenticate(self.admin)
        listing = self.client.get("/api/v1/compliance/flags/?status=OPEN")
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.data["count"], 2)

        acknowledged = self.client.patch(
            f"/api/v1/compliance/flags/{self.flag_a.id}/acknowledge/",
            {},
            format="json",
        )
        self.assertEqual(acknowledged.status_code, 200)
        self.assertEqual(acknowledged.data["status"], "ACKNOWLEDGED")

        resolved = self.client.patch(
            f"/api/v1/compliance/flags/{self.flag_a.id}/resolve/",
            {},
            format="json",
        )
        self.assertEqual(resolved.status_code, 200)
        self.assertEqual(resolved.data["status"], "RESOLVED")

        email = self.client.post(
            "/api/v1/compliance/generate-email/",
            {
                "template_type": "MISSING_FIELDS",
                "expected_submission_ids": [self.expected_a.id],
            },
            format="json",
        )
        self.assertEqual(email.status_code, 201)
        self.assertEqual(email.data["generated"], 1)
        log = EmailLog.objects.get(pk=email.data["email_ids"][0])
        self.assertIn("Provider A", log.subject)
        self.assertEqual(log.recipients[0]["email"], self.provider_a.primary_email)

    def test_provider_sees_only_own_compliance_flags(self):
        self.client.force_authenticate(self.entry_a)
        response = self.client.get("/api/v1/compliance/my-flags/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["provider"], self.provider_a.id)
        self.assertNotContains(response, "Provider B")

        self.client.force_authenticate(self.entry_b)
        response = self.client.get("/api/v1/compliance/my-flags/")
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["provider"], self.provider_b.id)
