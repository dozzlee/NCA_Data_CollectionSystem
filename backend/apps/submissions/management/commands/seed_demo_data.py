from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.compliance.models import EmailLog, EmailTemplate
from apps.forms_engine.models import (
    FormField,
    FormSection,
    FormTemplate,
    GridColumn,
    KMZUploadRequirement,
)
from apps.providers.models import ProviderContact, ProviderProfile
from apps.submissions.models import ExpectedSubmission, ReportingPeriod, ReviewAction, Submission
from apps.users.models import Organization, User


class Command(BaseCommand):
    help = "Seed a compact demo dataset for local testing."

    def handle(self, *args, **options):
        now = timezone.now()
        nca_org, _ = Organization.objects.get_or_create(
            name="National Communications Authority",
            defaults={"org_type": "NCA"},
        )
        nca_org.org_type = "NCA"
        nca_org.save(update_fields=["org_type"])

        admin = self.ensure_user(
            email="admin@nca.local",
            password="AdminPass123!",
            name="Local NCA Admin",
            role="NCA_ADMIN",
            organization=nca_org,
            is_staff=True,
            is_superuser=True,
        )
        officer = self.ensure_user(
            email="officer@nca.org.gh",
            password="OfficerPass123!",
            name="Ama Compliance Officer",
            role="NCA_OFFICER",
            organization=nca_org,
            is_staff=True,
        )

        providers = self.seed_providers()
        templates = self.seed_form_templates(now)
        periods = self.seed_periods(now, admin, templates, providers)
        expected = self.seed_expected_submissions(periods, providers, templates, officer)
        self.seed_submission_versions(expected, officer)
        self.seed_email_templates()
        self.seed_email_logs(expected, admin)

        self.stdout.write(self.style.SUCCESS("Seeded demo data."))
        self.stdout.write(f"Providers: {ProviderProfile.objects.count()}")
        self.stdout.write(f"Periods: {ReportingPeriod.objects.count()}")
        self.stdout.write(f"Expected submissions: {ExpectedSubmission.objects.count()}")
        self.stdout.write("Login: admin@nca.local / AdminPass123!")

    def ensure_user(self, email, password, name, role, organization, **flags):
        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                "name": name,
                "role": role,
                "organization": organization,
                "is_active": True,
                **flags,
            },
        )
        updates = []
        for field, value in {
            "name": name,
            "role": role,
            "organization": organization,
            "is_active": True,
            **flags,
        }.items():
            if getattr(user, field) != value:
                setattr(user, field, value)
                updates.append(field)
        user.set_password(password)
        updates.append("password")
        if updates:
            user.save()
        return user

    def seed_providers(self):
        rows = [
            {
                "registered_name": "Ghana Mobile Networks Ltd",
                "trade_name": "GhanaMobile",
                "category": "MNO",
                "licence_type": "Mobile Network Operator",
                "licence_number": "NCA/MNO/001/2026",
                "primary_email": "regulatory@ghanamobile.example",
                "primary_phone": "+233302555010",
                "digital_address": "GA-184-4421",
            },
            {
                "registered_name": "AccraNet ISP Services Ltd",
                "trade_name": "AccraNet",
                "category": "ISP",
                "licence_type": "Internet Service Provider",
                "licence_number": "NCA/ISP/028/2026",
                "primary_email": "compliance@accranet.example",
                "primary_phone": "+233302555020",
                "digital_address": "GA-244-1289",
            },
            {
                "registered_name": "Gold Coast Pay TV Ltd",
                "trade_name": "GoldView",
                "category": "PAY_TV",
                "licence_type": "Pay TV Broadcasting",
                "licence_number": "NCA/PTV/014/2026",
                "primary_email": "returns@goldview.example",
                "primary_phone": "+233302555030",
                "digital_address": "GA-488-9002",
            },
            {
                "registered_name": "TowerGrid Ghana Ltd",
                "trade_name": "TowerGrid",
                "category": "TOWER_OPERATOR",
                "licence_type": "Tower Operator",
                "licence_number": "NCA/TWR/006/2026",
                "primary_email": "nca@towergrid.example",
                "primary_phone": "+233302555040",
                "digital_address": "GA-932-7710",
            },
            {
                "registered_name": "MainMast Infrastructure Ltd",
                "trade_name": "MainMast",
                "category": "TOWER_MAIN",
                "licence_type": "Tower Main Infrastructure",
                "licence_number": "NCA/TWM/003/2026",
                "primary_email": "compliance@mainmast.example",
                "primary_phone": "+233302555050",
                "digital_address": "GA-592-4411",
            },
            {
                "registered_name": "FibreLink Domestic Ghana Ltd",
                "trade_name": "FibreLink",
                "category": "DOMESTIC_FIBRE",
                "licence_type": "Domestic Fibre",
                "licence_number": "NCA/DBS/012/2026",
                "primary_email": "regulatory@fibrelink.example",
                "primary_phone": "+233302555060",
                "digital_address": "GA-332-6804",
            },
            {
                "registered_name": "SubSea Cable Ghana Ltd",
                "trade_name": "SubSea Ghana",
                "category": "SUBMARINE_FIBRE",
                "licence_type": "Submarine Fibre",
                "licence_number": "NCA/SUB/002/2026",
                "primary_email": "nca@subseaghana.example",
                "primary_phone": "+233302555070",
                "digital_address": "GA-122-5588",
            },
        ]

        providers = {}
        for row in rows:
            org, _ = Organization.objects.get_or_create(
                name=row["registered_name"],
                defaults={"org_type": "PROVIDER"},
            )
            provider, _ = ProviderProfile.objects.update_or_create(
                licence_number=row["licence_number"],
                defaults={
                    **row,
                    "organization": org,
                    "status": "ACTIVE",
                    "physical_address": "Independence Avenue, Accra",
                    "postal_address": "P.O. Box CT 1000, Accra",
                    "website": "https://example.com",
                    "licence_issue_date": timezone.now().date().replace(year=2024),
                    "licence_expiry_date": timezone.now().date().replace(year=2029),
                },
            )
            ProviderContact.objects.update_or_create(
                provider=provider,
                email=row["primary_email"],
                defaults={
                    "name": f"{row['trade_name']} Compliance Desk",
                    "designation": "Regulatory Affairs Lead",
                    "phone": row["primary_phone"],
                    "notification_role": "Compliance",
                    "is_active": True,
                },
            )
            providers[row["category"]] = provider
        return providers

    def seed_form_templates(self, now):
        rows = [
            ("MNO-MONTHLY", "MNO Monthly Return", "MNO", "MONTHLY", False),
            ("DC-ISP06", "Internet Service Provider Annual Return", "ISP", "ANNUAL", False),
            ("DC-TB02", "Pay TV Broadcasting Annual Return", "PAY_TV", "ANNUAL", False),
            ("DC-ITC04", "Tower Operator Annual Return", "TOWER_OPERATOR", "ANNUAL", False),
            ("TOWER-MAIN-ANNUAL", "Tower Main Annual Return", "TOWER_MAIN", "ANNUAL", False),
            ("DC-DBS05", "Domestic Fibre Semi-Annual Return", "DOMESTIC_FIBRE", "SEMI_ANNUAL", True),
            ("DC-SUB03", "Submarine Fibre Annual Return", "SUBMARINE_FIBRE", "ANNUAL", True),
        ]

        templates = {}
        for form_code, name, category, frequency, kmz_required in rows:
            template, _ = FormTemplate.objects.update_or_create(
                form_code=form_code,
                defaults={
                    "name": name,
                    "provider_category": category,
                    "frequency": frequency,
                    "version": "1.0",
                    "effective_from": now.date().replace(month=1, day=1),
                    "status": "ACTIVE",
                    "kmz_required": kmz_required,
                    "excel_backup_enabled": True,
                    "instructions": "Demo template with representative regulatory fields.",
                },
            )
            section, _ = FormSection.objects.update_or_create(
                form_template=template,
                section_code="general",
                defaults={
                    "title": "General Information",
                    "instructions": "Provider identity and reporting summary.",
                    "sort_order": 1,
                    "kmz_upload_required": False,
                },
            )
            FormField.objects.update_or_create(
                section=section,
                field_code="reporting_contact",
                defaults={
                    "label": "Reporting contact",
                    "field_type": "text",
                    "unit": "",
                    "is_required": True,
                    "sort_order": 1,
                },
            )
            FormField.objects.update_or_create(
                section=section,
                field_code="subscriber_or_site_count",
                defaults={
                    "label": "Subscriber or site count",
                    "field_type": "number",
                    "unit": "",
                    "is_required": True,
                    "sort_order": 2,
                },
            )
            grid, _ = section.grids.update_or_create(
                grid_code="regional_summary",
                defaults={
                    "title": "Regional Summary",
                    "row_mode": "REPEATABLE",
                    "sort_order": 3,
                },
            )
            GridColumn.objects.update_or_create(
                grid=grid,
                column_code="region",
                defaults={"label": "Region", "field_type": "text", "is_required": True, "sort_order": 1},
            )
            GridColumn.objects.update_or_create(
                grid=grid,
                column_code="value",
                defaults={"label": "Value", "field_type": "number", "is_required": True, "sort_order": 2},
            )
            if kmz_required:
                KMZUploadRequirement.objects.update_or_create(
                    form_template=template,
                    category="ROUTE",
                    defaults={
                        "section": section,
                        "description": "Upload the current route/topology KMZ for this fibre network.",
                        "is_required": True,
                        "max_file_size_mb": 50,
                    },
                )
            templates[form_code] = template
        return templates

    def seed_periods(self, now, admin, templates, providers):
        specs = [
            {
                "name": "June 2026 Monthly Returns",
                "frequency": "MONTHLY",
                "year": 2026,
                "month": 6,
                "opens_at": now - timedelta(days=2),
                "due_at": now + timedelta(days=12),
                "status": "ACTIVE",
                "forms": ["MNO-MONTHLY"],
                "provider_keys": ["MNO"],
            },
            {
                "name": "2026 Annual Returns",
                "frequency": "ANNUAL",
                "year": 2026,
                "month": None,
                "opens_at": now - timedelta(days=30),
                "due_at": now + timedelta(days=5),
                "status": "ACTIVE",
                "forms": ["DC-ISP06", "DC-TB02", "DC-ITC04", "TOWER-MAIN-ANNUAL", "DC-SUB03"],
                "provider_keys": ["ISP", "PAY_TV", "TOWER_OPERATOR", "TOWER_MAIN", "SUBMARINE_FIBRE"],
            },
            {
                "name": "2026 Fibre H1 Returns",
                "frequency": "SEMI_ANNUAL",
                "year": 2026,
                "month": None,
                "opens_at": now - timedelta(days=45),
                "due_at": now - timedelta(days=3),
                "status": "ACTIVE",
                "forms": ["DC-DBS05", "DC-SUB03"],
                "provider_keys": ["DOMESTIC_FIBRE", "SUBMARINE_FIBRE"],
            },
            {
                "name": "2025 Annual Closeout",
                "frequency": "ANNUAL",
                "year": 2025,
                "month": None,
                "opens_at": now - timedelta(days=420),
                "due_at": now - timedelta(days=360),
                "status": "CLOSED",
                "forms": ["DC-ISP06", "DC-TB02", "DC-ITC04", "TOWER-MAIN-ANNUAL"],
                "provider_keys": ["ISP", "PAY_TV", "TOWER_OPERATOR", "TOWER_MAIN"],
            },
        ]

        periods = {}
        for spec in specs:
            period, _ = ReportingPeriod.objects.update_or_create(
                name=spec["name"],
                defaults={
                    "frequency": spec["frequency"],
                    "year": spec["year"],
                    "month": spec["month"],
                    "opens_at": spec["opens_at"],
                    "due_at": spec["due_at"],
                    "status": spec["status"],
                    "created_by": admin,
                },
            )
            period.applicable_form_templates.set([templates[code] for code in spec["forms"]])
            period.assigned_providers.set([providers[key] for key in spec["provider_keys"]])
            periods[spec["name"]] = period
        return periods

    def seed_expected_submissions(self, periods, providers, templates, officer):
        expected = {}
        for period in periods.values():
            for provider in period.assigned_providers.all():
                for form in period.applicable_form_templates.filter(provider_category=provider.category):
                    obj, _ = ExpectedSubmission.objects.get_or_create(
                        provider=provider,
                        form_template=form,
                        period=period,
                        defaults={"assigned_officer": officer},
                    )
                    if obj.assigned_officer_id is None:
                        obj.assigned_officer = officer
                        obj.save(update_fields=["assigned_officer"])
                    expected[(period.name, provider.category)] = obj

        status_plan = {
            ("June 2026 Monthly Returns", "MNO"): "DRAFT",
            ("2026 Annual Returns", "ISP"): "NOT_STARTED",
            ("2026 Annual Returns", "PAY_TV"): "SUBMITTED",
            ("2026 Annual Returns", "TOWER_OPERATOR"): "CORRECTION_REQUESTED",
            ("2026 Annual Returns", "TOWER_MAIN"): "APPROVED",
            ("2026 Annual Returns", "SUBMARINE_FIBRE"): "UNDER_REVIEW",
            ("2026 Fibre H1 Returns", "DOMESTIC_FIBRE"): "NOT_STARTED",
            ("2026 Fibre H1 Returns", "SUBMARINE_FIBRE"): "DRAFT",
            ("2025 Annual Closeout", "ISP"): "APPROVED",
            ("2025 Annual Closeout", "PAY_TV"): "APPROVED",
            ("2025 Annual Closeout", "TOWER_OPERATOR"): "APPROVED",
            ("2025 Annual Closeout", "TOWER_MAIN"): "REJECTED",
        }
        for key, status in status_plan.items():
            obj = expected.get(key)
            if not obj:
                continue
            obj.workflow_status = status
            obj.assigned_officer = officer
            obj.save(update_fields=["workflow_status", "assigned_officer"])
            obj.refresh_due_state()
        return expected

    def seed_submission_versions(self, expected, officer):
        submitted_statuses = {"SUBMITTED", "UNDER_REVIEW", "CORRECTION_REQUESTED", "APPROVED", "REJECTED"}
        for obj in expected.values():
            if obj.workflow_status not in submitted_statuses:
                continue
            submission, _ = Submission.objects.get_or_create(expected=obj, version=1)
            submission.completion_pct = Decimal("100.00") if obj.workflow_status == "APPROVED" else Decimal("82.00")
            submission.submitted_by = officer
            submission.submitted_at = obj.period.due_at - timedelta(days=2)
            if obj.workflow_status in {"APPROVED", "REJECTED", "CORRECTION_REQUESTED"}:
                submission.reviewed_by = officer
                submission.reviewed_at = obj.period.due_at + timedelta(days=1)
            submission.save()
            if obj.workflow_status == "CORRECTION_REQUESTED":
                ReviewAction.objects.get_or_create(
                    submission=submission,
                    action="REQUEST_CORRECTION",
                    target_type="SECTION",
                    target_id="general",
                    defaults={
                        "comment": "Please verify the regional summary totals and resubmit.",
                        "is_provider_visible": True,
                        "created_by": officer,
                    },
                )

    def seed_email_templates(self):
        templates = [
            (
                "PERIOD_OPEN",
                "Regulatory Data Collection Period Open - {{period_name}}",
                "Dear {{provider_name}},\n\nThe {{period_name}} period is open. Please submit {{form_name}} by {{due_date}}.",
            ),
            (
                "REMINDER",
                "Reminder: {{form_name}} Return Due {{due_date}}",
                "Dear {{provider_name}},\n\nThis is a reminder that {{form_name}} for {{period_name}} is due on {{due_date}}.",
            ),
            (
                "OVERDUE",
                "OVERDUE: {{form_name}} Return for {{period_name}}",
                "Dear {{provider_name}},\n\nYour {{form_name}} submission for {{period_name}} is overdue.",
            ),
            (
                "CORRECTION_REQUEST",
                "Correction Required: {{form_name}} Submission for {{period_name}}",
                "Dear {{provider_name}},\n\nCorrections are required for {{form_name}}.",
            ),
        ]
        placeholders = ["{{provider_name}}", "{{period_name}}", "{{form_name}}", "{{due_date}}", "{{workflow_status}}"]
        for template_type, subject, body in templates:
            EmailTemplate.objects.update_or_create(
                template_type=template_type,
                defaults={"subject": subject, "body": body, "placeholders": placeholders},
            )

    def seed_email_logs(self, expected, admin):
        targets = [
            (("2026 Fibre H1 Returns", "DOMESTIC_FIBRE"), "OVERDUE"),
            (("2026 Fibre H1 Returns", "SUBMARINE_FIBRE"), "OVERDUE"),
            (("2026 Annual Returns", "TOWER_OPERATOR"), "CORRECTION_REQUEST"),
        ]
        for key, template_type in targets:
            obj = expected.get(key)
            if not obj:
                continue
            template = EmailTemplate.objects.get(template_type=template_type)
            subject = template.subject
            replacements = {
                "{{provider_name}}": obj.provider.registered_name,
                "{{form_name}}": obj.form_template.name,
                "{{period_name}}": obj.period.name,
                "{{due_date}}": obj.period.due_at.strftime("%d %B %Y"),
                "{{workflow_status}}": obj.workflow_status,
            }
            for token, value in replacements.items():
                subject = subject.replace(token, value)
            EmailLog.objects.get_or_create(
                provider=obj.provider,
                expected_submission=obj,
                period=obj.period,
                compliance_stage=template_type,
                defaults={
                    "template": template,
                    "subject": subject,
                    "body": template.body,
                    "recipients": [{"email": obj.provider.primary_email, "name": obj.provider.registered_name}],
                    "generated_by": admin,
                    "status": "DRAFT",
                },
            )
