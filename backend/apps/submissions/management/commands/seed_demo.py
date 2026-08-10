from datetime import date, timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.forms_engine.models import FormField, FormSection, FormTemplate
from apps.providers.models import ProviderProfile
from apps.submissions.models import ExpectedSubmission, ReportingPeriod
from apps.users.models import Organization, User


class Command(BaseCommand):
    help = "Create repeatable development-only MTN/Vodafone workflow demo data."

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("seed_demo is disabled unless DEBUG=True.")

        nca_org, _ = Organization.objects.get_or_create(name="National Communications Authority", org_type="NCA")
        providers = {}
        for name, domain, licence in (
            ("MTN Ghana", "mtn.com.gh", "MNO-MTN-001"),
            ("Vodafone Ghana", "vodafone.com.gh", "MNO-VOD-001"),
        ):
            organization, _ = Organization.objects.get_or_create(name=name, org_type="PROVIDER")
            profile, _ = ProviderProfile.objects.update_or_create(
                organization=organization,
                defaults={
                    "registered_name": name, "trade_name": name.split()[0],
                    "category": "MNO", "licence_type": "Mobile Network Operator",
                    "licence_number": licence, "primary_email": f"regulatory@{domain}",
                    "primary_phone": "+233 20 000 0000", "status": "ACTIVE",
                },
            )
            providers[domain] = profile

        accounts = (
            ("admin@nca.org.gh", "System Administrator", "NCA_ADMIN", nca_org, "Admin1234!"),
            ("officer.mensah@nca.org.gh", "NCA Officer Mensah", "NCA_OFFICER", nca_org, "Officer1234!"),
            ("data@mtn.com.gh", "MTN Data Entry", "PROVIDER_DATA_ENTRY", providers["mtn.com.gh"].organization, "Provider1234!"),
            ("approver@mtn.com.gh", "MTN Approver", "PROVIDER_APPROVER", providers["mtn.com.gh"].organization, "Approver1234!"),
            ("data@vodafone.com.gh", "Vodafone Data Entry", "PROVIDER_DATA_ENTRY", providers["vodafone.com.gh"].organization, "Provider1234!"),
            ("approver@vodafone.com.gh", "Vodafone Approver", "PROVIDER_APPROVER", providers["vodafone.com.gh"].organization, "Approver1234!"),
        )
        for email, name, role, organization, password in accounts:
            user, _ = User.objects.update_or_create(
                email=email,
                defaults={
                    "name": name, "role": role, "organization": organization,
                    "is_active": True,
                },
            )
            user.set_password(password)
            user.save(update_fields=["password"])

        User.objects.filter(
            email__in=("admin@mtn.com.gh", "admin@vodafone.com.gh")
        ).update(is_active=False)

        template, _ = FormTemplate.objects.update_or_create(
            form_code="MNO-MONTHLY",
            defaults={
                "name": "MNO Monthly Return (Demo)", "provider_category": "MNO",
                "frequency": "MONTHLY", "version": "1.0",
                "effective_from": date.today(), "status": "ACTIVE",
                "instructions": "Development demonstration form for the provider workflow.",
            },
        )
        general, _ = FormSection.objects.update_or_create(
            form_template=template, section_code="GENERAL",
            defaults={"title": "General Information", "sort_order": 1},
        )
        declaration, _ = FormSection.objects.update_or_create(
            form_template=template, section_code="DECLARATION",
            defaults={"title": "Declaration", "sort_order": 2},
        )
        for section, code, label, field_type, order in (
            (general, "REPORTING_CONTACT", "Reporting contact", "text", 1),
            (general, "TOTAL_SUBSCRIBERS", "Total active subscribers", "number", 2),
            (general, "ACTIVE_SITES", "Number of active network sites", "number", 3),
            (declaration, "ACCURATE_DECLARATION", "I confirm that this return is accurate", "declaration", 1),
        ):
            FormField.objects.update_or_create(
                section=section, field_code=code,
                defaults={
                    "label": label, "field_type": field_type,
                    "is_required": True, "sort_order": order,
                },
            )

        now = timezone.now()
        period, _ = ReportingPeriod.objects.update_or_create(
            name="MNO Monthly Demo",
            defaults={
                "frequency": "MONTHLY", "year": now.year, "month": now.month,
                "opens_at": now - timedelta(days=1), "due_at": now + timedelta(days=14),
                "status": "ACTIVE", "created_by": User.objects.get(email="admin@nca.org.gh"),
            },
        )
        period.applicable_form_templates.set([template])
        period.assigned_providers.set(providers.values())
        for provider in providers.values():
            ExpectedSubmission.objects.get_or_create(
                provider=provider, form_template=template, period=period,
                defaults={"workflow_status": "NOT_STARTED", "due_state": "OPEN"},
            )

        self.stdout.write(self.style.SUCCESS(
            "Demo data ready: six accounts, MTN/Vodafone, and an active MNO form."
        ))
