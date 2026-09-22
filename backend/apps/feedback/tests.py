from rest_framework.test import APITestCase

from apps.audit.models import AuditEvent
from apps.users.models import Organization, User
from .models import FeedbackItem, FeedbackNotification


class ProviderCorrespondencePermissionTests(APITestCase):
    def setUp(self):
        organization = Organization.objects.create(name="Provider", org_type="PROVIDER")
        self.entry = User.objects.create_user("entry-feedback@example.com", "password", name="Entry", role="PROVIDER_DATA_ENTRY", organization=organization)
        self.approver = User.objects.create_user("approver-feedback@example.com", "password", name="Approver", role="PROVIDER_APPROVER", organization=organization)
        self.other_org = Organization.objects.create(name="Other Provider", org_type="PROVIDER")
        self.other_approver = User.objects.create_user("other-feedback@example.com", "password", name="Other Approver", role="PROVIDER_APPROVER", organization=self.other_org)
        self.admin = User.objects.create_user("admin-feedback@nca.org.gh", "password", name="Admin", role="NCA_ADMIN")
        self.officer = User.objects.create_user("officer-feedback@nca.org.gh", "password", name="Officer", role="NCA_OFFICER")

    def test_data_entry_has_technical_support_only(self):
        self.client.force_authenticate(self.entry)
        correspondence = self.client.post("/api/v1/feedback/", {"category": "GENERAL", "subject": "Question", "message": "Contact NCA"}, format="json")
        self.assertEqual(correspondence.status_code, 403)
        issue = self.client.post("/api/v1/issues/", {"title": "System error", "description": "The save button failed.", "severity": "HIGH"}, format="json")
        self.assertEqual(issue.status_code, 201)

    def test_provider_approver_can_send_authenticated_inquiry(self):
        self.client.force_authenticate(self.approver)
        response = self.client.post("/api/v1/feedback/", {"category": "GENERAL", "subject": "Compliance question", "message": "Please clarify the notice."}, format="json")
        self.assertEqual(response.status_code, 201)

    def test_provider_sees_only_their_own_feedback(self):
        FeedbackItem.objects.create(submitted_by=self.approver, subject="Mine", message="My feedback")
        FeedbackItem.objects.create(submitted_by=self.other_approver, subject="Other", message="Other feedback")
        self.client.force_authenticate(self.approver)
        response = self.client.get("/api/v1/feedback/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["subject"] for item in response.data], ["Mine"])

    def test_nca_can_list_and_acknowledge_feedback_once(self):
        item = FeedbackItem.objects.create(submitted_by=self.approver, subject="Portal", message="Useful suggestion")
        self.client.force_authenticate(self.officer)
        listing = self.client.get("/api/v1/feedback/")
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.data[0]["organization"], "Provider")

        response = self.client.post(f"/api/v1/feedback/{item.id}/acknowledge/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["acknowledged"])
        self.assertEqual(FeedbackNotification.objects.filter(feedback=item, recipient=self.approver).count(), 1)
        self.assertTrue(AuditEvent.objects.filter(action="FEEDBACK_ACKNOWLEDGED", entity_id=str(item.id)).exists())

        replay = self.client.post(f"/api/v1/feedback/{item.id}/acknowledge/")
        self.assertEqual(replay.status_code, 200)
        self.assertEqual(FeedbackNotification.objects.filter(feedback=item, recipient=self.approver).count(), 1)

    def test_data_entry_cannot_list_or_acknowledge_feedback(self):
        item = FeedbackItem.objects.create(submitted_by=self.approver, subject="Portal", message="Suggestion")
        self.client.force_authenticate(self.entry)
        self.assertEqual(self.client.get("/api/v1/feedback/").status_code, 403)
        self.assertEqual(self.client.post(f"/api/v1/feedback/{item.id}/acknowledge/").status_code, 403)

    def test_approver_cannot_acknowledge_feedback(self):
        item = FeedbackItem.objects.create(submitted_by=self.approver, subject="Portal", message="Suggestion")
        self.client.force_authenticate(self.approver)
        self.assertEqual(self.client.post(f"/api/v1/feedback/{item.id}/acknowledge/").status_code, 403)
