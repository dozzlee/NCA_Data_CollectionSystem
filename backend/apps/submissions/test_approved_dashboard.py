from copy import deepcopy
from django.utils import timezone
from rest_framework.test import APITestCase
from apps.forms_engine.models import FormSection, FormField
from .models import SubmissionValue
from .approved_dashboard import overlay_approved_submissions, add_complete_quarters
from .industry_dashboard import dataset_for_user
from .test_remediation import CommunicationSubmissionPenaltyRemediationTests


class ApprovedDashboardTests(APITestCase):
    setUp = CommunicationSubmissionPenaltyRemediationTests.setUp

    def baseline(self):
        return {"metadata": {}, "charts": [], "sectors": [], "operators": [],
                "periods": ["Q1 2025"], "industryOverview": {"chartIds": []}}

    def indicator(self, code="TOTAL_MOBILE_CELLULAR_VOICE_SUBSCRIPTIONS_PREPAID_POSTPAID"):
        self.form.form_code = "MNO-MONTHLY"
        self.form.family = None
        self.form.save()
        section = FormSection.objects.create(form_template=self.form, section_code="SUBSCRIPTIONS", title="Subscriptions")
        return FormField.objects.create(section=section, field_code=code, label="Subscriptions", field_type="number")

    def approve(self, submission):
        submission.regulatory_status = "APPROVED"
        submission.reviewed_at = timezone.now()
        submission.save()

    def test_only_latest_approved_replaces_provider_period_without_mutating_baseline(self):
        field = self.indicator()
        for submission, amount in [(self.returned, "100"), (self.latest, "200")]:
            SubmissionValue.objects.create(submission=submission, field=field, value=amount, value_status="PROVIDED")
        self.approve(self.returned)
        baseline = self.baseline()
        baseline["charts"] = [{"id":"voice-subs-market-share", "series":[
            {"name":self.provider.registered_name, "aggregation":"yearEnd", "values":[
                {"period":"Q1 2025","value":50}, {"period":"2026-09","value":75}]},
            {"name":"Other provider","aggregation":"yearEnd","values":[{"period":"2026-09","value":300}]}
        ]}]
        before = deepcopy(baseline)
        result = overlay_approved_submissions(baseline)
        self.assertEqual(result["charts"][0]["series"][0]["values"][-1]["value"], 100)
        self.approve(self.latest)
        result = overlay_approved_submissions(baseline)
        self.assertEqual(result["charts"][0]["series"][0]["values"][-1]["value"], 200)
        self.assertEqual(result["charts"][0]["series"][1]["values"][0]["value"], 300)
        self.assertEqual(baseline, before)
        self.assertEqual(result, overlay_approved_submissions(baseline))
        provider_result = dataset_for_user(result, self.approver)
        self.assertFalse(any(c.get("approvedSources") for c in provider_result["charts"]))

    def test_new_services_and_annual_observations_do_not_become_monthly(self):
        field = self.indicator("REVENUE")
        self.form.form_code = "DC-TB02"
        self.form.family = None
        self.form.provider_category = "PAY_TV"
        self.form.save()
        self.period.frequency = "ANNUAL"
        self.period.month = None
        self.period.save()
        SubmissionValue.objects.create(submission=self.latest, field=field, value="12", value_status="PROVIDED")
        self.approve(self.latest)
        result = overlay_approved_submissions(self.baseline())
        self.assertTrue({"broadcasting","fibre","fixed","mobile","bwa"} <= {s["id"] for s in result["sectors"]})
        self.assertEqual(result["charts"][0]["sectorId"], "broadcasting")
        self.assertEqual(result["charts"][0]["series"][0]["values"], [{"period":"2026","value":12}])
        self.assertFalse(result["metadata"]["monthlyDataAvailable"])

    def test_quarter_requires_three_months_and_uses_metric_aggregation(self):
        series = {"aggregation":"sum","values":[{"period":"Q1 2026","value":100},
            {"period":"2026-01","value":10},{"period":"2026-02","value":20}]}
        add_complete_quarters(series)
        self.assertEqual(next(p["value"] for p in series["values"] if p["period"]=="Q1 2026"),100)
        series["values"].append({"period":"2026-03","value":30})
        add_complete_quarters(series)
        self.assertEqual(next(p["value"] for p in series["values"] if p["period"]=="Q1 2026"),60)

    def test_mobile_fibre_indicator_is_listed_only_under_fibre(self):
        field = self.indicator("FIBRE_TO_THE_HOME_BUILDING_INTERNET_SUBSCRIPTIONS")
        SubmissionValue.objects.create(submission=self.latest, field=field, value="42", value_status="PROVIDED")
        self.approve(self.latest)
        result = overlay_approved_submissions(self.baseline())
        chart = result["charts"][0]
        self.assertEqual(chart["sectorId"], "fibre")
        mobile = next(s for s in result["sectors"] if s["id"] == "mobile")
        self.assertFalse(any(chart["id"] in section["chartIds"] for section in mobile["sections"]))
        self.assertNotIn("internet", [s["id"] for s in result["sectors"]])

    def test_isp_indicators_belong_to_bwa(self):
        field = self.indicator("TOTAL_REVENUE")
        self.form.provider_category = "ISP"
        self.form.save()
        SubmissionValue.objects.create(submission=self.latest, field=field, value="30", value_status="PROVIDED")
        self.approve(self.latest)
        self.assertEqual(overlay_approved_submissions(self.baseline())["charts"][0]["sectorId"], "bwa")
