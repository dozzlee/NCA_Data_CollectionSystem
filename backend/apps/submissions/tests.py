from datetime import timedelta

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.forms_engine.models import FormField, FormSection, FormTemplate
from apps.providers.models import ProviderProfile
from apps.users.models import Organization, User
from .models import EditRequest, ExpectedSubmission, Notification, ReportingPeriod, Submission, SubmissionValue


class WorkflowPermissionTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        nca_org = Organization.objects.create(name="NCA", org_type="NCA")
        self.provider_org = Organization.objects.create(name="MTN", org_type="PROVIDER")
        other_org = Organization.objects.create(name="Other", org_type="PROVIDER")
        self.admin = User.objects.create_user("admin@test.local", "password1234", name="Admin", role="NCA_ADMIN", organization=nca_org)
        self.officer = User.objects.create_user("officer@test.local", "password1234", name="Officer", role="NCA_OFFICER", organization=nca_org)
        self.entry = User.objects.create_user("entry@test.local", "password1234", name="Entry", role="PROVIDER_DATA_ENTRY", organization=self.provider_org)
        self.approver = User.objects.create_user("approver@test.local", "password1234", name="Approver", role="PROVIDER_APPROVER", organization=self.provider_org)
        self.other_entry = User.objects.create_user("other@test.local", "password1234", name="Other", role="PROVIDER_DATA_ENTRY", organization=other_org)
        provider = ProviderProfile.objects.create(
            organization=self.provider_org, registered_name="MTN", category="MNO",
            licence_type="MNO", licence_number="1", primary_email="mtn@test.local", primary_phone="1",
        )
        template = FormTemplate.objects.create(
            form_code="MNO-MONTHLY", name="Monthly", provider_category="MNO",
            frequency="MONTHLY", effective_from=timezone.now().date(), status="ACTIVE",
        )
        section = FormSection.objects.create(form_template=template, section_code="A", title="A")
        self.field = FormField.objects.create(section=section, field_code="A1", label="Value", field_type="text")
        period = ReportingPeriod.objects.create(
            name="Current", frequency="MONTHLY", year=2026, month=7,
            opens_at=timezone.now() - timedelta(days=1), due_at=timezone.now() + timedelta(days=7),
            status="ACTIVE", created_by=self.admin,
        )
        self.expected = ExpectedSubmission.objects.create(provider=provider, form_template=template, period=period, workflow_status="DRAFT")
        self.submission = Submission.objects.create(expected=self.expected)
        SubmissionValue.objects.create(submission=self.submission, field=self.field, value="original", value_status="PROVIDED", updated_by=self.entry)

    def auth(self, user):
        self.client.force_authenticate(user)

    def test_role_actions_and_cross_provider_isolation(self):
        self.auth(self.admin)
        self.assertEqual(self.client.post(f"/api/v1/expected-submissions/{self.expected.id}/start/").status_code, 403)
        self.auth(self.approver)
        self.assertEqual(self.client.put(f"/api/v1/submissions/{self.submission.id}/sections/A/values/", {"values": []}, format="json").status_code, 403)
        self.auth(self.other_entry)
        self.assertEqual(self.client.get(f"/api/v1/expected-submissions/{self.expected.id}/").status_code, 404)

    def test_data_entry_to_approver_to_nca(self):
        self.auth(self.entry)
        response = self.client.post(f"/api/v1/submissions/{self.submission.id}/submit-for-approval/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Notification.objects.filter(recipient=self.approver, event_type="PENDING_APPROVAL").exists())
        self.auth(self.approver)
        response = self.client.post(f"/api/v1/submissions/{self.submission.id}/official-submit/")
        self.assertEqual(response.status_code, 200)
        self.expected.refresh_from_db()
        self.assertEqual(self.expected.workflow_status, "SUBMITTED")
        self.assertTrue(Notification.objects.filter(recipient=self.officer, event_type="OFFICIAL_SUBMISSION").exists())

    def test_edit_request_approval_creates_immutable_new_version(self):
        self.expected.workflow_status = "APPROVED"
        self.expected.save()
        self.auth(self.approver)
        response = self.client.post("/api/v1/edit-requests/", {"submission": self.submission.id, "reason": "Correct KPI"}, format="json")
        self.assertEqual(response.status_code, 201)
        edit_id = response.data["id"]
        self.auth(self.officer)
        response = self.client.post(f"/api/v1/edit-requests/{edit_id}/approve/", {"decision_note": "Approved"}, format="json")
        self.assertEqual(response.status_code, 200)
        edit = EditRequest.objects.get(pk=edit_id)
        self.assertEqual(edit.status, "APPROVED")
        self.assertEqual(edit.reopened_submission.version, 2)
        self.assertEqual(edit.reopened_submission.values.get(field=self.field).value, "original")
        self.assertEqual(SubmissionValue.objects.get(submission=self.submission, field=self.field).value, "original")


class DemoSeedTests(TestCase):
    @override_settings(DEBUG=True)
    def test_seed_is_idempotent(self):
        call_command("seed_demo")
        call_command("seed_demo")
        self.assertEqual(User.objects.filter(email__in=[
            "admin@nca.org.gh", "officer.mensah@nca.org.gh",
            "data@mtn.com.gh", "approver@mtn.com.gh",
            "data@vodafone.com.gh", "approver@vodafone.com.gh",
        ]).count(), 6)
        self.assertEqual(ExpectedSubmission.objects.filter(form_template__form_code="MNO-MONTHLY").count(), 2)
