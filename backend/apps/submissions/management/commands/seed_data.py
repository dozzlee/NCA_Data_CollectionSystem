from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import date
from apps.providers.models import ProviderProfile
from apps.submissions.models import ReportingPeriod, ExpectedSubmission, Submission, SubmissionValue
from apps.forms_engine.models import FormTemplate, FormSection, FormField
from apps.users.models import User, Organization
import random


class Command(BaseCommand):
    help = 'Seed the database with realistic test data'

    def handle(self, *args, **options):
        # Skip if already seeded
        if ReportingPeriod.objects.exists():
            self.stdout.write(self.style.SUCCESS("✓ Database already seeded, skipping."))
            return

        self.stdout.write("🌱 Seeding database with test data...")

        # Get or create an admin user to satisfy created_by FK
        admin, _ = User.objects.get_or_create(
            email='admin@nca.org.gh',
            defaults={
                'name': 'NCA Administrator',
                'role': 'NCA_ADMIN',
                'is_active': True,
                'is_staff': True,
                'is_superuser': True,
            }
        )
        if _:
            admin.set_password('testpass123')
            admin.save()
            self.stdout.write("  ✓ Created NCA Admin user")

        # Create NCA Officer
        officer, _ = User.objects.get_or_create(
            email='officer.asante@nca.org.gh',
            defaults={
                'name': 'Kwame Asante',
                'role': 'NCA_OFFICER',
                'is_active': True,
            }
        )
        if _:
            officer.set_password('testpass123')
            officer.save()
            self.stdout.write("  ✓ Created NCA Officer user")

        # Create providers
        provider_data = [
            ('Vodafone Ghana Limited', 'VOD-GH-001', 'MNO', 'admin@vodafone.com.gh'),
            ('MTN Ghana Limited', 'MTN-GH-001', 'MNO', 'admin@mtn.com.gh'),
            ('AirtelTigo Ghana', 'ART-GH-001', 'MNO', 'admin@airteltigo.com.gh'),
            ('Surfline Communications', 'SUR-GH-001', 'ISP', 'admin@surfline.com.gh'),
            ('Busy Internet', 'BSY-GH-001', 'ISP', 'admin@busy.com.gh'),
            ('StarTimes Ghana', 'STA-GH-001', 'PAY_TV', 'admin@startimes.com.gh'),
            ('ATC Ghana', 'ATC-GH-001', 'TOWER_OPERATOR', 'admin@atcghana.com'),
        ]

        providers = []
        for reg_name, lic_num, category, email in provider_data:
            p, created = ProviderProfile.objects.get_or_create(
                licence_number=lic_num,
                defaults={
                    'registered_name': reg_name,
                    'category': category,
                    'status': 'ACTIVE',
                    'primary_email': email,
                    'primary_phone': '+233 30 000 0000',
                }
            )
            providers.append(p)
            if created:
                self.stdout.write(f"  ✓ Created provider: {reg_name}")

        # Create provider users for Vodafone
        vodafone = providers[0]

        # Create an Organisation record and link it to the Vodafone provider profile
        vod_org, _ = Organization.objects.get_or_create(
            name='Vodafone Ghana Limited',
            defaults={'org_type': 'PROVIDER'}
        )
        # Link the org to the provider profile so RBAC works
        if vodafone.organization is None:
            vodafone.organization = vod_org
            vodafone.save(update_fields=['organization'])

        data_entry, _ = User.objects.get_or_create(
            email='dataentry@vodafone.com.gh',
            defaults={
                'name': 'Vodafone Data Entry',
                'role': 'PROVIDER_DATA_ENTRY',
                'organization': vod_org,
                'is_active': True,
            }
        )
        if _:
            data_entry.set_password('testpass123')
            data_entry.save()
            self.stdout.write("  ✓ Created Provider Data Entry user")

        approver, _ = User.objects.get_or_create(
            email='admin@vodafone.com.gh',
            defaults={
                'name': 'Vodafone Approver',
                'role': 'PROVIDER_APPROVER',
                'organization': vod_org,
                'is_active': True,
            }
        )
        if _:
            approver.set_password('testpass123')
            approver.save()
            self.stdout.write("  ✓ Created Provider Approver user")

        # Use existing form templates (created by migrations/fixtures)
        # Only use form codes that exist in the FORM_CODES choices
        existing_forms = list(FormTemplate.objects.filter(status='ACTIVE'))

        if not existing_forms:
            # Try any form templates
            existing_forms = list(FormTemplate.objects.all())

        if not existing_forms:
            self.stdout.write("  ⚠ No form templates found. Skipping submissions seeding.")
            self.stdout.write(self.style.SUCCESS("✅ Partial seeding complete (users + providers only)!"))
            return

        self.stdout.write(f"  ✓ Found {len(existing_forms)} form template(s)")

        # Create reporting periods (using actual model fields)
        now = timezone.now()
        periods = []

        period_configs = [
            ('Q1 2024', 2024, 'ANNUAL', date(2024, 1, 1),
             timezone.make_aware(timezone.datetime(2024, 1, 1)),
             timezone.make_aware(timezone.datetime(2024, 3, 31)), 'CLOSED'),
            ('Q2 2024', 2024, 'ANNUAL', date(2024, 4, 1),
             timezone.make_aware(timezone.datetime(2024, 4, 1)),
             timezone.make_aware(timezone.datetime(2024, 6, 30)), 'CLOSED'),
            ('Q3 2024', 2024, 'ANNUAL', date(2024, 7, 1),
             timezone.make_aware(timezone.datetime(2024, 7, 1)),
             timezone.make_aware(timezone.datetime(2024, 9, 30)), 'CLOSED'),
            ('Q4 2024', 2024, 'ANNUAL', date(2024, 10, 1),
             timezone.make_aware(timezone.datetime(2024, 10, 1)),
             timezone.make_aware(timezone.datetime(2024, 12, 31)), 'ACTIVE'),
            ('Q1 2025', 2025, 'ANNUAL', date(2025, 1, 1),
             timezone.make_aware(timezone.datetime(2025, 1, 1)),
             timezone.make_aware(timezone.datetime(2025, 3, 31)), 'ACTIVE'),
        ]

        for p_name, p_year, p_freq, p_eff, p_opens, p_due, p_status in period_configs:
            p, created = ReportingPeriod.objects.get_or_create(
                name=p_name,
                defaults={
                    'year': p_year,
                    'frequency': p_freq,
                    'opens_at': p_opens,
                    'due_at': p_due,
                    'status': p_status,
                    'created_by': admin,
                }
            )
            if created:
                # Link all providers and a form template
                p.assigned_providers.set(providers)
                p.applicable_form_templates.set(existing_forms[:2])
                periods.append(p)
                self.stdout.write(f"  ✓ Created period: {p_name}")

        if not periods:
            self.stdout.write("  ⚠ No periods created (may already exist)")

        # Create expected submissions for Vodafone across active periods
        active_periods = ReportingPeriod.objects.filter(status__in=['ACTIVE', 'CLOSED'])
        created_count = 0

        statuses = ['NOT_STARTED', 'DRAFT', 'SUBMITTED', 'APPROVED', 'UNDER_REVIEW']

        for i, period in enumerate(active_periods[:4]):
            form = existing_forms[i % len(existing_forms)]
            status = statuses[i % len(statuses)]

            es, created = ExpectedSubmission.objects.get_or_create(
                provider=vodafone,
                period=period,
                form_template=form,
                defaults={
                    'workflow_status': status,
                    'due_state': 'OVERDUE' if period.due_at < now else 'ON_TIME',
                }
            )

            if created:
                created_count += 1
                # Create actual submission for non-NOT_STARTED statuses
                if status not in ['NOT_STARTED']:
                    sub = Submission.objects.create(
                        expected=es,
                        version=1,
                        completion_pct=random.randint(40, 100),
                    )
                    # Add sample values for fields in this form
                    fields = FormField.objects.filter(section__form_template=form)[:5]
                    for field in fields:
                        SubmissionValue.objects.create(
                            submission=sub,
                            field=field,
                            value=str(random.randint(10000, 999999)),
                            value_status='PROVIDED',
                        )

        self.stdout.write(f"  ✓ Created {created_count} expected submissions")
        self.stdout.write(self.style.SUCCESS("✅ Data seeding complete!"))
