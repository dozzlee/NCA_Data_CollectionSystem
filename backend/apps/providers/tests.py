from datetime import date, timedelta
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.audit.models import AuditEvent
from apps.audit.services import verify_chain
from apps.data_requests.models import DataRequest, DataRequestArtifact
from apps.forms_engine.models import FormFamily, FormTemplate, FormWorkbookImport
from apps.submissions.models import (
    ExpectedSubmission, PeriodFormAssignment, ReportingPeriod, Submission,
    SubmissionEvent, SubmissionNotification, SubmissionReceipt,
)
from apps.uploads.models import SubmissionExcelBackup
from apps.users.models import Organization, User
from .management.commands.purge_local_mno_and_unowned_providers import (
    CONFIRMATION, MNO_ONLY_CONFIRMATION,
)
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


class LocalMNOProviderCleanupTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            "cleanup-admin@nca.test", "password", name="Cleanup Admin", role="NCA_ADMIN",
        )
        provider_org = Organization.objects.create(name="Account-backed Provider", org_type="PROVIDER")
        self.retained = ProviderProfile.objects.create(
            organization=provider_org, registered_name="Account-backed Provider", sector="TELECOM",
            category="ISP", licence_type="ISP", licence_number="KEEP-1",
            primary_email="keep@example.com", primary_phone="1",
        )
        self.data_entry = User.objects.create_user(
            "entry@keep.test", "password", name="Data Entry", role="PROVIDER_DATA_ENTRY",
            organization=provider_org, is_active=False,
        )
        self.removed = ProviderProfile.objects.create(
            registered_name="Provider Without Accounts", sector="TELECOM", category="ISP",
            licence_type="ISP", licence_number="DROP-1", primary_email="drop@example.com",
            primary_phone="2",
        )
        self.mno_family = FormFamily.objects.create(
            code="MNO-MONTHLY", name="MNO Monthly", canonical_frequency="MONTHLY",
        )
        self.mno = FormTemplate.objects.create(
            family=self.mno_family, form_code="MNO-MONTHLY", name="MNO", version="1.0",
            sector="TELECOM", provider_category="MNO", frequency="MONTHLY",
            effective_from=date(2026, 1, 1), status="ACTIVE", approval_status="APPROVED",
        )
        other_family = FormFamily.objects.create(code="KEEP-FORM", name="Keep Form", canonical_frequency="MONTHLY")
        self.other = FormTemplate.objects.create(
            family=other_family, form_code="KEEP-FORM", name="Keep Form", version="1.0",
            sector="TELECOM", provider_category="ISP", frequency="MONTHLY",
            effective_from=date(2026, 1, 1), status="ACTIVE", approval_status="APPROVED",
        )
        self.period = ReportingPeriod.objects.create(
            name="Cleanup period", frequency="MONTHLY", year=2026, month=8,
            opens_at=timezone.now() - timedelta(days=1), due_at=timezone.now() + timedelta(days=7),
            status="ACTIVE", created_by=self.admin,
        )
        mno_assignment = PeriodFormAssignment.objects.create(
            period=self.period, form_template=self.mno, provider=self.retained, assigned_by=self.admin,
        )
        removed_assignment = PeriodFormAssignment.objects.create(
            period=self.period, form_template=self.other, provider=self.removed, assigned_by=self.admin,
        )
        self.mno_expected = ExpectedSubmission.objects.create(
            provider=self.retained, form_template=self.mno, period=self.period,
            workflow_status="SUBMITTED", manual_assignment=mno_assignment,
        )
        self.removed_expected = ExpectedSubmission.objects.create(
            provider=self.removed, form_template=self.other, period=self.period,
            workflow_status="APPROVED", manual_assignment=removed_assignment,
        )
        self.mno_submission = Submission.objects.create(expected=self.mno_expected, version=1)
        self.removed_submission = Submission.objects.create(expected=self.removed_expected, version=1)
        event = SubmissionEvent.objects.create(
            submission=self.mno_submission, actor=self.admin, event_type="FORM_ASSIGNED",
            message="Assigned", audience="PROVIDER",
        )
        SubmissionNotification.objects.create(
            recipient=self.data_entry, submission=self.mno_submission, event=event,
            title="Assigned", message="Assigned",
        )

    def _create_private_records(self, upload_root, export_root):
        workbook_path = Path(upload_root) / "form-workbooks" / "mno.xlsx"
        workbook_path.parent.mkdir(parents=True); workbook_path.write_bytes(b"workbook")
        FormWorkbookImport.objects.create(
            form_code="MNO-MONTHLY", name="MNO", version="1.0", sector="TELECOM",
            provider_category="MNO", frequency="MONTHLY", file_name="mno.xlsx",
            file_size=8, storage_path="form-workbooks/mno.xlsx", sha256="a" * 64,
            scan_status="CLEAN", parse_status="CONFIRMED", parser_version="xlsx-worksheet-v3",
            created_by=self.admin, resulting_template=self.mno,
        )
        receipt_path = Path(export_root) / "receipt.pdf"; receipt_path.write_bytes(b"receipt")
        SubmissionReceipt.objects.create(
            submission=self.mno_submission, reference="TEST-RECEIPT", snapshot={},
            private_path=str(receipt_path), file_size=7, sha256="b" * 64,
        )
        backup_path = Path(upload_root) / "uploads" / "backup.xlsx"
        backup_path.parent.mkdir(parents=True); backup_path.write_bytes(b"backup")
        SubmissionExcelBackup.objects.create(
            submission=self.removed_submission, file_name="backup.xlsx", file_size=6,
            storage_path="uploads/backup.xlsx", uploaded_by=self.admin, sha256="c" * 64,
        )
        request = DataRequest.objects.create(
            requester=self.admin, requester_name=self.admin.name, requester_email=self.admin.email,
            requesting_division="Test", title="Released data", purpose="Cleanup test",
            requested_format="CSV", status="READY",
            approval_manifest={"submission_ids": [self.removed_submission.id], "field_ids": [], "grid_column_ids": []},
        )
        artifact_path = Path(export_root) / "release.csv"; artifact_path.write_bytes(b"released")
        DataRequestArtifact.objects.create(
            request=request, private_path=str(artifact_path), filename="release.csv", mime_type="text/csv",
            file_size=8, row_count=1, sha256="d" * 64, generated_by=self.admin,
            expires_at=timezone.now() + timedelta(days=30),
        )
        return workbook_path, receipt_path, backup_path, artifact_path, request

    def test_dry_run_is_non_mutating_and_commit_is_idempotent(self):
        with TemporaryDirectory() as upload_root, TemporaryDirectory() as export_root:
            files = self._create_private_records(upload_root, export_root)
            with override_settings(PRIVATE_UPLOAD_ROOT=upload_root, PRIVATE_EXPORT_ROOT=export_root, DEBUG=True):
                output = StringIO()
                call_command("purge_local_mno_and_unowned_providers", stdout=output)
                report = __import__("json").loads(output.getvalue())
                self.assertEqual(report["mode"], "dry-run")
                self.assertEqual(report["counts"]["providers"], 1)
                self.assertTrue(FormTemplate.objects.filter(form_code="MNO-MONTHLY").exists())
                self.assertTrue(ProviderProfile.objects.filter(pk=self.removed.pk).exists())

                committed = StringIO()
                call_command(
                    "purge_local_mno_and_unowned_providers", commit=True, confirm=CONFIRMATION,
                    actor_email=self.admin.email, stdout=committed,
                )
                self.assertFalse(FormTemplate.objects.filter(form_code="MNO-MONTHLY").exists())
                self.assertFalse(FormFamily.objects.filter(code="MNO-MONTHLY").exists())
                self.assertFalse(ProviderProfile.objects.filter(pk=self.removed.pk).exists())
                self.assertTrue(ProviderProfile.objects.filter(pk=self.retained.pk).exists())
                self.assertTrue(FormTemplate.objects.filter(pk=self.other.pk).exists())
                request = DataRequest.objects.get(pk=files[-1].pk)
                self.assertEqual(request.status, "EXPIRED")
                self.assertIsNotNone(request.artifact.expired_at)
                for path in files[:-1]: self.assertFalse(path.exists())
                self.assertTrue(AuditEvent.objects.filter(action="LOCAL_MNO_PROVIDER_PURGE").exists())
                self.assertEqual(verify_chain(), [])

                replay = StringIO()
                call_command(
                    "purge_local_mno_and_unowned_providers", commit=True, confirm=CONFIRMATION,
                    actor_email=self.admin.email, stdout=replay,
                )
                replay_report = __import__("json").loads(replay.getvalue())
                self.assertEqual(replay_report["counts"]["providers"], 0)
                self.assertEqual(replay_report["counts"]["form_templates"], 0)

    def test_mno_only_mode_never_targets_providers_or_unrelated_records(self):
        with TemporaryDirectory() as upload_root, TemporaryDirectory() as export_root:
            files = self._create_private_records(upload_root, export_root)
            with override_settings(PRIVATE_UPLOAD_ROOT=upload_root, PRIVATE_EXPORT_ROOT=export_root, DEBUG=True):
                output = StringIO()
                call_command("purge_local_mno_and_unowned_providers", mno_only=True, stdout=output)
                report = __import__("json").loads(output.getvalue())
                self.assertEqual(report["scope"], "MNO_ONLY")
                self.assertEqual(report["counts"]["providers"], 0)
                self.assertEqual(report["expected_submission_ids"], [self.mno_expected.id])

                committed = StringIO()
                call_command(
                    "purge_local_mno_and_unowned_providers", mno_only=True, commit=True,
                    confirm=MNO_ONLY_CONFIRMATION, actor_email=self.admin.email, stdout=committed,
                )
                self.assertFalse(FormFamily.objects.filter(code="MNO-MONTHLY").exists())
                self.assertFalse(ExpectedSubmission.objects.filter(pk=self.mno_expected.pk).exists())
                self.assertTrue(ProviderProfile.objects.filter(pk=self.removed.pk).exists())
                self.assertTrue(ProviderProfile.objects.filter(pk=self.retained.pk).exists())
                self.assertTrue(ExpectedSubmission.objects.filter(pk=self.removed_expected.pk).exists())
                self.assertTrue(FormTemplate.objects.filter(pk=self.other.pk).exists())
                self.assertFalse(files[0].exists())
                self.assertFalse(files[1].exists())
                self.assertTrue(files[2].exists())
                self.assertTrue(files[3].exists())
                request = DataRequest.objects.get(pk=files[-1].pk)
                self.assertEqual(request.status, "READY")
                self.assertTrue(AuditEvent.objects.filter(action="LOCAL_MNO_FORM_PURGE").exists())
                self.assertEqual(verify_chain(), [])

                replay = StringIO()
                call_command("purge_local_mno_and_unowned_providers", mno_only=True, stdout=replay)
                replay_report = __import__("json").loads(replay.getvalue())
                self.assertEqual(replay_report["counts"]["form_templates"], 0)
                self.assertEqual(replay_report["counts"]["submissions"], 0)

    @override_settings(DEBUG=False)
    def test_commit_is_refused_outside_local_debug(self):
        with self.assertRaises(CommandError):
            call_command(
                "purge_local_mno_and_unowned_providers", commit=True, confirm=CONFIRMATION,
                actor_email=self.admin.email,
            )
