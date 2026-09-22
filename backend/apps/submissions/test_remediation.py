from datetime import timedelta

from django.utils import timezone
from rest_framework.test import APITestCase

from apps.audit.models import AuditEvent
from apps.audit.services import record_audit
from apps.compliance.models import CommunicationRecord
from apps.forms_engine.models import FormTemplate
from apps.providers.models import ProviderProfile
from apps.users.models import Organization, User

from .models import ExpectedSubmission, ReportingPeriod, Submission


class CommunicationSubmissionPenaltyRemediationTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            "admin-remediation@nca.test", "password", name="Admin", role="NCA_ADMIN",
        )
        self.officer = User.objects.create_user(
            "officer-remediation@nca.test", "password", name="Officer", role="NCA_OFFICER",
        )
        organization = Organization.objects.create(name="Provider Remediation", org_type="PROVIDER")
        self.approver = User.objects.create_user(
            "approver-remediation@provider.test", "password", name="Approver",
            role="PROVIDER_APPROVER", organization=organization,
        )
        self.provider = ProviderProfile.objects.create(
            organization=organization, provider_code="REM", registered_name="Provider Remediation",
            category="MNO", licence_type="MNO", licence_number="REM-1",
            primary_email="contact@provider.test", primary_phone="1",
        )
        self.form = FormTemplate.objects.create(
            form_code="REMEDIATION", name="Remediation Form", provider_category="MNO",
            frequency="MONTHLY", version="1.0", effective_from=timezone.localdate(),
            status="ACTIVE", mapping_complete=True, approval_status="APPROVED",
        )
        self.period = ReportingPeriod.objects.create(
            name="September 2026", frequency="MONTHLY", year=2026, month=9,
            opens_at=timezone.now() - timedelta(days=3), due_at=timezone.now() + timedelta(days=20),
            status="ACTIVE", created_by=self.admin,
        )
        self.expected = ExpectedSubmission.objects.create(
            provider=self.provider, form_template=self.form, period=self.period,
            workflow_status="RESUBMITTED", provider_status="CLOSED",
        )
        self.returned = Submission.objects.create(
            expected=self.expected, version=1, regulatory_status="RETURNED_FOR_CORRECTION",
            submitted_by=self.approver, submitted_at=timezone.now() - timedelta(days=2),
        )
        self.latest = Submission.objects.create(
            expected=self.expected, version=2, regulatory_status="SUBMITTED",
            submitted_by=self.approver, submitted_at=timezone.now() - timedelta(hours=2),
            supersedes=self.returned,
        )

    def test_provider_submissions_returns_one_task_with_latest_formal_version(self):
        self.client.force_authenticate(self.approver)
        response = self.client.get("/api/v1/provider-submissions/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["count"], 1)
        row = response.data["results"][0]
        self.assertEqual(row["form_task_id"], self.expected.id)
        self.assertEqual(row["latest_submission_id"], self.latest.id)
        self.assertEqual(row["regulatory_status"], "SUBMITTED")

    def test_provider_submissions_labels_returned_form_as_flagged(self):
        self.latest.regulatory_status = "DRAFT"
        self.latest.submitted_at = None
        self.latest.save(update_fields=["regulatory_status", "submitted_at"])
        self.client.force_authenticate(self.approver)
        response = self.client.get("/api/v1/provider-submissions/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["count"], 1)
        row = response.data["results"][0]
        self.assertEqual(row["latest_submission_id"], self.returned.id)
        self.assertEqual(row["regulatory_status"], "RETURNED_FOR_CORRECTION")
        self.assertEqual(row["provider_display_status"], "FLAGGED")

    def test_communication_history_spans_versions_newest_first_and_hides_internal(self):
        older = CommunicationRecord.objects.create(
            submission=self.returned, expected_submission=self.expected, event_type="CORRECTION_REQUESTED",
            channel="SYSTEM", direction="OUTBOUND", subject="Older", body="Older", content_sha256="a" * 64,
            submission_reference=self.returned.submission_reference,
        )
        newer = CommunicationRecord.objects.create(
            submission=self.latest, expected_submission=self.expected, event_type="OFFICIALLY_SUBMITTED",
            channel="SYSTEM", direction="OUTBOUND", subject="Newer", body="Newer", content_sha256="b" * 64,
            submission_reference=self.latest.submission_reference,
        )
        CommunicationRecord.objects.create(
            submission=self.latest, expected_submission=self.expected, event_type="ADD_NOTE",
            channel="SYSTEM", direction="INTERNAL", subject="Internal", body="Secret", content_sha256="c" * 64,
            submission_reference=self.latest.submission_reference,
        )
        CommunicationRecord.objects.filter(pk=older.pk).update(created_at=timezone.now() - timedelta(days=1))
        CommunicationRecord.objects.filter(pk=newer.pk).update(created_at=timezone.now())
        self.client.force_authenticate(self.approver)
        response = self.client.get(f"/api/v1/submissions/{self.latest.id}/communications/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual([row["subject"] for row in response.data], ["Newer", "Older"])
        self.assertEqual(response.data[0]["submission_version"], 2)

    def test_only_admin_updates_penalty_and_provider_summary_aggregates_it(self):
        url = f"/api/v1/expected-submissions/{self.expected.id}/penalty/"
        self.client.force_authenticate(self.officer)
        self.assertEqual(self.client.patch(url, {"penalty_amount_ghs": "250.00", "penalty_reference": "P-1"}).status_code, 403)

        self.client.force_authenticate(self.admin)
        response = self.client.patch(url, {
            "penalty_amount_ghs": "250.00", "penalty_reference": "P-1", "penalty_note": "Late return",
        }, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["penalty_amount_ghs"], "250.00")
        self.assertTrue(AuditEvent.objects.filter(action="OBLIGATION_PENALTY_UPDATED", entity_id=str(self.expected.id)).exists())

        self.client.force_authenticate(self.approver)
        summary = self.client.get("/api/v1/provider-workspace/summary/")
        self.assertEqual(summary.status_code, 200, summary.data)
        self.assertEqual(summary.data["penalty_amount_ghs"], 250)
        self.assertEqual(summary.data["penalty_obligation_count"], 1)

    def test_admin_marks_penalty_paid_with_audit_and_idempotent_retry(self):
        self.expected.penalty_amount_ghs = 250
        self.expected.penalty_reference = "P-1"
        self.expected.save()
        url = f"/api/v1/expected-submissions/{self.expected.id}/penalty/"
        payload = {"action": "MARK_PAID", "payment_reference": "PAY-123", "payment_note": "Received"}
        for user in [self.officer, self.approver]:
            self.client.force_authenticate(user)
            self.assertEqual(self.client.patch(url, payload, format="json").status_code, 403)
        self.client.force_authenticate(self.admin)
        response = self.client.patch(url, payload, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["penalty_amount_ghs"], "0.00")
        self.expected.refresh_from_db()
        self.assertEqual(self.expected.penalty_updated_by, self.admin)
        event = AuditEvent.objects.get(action="OBLIGATION_PENALTY_PAID", entity_id=str(self.expected.id))
        self.assertEqual(event.before_value["penalty_amount_ghs"], "250.00")
        self.assertEqual(event.after_value["payment_reference"], "PAY-123")
        self.assertEqual(self.client.patch(url, payload, format="json").status_code, 200)
        self.assertEqual(AuditEvent.objects.filter(action="OBLIGATION_PENALTY_PAID").count(), 1)
        self.client.force_authenticate(self.approver)
        summary = self.client.get("/api/v1/provider-workspace/summary/").data
        self.assertEqual(summary["penalty_amount_ghs"], 0)
        self.assertEqual(summary["penalty_obligation_count"], 0)

    def test_non_zero_penalty_requires_reference(self):
        self.client.force_authenticate(self.admin)
        response = self.client.patch(
            f"/api/v1/expected-submissions/{self.expected.id}/penalty/",
            {"penalty_amount_ghs": "10.00", "penalty_reference": ""}, format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_audit_api_is_admin_only_and_sensitive_metadata_is_redacted(self):
        event = record_audit(
            user=self.admin, action="REDACTION_TEST", entity_type="Test", entity_id="1",
            after={"password": "never-store", "values": ["private"], "count": 1},
        )
        self.assertTrue(event.after_value["password"]["redacted"])
        self.assertTrue(event.after_value["values"]["redacted"])
        self.assertEqual(event.after_value["count"], 1)
        self.client.force_authenticate(self.officer)
        self.assertEqual(self.client.get("/api/v1/audit/").status_code, 403)
        self.client.force_authenticate(self.admin)
        response = self.client.get("/api/v1/audit/?action=REDACTION_TEST")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["results"][0]["action"], "REDACTION_TEST")
