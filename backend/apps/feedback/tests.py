from rest_framework.test import APITestCase

from apps.users.models import Organization, User


class ProviderCorrespondencePermissionTests(APITestCase):
    def setUp(self):
        organization = Organization.objects.create(name="Provider", org_type="PROVIDER")
        self.entry = User.objects.create_user("entry-feedback@example.com", "password", name="Entry", role="PROVIDER_DATA_ENTRY", organization=organization)
        self.approver = User.objects.create_user("approver-feedback@example.com", "password", name="Approver", role="PROVIDER_APPROVER", organization=organization)

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
