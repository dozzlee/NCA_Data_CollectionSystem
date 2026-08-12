from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management import call_command
from django.test import TestCase

from apps.users.models import User
from .models import FormGapAssessment, FormTemplate, GridRow, ValidationRule


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
