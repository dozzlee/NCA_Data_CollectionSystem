from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APITestCase
from openpyxl import Workbook
from io import BytesIO

from apps.users.models import User
from .models import FormGapAssessment, FormTemplate, GridRow, ValidationRule, FormWorkbookImport


class PRDSection11FormTests(TestCase):
    def setUp(self):
        User.objects.create_user("prd-admin@nca.test", "password", name="Admin", role="NCA_ADMIN")
        User.objects.create_user("prd-officer@nca.test", "password", name="Officer", role="NCA_OFFICER")

    def test_loader_builds_exact_section_11_versions_and_publishes_provisional_tower_code(self):
        with TemporaryDirectory() as directory:
            source = Path(directory) / "Product Requirements Document - Development Ready.docx"
            source.write_bytes(b"section-11-test-source")
            call_command("load_prd_section11", source=str(source), verbosity=0)
        active = FormTemplate.objects.filter(status="ACTIVE", approval_status="APPROVED")
        self.assertEqual(active.count(), 7)
        self.assertEqual(set(active.values_list("form_code", flat=True)), {"MNO-MONTHLY", "DC-TB02", "DC-ISP06", "DC-ITC04", "TOWER-MAIN-ANNUAL", "DC-DBS05", "DC-SUB03"})
        tower = FormTemplate.objects.get(form_code="TOWER-MAIN-ANNUAL", version="2.0")
        self.assertEqual(tower.status, "ACTIVE")
        self.assertEqual(tower.family.code_status, "PROVISIONAL")
        self.assertTrue(tower.gap_assessments.filter(requirement__requirement_type="SOURCE_DECISION", status="MATCHED").exists())
        mno = active.get(form_code="MNO-MONTHLY")
        brands = list(GridRow.objects.filter(grid__section__form_template=mno, grid__grid_code="phone_brand_counts").values_list("row_label", flat=True))
        self.assertIn("Samsung", brands)
        self.assertIn("Itel", brands)
        self.assertFalse(mno.sections.filter(grids__grid_code="industry_subscriptions_metrics").exists())
        self.assertEqual(mno.version, "3.0")
        self.assertEqual(active.get(form_code="DC-DBS05").frequency, "ANNUAL")
        self.assertTrue(active.get(form_code="DC-DBS05").kmz_requirements.exists())
        self.assertFalse(active.get(form_code="DC-SUB03").kmz_requirements.exists())
        for rule in ValidationRule.objects.filter(form_template__in=active):
            rule.full_clean()


class WorkbookFormImportTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user("workbook-admin@nca.test", "password", name="Admin", role="NCA_ADMIN")
        self.client.force_authenticate(self.admin)

    def workbook_file(self):
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Subscriber Data"
        sheet.append(["Indicator", "Value"])
        sheet.append(["Total subscribers", 999999])
        sheet.append(["Churn rate (%)", 0.12])
        sheet.add_table(__import__("openpyxl").worksheet.table.Table(displayName="SubscriberMetrics", ref="A1:B3"))
        out = BytesIO(); workbook.save(out)
        return SimpleUploadedFile("source.xlsx", out.getvalue(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    @override_settings(MALWARE_SCANNER_REQUIRED=False)
    def test_workbook_import_generates_schema_only_and_confirms_draft(self):
        with TemporaryDirectory() as private_root:
            with override_settings(PRIVATE_UPLOAD_ROOT=private_root):
                response = self.client.post("/api/v1/form-workbook-imports/", {
                    "form_code": "NEW-QUARTERLY", "name": "New Quarterly Return", "version": "1.0",
                    "sector": "TELECOM", "provider_category": "ISP", "frequency": "QUARTERLY",
                    "file": self.workbook_file(),
                }, format="multipart")
                self.assertEqual(response.status_code, 201, response.data)
                item = FormWorkbookImport.objects.get(pk=response.data["id"])
                self.assertEqual(item.parse_status, "READY")
                self.assertNotIn("999999", str(item.detected_schema))
                confirmed = self.client.post(f"/api/v1/form-workbook-imports/{item.id}/confirm/", {}, format="json")
                self.assertEqual(confirmed.status_code, 201, confirmed.data)
                form = FormTemplate.objects.get(pk=confirmed.data["id"])
                self.assertEqual(form.form_code, "NEW-QUARTERLY")
                self.assertEqual(form.frequency, "QUARTERLY")
                self.assertEqual(form.mapping_basis, "SOURCE_FORM")
