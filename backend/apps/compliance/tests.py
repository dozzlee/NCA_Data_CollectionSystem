from datetime import timedelta
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.forms_engine.models import FormTemplate
from apps.providers.models import ProviderProfile
from apps.submissions.models import ExpectedSubmission, ReportingPeriod, Submission, SubmissionEvent
from apps.users.models import Organization, User

from .models import (
    CommunicationRecord, ComplianceFlag, EmailTemplate, ExternalEmailHandoff,
)


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
        self.approver_a = User.objects.create_user(
            "approver@a.test",
            "StrongPassword123!",
            name="Approver A",
            role="PROVIDER_APPROVER",
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
        self.submission_a = Submission.objects.create(expected=self.expected_a, version=1)
        self.submission_b = Submission.objects.create(expected=self.expected_b, version=1)
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

    def test_admin_can_list_and_update_submission_scoped_flags(self):
        self.client.force_authenticate(self.admin)
        listing = self.client.get(f"/api/v1/submissions/{self.submission_a.id}/compliance-flags/")
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(len(listing.data), 1)
        self.assertEqual(listing.data[0]["expected_submission"], self.expected_a.id)

        acknowledged = self.client.patch(
            f"/api/v1/submissions/{self.submission_a.id}/compliance-flags/{self.flag_a.id}/",
            {"status": "ACKNOWLEDGED"},
            format="json",
        )
        self.assertEqual(acknowledged.status_code, 200)
        self.assertEqual(acknowledged.data["status"], "ACKNOWLEDGED")
        self.assertTrue(acknowledged.data["event_id"])
        self.assertTrue(CommunicationRecord.objects.filter(submission_event_id=acknowledged.data["event_id"]).exists())

        resolved = self.client.patch(
            f"/api/v1/submissions/{self.submission_a.id}/compliance-flags/{self.flag_a.id}/",
            {"status": "RESOLVED"},
            format="json",
        )
        self.assertEqual(resolved.status_code, 200)
        self.assertEqual(resolved.data["status"], "RESOLVED")

    def test_provider_sees_only_own_compliance_flags(self):
        self.client.force_authenticate(self.entry_a)
        response = self.client.get(f"/api/v1/submissions/{self.submission_a.id}/compliance-flags/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["provider"], self.provider_a.id)
        self.assertNotContains(response, "Provider B")

        denied = self.client.get(f"/api/v1/submissions/{self.submission_b.id}/compliance-flags/")
        self.assertEqual(denied.status_code, 404)

    def test_workflow_event_creates_one_correspondence_and_one_handoff(self):
        template = EmailTemplate.objects.create(
            template_type="SUBMISSION_APPROVED", version=101, status="APPROVED",
            subject="Approved {{submission_reference}}",
            body="{{form_name}} was approved. {{portal_link}}",
            placeholders=["submission_reference", "form_name", "portal_link"],
        )
        event = SubmissionEvent.objects.create(
            submission=self.submission_a, actor=self.admin, event_type="SUBMISSION_APPROVED",
            from_status="DRAFT", to_status="APPROVED", message="Approved", audience="BOTH",
        )
        from .communications import create_system_record, ensure_email_handoff
        record = create_system_record(submission=self.submission_a, event=event)
        replay = create_system_record(submission=self.submission_a, event=event)
        handoff = ensure_email_handoff(submission=self.submission_a, event=event, actor=self.admin)
        handoff_replay = ensure_email_handoff(submission=self.submission_a, event=event, actor=self.admin)
        self.assertEqual(record.id, replay.id)
        self.assertEqual(handoff.id, handoff_replay.id)
        self.assertEqual(record.channel, "SYSTEM")
        self.assertEqual(record.email_log_id, None)
        self.assertNotIn("/submissions/", record.body)
        self.assertNotIn("/submissions/", handoff.body)
        self.assertEqual(CommunicationRecord.objects.filter(submission_event=event).count(), 1)
        self.assertEqual(ExternalEmailHandoff.objects.filter(event=event).count(), 1)
        self.assertEqual({row["email"] for row in handoff.recipients}, {self.entry_a.email, self.approver_a.email})

    def test_only_provider_approver_can_send_submission_correspondence_to_nca(self):
        self.expected_a.workflow_status = "PENDING_APPROVAL"
        self.expected_a.save(update_fields=["workflow_status"])
        payload = {"message": "Please review the updated service figures.", "comments": "Please review the updated service figures."}
        self.client.force_authenticate(self.entry_a)
        denied = self.client.post(
            f"/api/v1/submissions/{self.submission_a.id}/communications/send/",
            {"message": payload["message"]}, format="json",
        )
        self.assertEqual(denied.status_code, 403)

        self.client.force_authenticate(self.approver_a)
        sent = self.client.post(
            f"/api/v1/submissions/{self.submission_a.id}/communications/send/",
            {"message": payload["message"]}, format="json",
        )
        self.assertEqual(sent.status_code, 201, sent.data)
        record = CommunicationRecord.objects.get(submission=self.submission_a, event_type="SUBMISSION_CORRESPONDENCE")
        self.assertEqual(record.channel, "SYSTEM")
        self.assertEqual({row["role"] for row in record.recipients}, {"NCA_ADMIN"})
        first = self.client.post(
            f"/api/v1/submissions/{self.submission_a.id}/communications/email-handoff/",
            {"event_id": sent.data["event_id"]}, format="json",
        )
        second = self.client.post(
            f"/api/v1/submissions/{self.submission_a.id}/communications/email-handoff/",
            {"event_id": sent.data["event_id"]}, format="json",
        )
        self.assertEqual(first.status_code, 201)
        self.assertEqual(first.data["id"], second.data["id"])
        self.assertEqual(ExternalEmailHandoff.objects.filter(event_id=sent.data["event_id"]).count(), 1)
