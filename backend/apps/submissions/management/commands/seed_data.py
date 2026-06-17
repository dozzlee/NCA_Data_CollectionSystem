from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.utils import timezone
from datetime import date
from apps.compliance.models import EmailTemplate
from apps.providers.models import ProviderProfile
from apps.submissions.models import ReportingPeriod, ExpectedSubmission, Submission, SubmissionValue
from apps.forms_engine.models import FormTemplate, FormSection, FormField
from apps.users.models import User, Organization
import random


class Command(BaseCommand):
    help = 'Seed the database with realistic test data'

    def handle(self, *args, **options):
        # If periods already exist, still backfill support data introduced later.
        if ReportingPeriod.objects.exists():
            if not FormTemplate.objects.exists():
                self.seed_form_templates()
            self.seed_email_templates()
            call_command("flag_missing_data")
            self.stdout.write(self.style.SUCCESS("✓ Database already seeded; support data refreshed."))
            return

        self.stdout.write("🌱 Seeding database with test data...")
        self.seed_email_templates()

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

        # Ensure there are active form templates. Migrations create the schema
        # only, so a fresh container needs seed templates before submissions.
        if not FormTemplate.objects.exists():
            self.seed_form_templates()

        # Use existing form templates (created by seed data or admin users).
        # Only use form codes that exist in the FORM_CODES choices.
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

        # Create users and organizations for multiple providers
        self.create_provider_users(providers[1], 'MTN Ghana Limited', 'mtn')
        self.create_provider_users(providers[2], 'AirtelTigo Ghana', 'airteltigo')
        self.create_provider_users(providers[3], 'Surfline Communications', 'surfline')

        # Create expected submissions for all providers across periods
        active_periods = list(ReportingPeriod.objects.filter(status__in=['ACTIVE', 'CLOSED']))
        created_count = 0

        # Varied statuses for realistic data
        all_statuses = ['NOT_STARTED', 'DRAFT', 'PENDING_APPROVAL', 'SUBMITTED',
                        'UNDER_REVIEW', 'CORRECTION_REQUESTED', 'APPROVED', 'REJECTED']

        # Create submissions for each provider across periods with varied states
        for provider_idx, provider in enumerate(providers[:5]):  # Create for first 5 providers
            for period_idx, period in enumerate(active_periods):
                for form_idx, form in enumerate(existing_forms[:2]):
                    # Vary status based on provider and period
                    status_idx = (provider_idx + period_idx + form_idx) % len(all_statuses)
                    status = all_statuses[status_idx]

                    es, created = ExpectedSubmission.objects.get_or_create(
                        provider=provider,
                        period=period,
                        form_template=form,
                        defaults={
                            'workflow_status': status,
                            'due_state': self.get_due_state(period, now, provider_idx % 3),
                        }
                    )

                    if created:
                        created_count += 1
                        # Create actual submission for most statuses
                        if status not in ['NOT_STARTED']:
                            completion = self.get_varied_completion(status, provider_idx)
                            sub = Submission.objects.create(
                                expected=es,
                                version=1,
                                completion_pct=completion,
                            )
                            # Add realistic field values
                            fields = list(FormField.objects.filter(section__form_template=form))
                            for field in fields[:8]:
                                SubmissionValue.objects.create(
                                    submission=sub,
                                    field=field,
                                    value=self.get_field_value(field, provider_idx),
                                    value_status=random.choice(['PROVIDED', 'NOT_APPLICABLE', 'NOT_AVAILABLE']) if field.field_code != 'reporting_contact' else 'PROVIDED',
                                )

        self.stdout.write(f"  ✓ Created {created_count} expected submissions with varied data")
        call_command("flag_missing_data")
        self.stdout.write(self.style.SUCCESS("✅ Data seeding complete with realistic test data!"))

    def create_provider_users(self, provider, org_name, email_prefix):
        org, _ = Organization.objects.get_or_create(name=org_name, defaults={'org_type': 'PROVIDER'})
        if provider.organization is None:
            provider.organization = org
            provider.save(update_fields=['organization'])

        data_entry, created = User.objects.get_or_create(
            email=f'dataentry@{email_prefix}.com.gh',
            defaults={
                'name': f'{org_name} Data Entry',
                'role': 'PROVIDER_DATA_ENTRY',
                'organization': org,
                'is_active': True,
            }
        )
        if created:
            data_entry.set_password('testpass123')
            data_entry.save()

        approver, created = User.objects.get_or_create(
            email=f'approver@{email_prefix}.com.gh',
            defaults={
                'name': f'{org_name} Approver',
                'role': 'PROVIDER_APPROVER',
                'organization': org,
                'is_active': True,
            }
        )
        if created:
            approver.set_password('testpass123')
            approver.save()

    def get_due_state(self, period, now, provider_idx):
        if period.status == 'CLOSED':
            return 'CLOSED'
        if provider_idx == 0:
            return 'OVERDUE' if period.due_at < now else 'OPEN'
        elif provider_idx == 1:
            return 'OVERDUE'
        else:
            return 'OPEN'

    def get_varied_completion(self, status, provider_idx):
        # Vary completion % by status
        completion_map = {
            'NOT_STARTED': 0,
            'DRAFT': random.randint(15, 60),
            'PENDING_APPROVAL': random.randint(80, 95),
            'SUBMITTED': random.randint(70, 95),
            'UNDER_REVIEW': random.randint(85, 100),
            'CORRECTION_REQUESTED': random.randint(50, 75),
            'APPROVED': 100,
            'REJECTED': random.randint(20, 60),
        }
        return completion_map.get(status, random.randint(40, 100))

    def get_field_value(self, field, provider_idx):
        # Generate realistic values based on field type and provider
        field_code = field.field_code
        if field_code == 'reporting_contact':
            return f'Contact {provider_idx + 1} <contact{provider_idx}@provider.com>'
        elif field_code == 'subscriber_or_site_count':
            return str(random.randint(100000, 5000000) if provider_idx % 2 == 0 else random.randint(50000, 500000))
        elif field_code == 'gross_revenue':
            return str(random.randint(1000000, 500000000))
        elif field_code == 'comments':
            return f'Submission prepared by provider team {provider_idx + 1}'
        else:
            # Generic numeric value for other fields
            return str(random.randint(10000, 999999))

    def seed_form_templates(self):
        template_data = [
            ('MNO-MONTHLY', 'MNO Monthly Return', 'MNO', 'MONTHLY'),
            ('DC-ISP06', 'Internet Service Provider Annual Return', 'ISP', 'ANNUAL'),
            ('DC-TB02', 'Pay TV Broadcasting Annual Return', 'PAY_TV', 'ANNUAL'),
            ('DC-ITC04', 'Tower Operator Annual Return', 'TOWER_OPERATOR', 'ANNUAL'),
        ]

        for form_code, name, category, frequency in template_data:
            template, created = FormTemplate.objects.get_or_create(
                form_code=form_code,
                defaults={
                    'name': name,
                    'provider_category': category,
                    'frequency': frequency,
                    'version': '1.0',
                    'effective_from': date(2024, 1, 1),
                    'status': 'ACTIVE',
                    'instructions': 'Seeded demo form template for Hugging Face testing.',
                }
            )
            if not created and template.status != 'ACTIVE':
                template.status = 'ACTIVE'
                template.save(update_fields=['status'])

            section, _ = FormSection.objects.get_or_create(
                form_template=template,
                section_code='general',
                defaults={
                    'title': 'General Information',
                    'instructions': 'Basic reporting information for this return.',
                    'sort_order': 1,
                }
            )

            fields = [
                ('reporting_contact', 'Reporting contact', 'text', ''),
                ('subscriber_or_site_count', 'Subscriber or site count', 'number', ''),
                ('gross_revenue', 'Gross revenue', 'currency', 'GHS'),
                ('active_sites', 'Number of active sites', 'number', ''),
                ('employees', 'Total employees', 'number', ''),
                ('capex', 'Capital expenditure', 'currency', 'GHS'),
                ('opex', 'Operating expenditure', 'currency', 'GHS'),
                ('comments', 'Submission comments', 'textarea', ''),
            ]
            for sort_order, (field_code, label, field_type, unit) in enumerate(fields, start=1):
                FormField.objects.get_or_create(
                    section=section,
                    field_code=field_code,
                    defaults={
                        'label': label,
                        'field_type': field_type,
                        'unit': unit,
                        'is_required': field_code != 'comments',
                        'sort_order': sort_order,
                    }
                )

            if created:
                self.stdout.write(f"  ✓ Created form template: {form_code}")

    def seed_email_templates(self):
        templates = [
            (
                'PERIOD_OPEN',
                'Regulatory Data Collection Period Open - {{period_name}}',
                'Dear {{provider_name}},\n\nThe {{period_name}} regulatory data collection period is now open. Please log in to the NCA Data Collection System to complete and submit your {{form_name}} return.\n\nDue date: {{due_date}}\n\nRegards,\nNational Communications Authority',
                ['{{provider_name}}', '{{period_name}}', '{{form_name}}', '{{due_date}}'],
            ),
            (
                'REMINDER',
                'Reminder: {{form_name}} Return Due {{due_date}}',
                'Dear {{provider_name}},\n\nThis is a reminder that your {{form_name}} submission for {{period_name}} is due on {{due_date}}.\n\nCurrent status: {{workflow_status}}\n\nPlease complete your submission in the NCA Data Collection System.\n\nRegards,\nNational Communications Authority',
                ['{{provider_name}}', '{{form_name}}', '{{period_name}}', '{{due_date}}', '{{workflow_status}}'],
            ),
            (
                'OVERDUE',
                'OVERDUE: {{form_name}} Return for {{period_name}}',
                'Dear {{provider_name}},\n\nYour {{form_name}} submission for {{period_name}} was due on {{due_date}} and has not yet been received.\n\nPlease submit your return immediately. Continued non-compliance may result in regulatory action.\n\nRegards,\nNational Communications Authority',
                ['{{provider_name}}', '{{form_name}}', '{{period_name}}', '{{due_date}}'],
            ),
            (
                'CORRECTION_REQUEST',
                'Correction Required: {{form_name}} Submission for {{period_name}}',
                'Dear {{provider_name}},\n\nYour {{form_name}} submission for {{period_name}} has been reviewed by NCA. Corrections are required before approval.\n\nPlease log in to view the required corrections and resubmit.\n\nRegards,\nNational Communications Authority',
                ['{{provider_name}}', '{{form_name}}', '{{period_name}}'],
            ),
            (
                'DRAFT_INCOMPLETE',
                'Incomplete Draft: {{form_name}} for {{period_name}}',
                'Dear {{provider_name}},\n\nYour {{form_name}} draft for {{period_name}} is incomplete. Please complete all required fields and submit before the due date.\n\nRegards,\nNational Communications Authority',
                ['{{provider_name}}', '{{form_name}}', '{{period_name}}'],
            ),
            (
                'ESCALATION',
                'Escalation Notice: {{form_name}} for {{period_name}}',
                'Dear {{provider_name}},\n\nThis submission requires urgent attention from your compliance team: {{form_name}} for {{period_name}}.\n\nRegards,\nNational Communications Authority',
                ['{{provider_name}}', '{{form_name}}', '{{period_name}}'],
            ),
        ]

        created_count = 0
        for template_type, subject, body, placeholders in templates:
            _, created = EmailTemplate.objects.update_or_create(
                template_type=template_type,
                defaults={
                    'subject': subject,
                    'body': body,
                    'placeholders': placeholders,
                },
            )
            if created:
                created_count += 1

        if created_count:
            self.stdout.write(f"  ✓ Created {created_count} email templates")
