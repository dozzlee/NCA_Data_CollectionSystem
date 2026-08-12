from datetime import date

from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APITestCase

from apps.forms_engine.models import FormFamily
from apps.users.models import User
from .models import ProviderFormAssignment, ProviderProfile


class ProviderFormRegisterTests(APITestCase):
    def setUp(self):
        self.officer = User.objects.create_user("coverage-officer@nca.test", "password", name="Officer", role="NCA_OFFICER")
        self.provider = ProviderProfile.objects.create(registered_name="Official Test ISP", sector="TELECOM", category="ISP", licence_type="ISP", licence_number="ISP-1", primary_email="isp@example.com", primary_phone="1")
        self.family = FormFamily.objects.create(code="DC-ISP06", name="ISP", canonical_frequency="ANNUAL")
        self.client.force_authenticate(self.officer)

    def csv_file(self):
        content = f"provider_id,form_code,obligation,effective_from,effective_to,source_reference\n{self.provider.provider_id},DC-ISP06,REQUIRED,2026-01-01,,NCA official register 2026\n"
        return SimpleUploadedFile("assignments.csv", content.encode("utf-8"), content_type="text/csv")

    def test_validated_dry_run_and_commit(self):
        dry_run = self.client.post("/api/v1/provider-form-assignments/import/", {"file": self.csv_file(), "dry_run": "true"}, format="multipart")
        self.assertEqual(dry_run.status_code, 200, dry_run.data)
        self.assertTrue(dry_run.data["dry_run"])
        self.assertEqual(ProviderFormAssignment.objects.count(), 0)
        commit = self.client.post("/api/v1/provider-form-assignments/import/", {"file": self.csv_file(), "dry_run": "false"}, format="multipart")
        self.assertEqual(commit.status_code, 201, commit.data)
        self.assertEqual(ProviderFormAssignment.objects.get().confirmed_by, self.officer)

    def test_overlapping_official_assignments_are_rejected(self):
        ProviderFormAssignment.objects.create(provider=self.provider, form_family=self.family, obligation="REQUIRED", effective_from=date(2026, 1, 1), source_reference="Official list", confirmed_by=self.officer)
        response = self.client.post("/api/v1/provider-form-assignments/", {"provider": self.provider.id, "form_family": self.family.id, "obligation": "REQUIRED", "effective_from": "2026-06-01", "source_reference": "Replacement"}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_standalone_coverage_endpoint_is_removed(self):
        response = self.client.get("/api/v1/provider-form-coverage/")
        self.assertEqual(response.status_code, 404)
