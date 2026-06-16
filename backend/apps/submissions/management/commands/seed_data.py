from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from apps.providers.models import ProviderProfile
from apps.submissions.models import ReportingPeriod, FormTemplate, ExpectedSubmission, Submission, SubmissionValue
from apps.forms_engine.models import FormField
import random

class Command(BaseCommand):
    help = 'Seed the database with realistic test data'

    def handle(self, *args, **options):
        # Skip if data already seeded (idempotent)
        if ReportingPeriod.objects.filter(name__contains="2024").exists():
            self.stdout.write(self.style.SUCCESS("✓ Database already seeded, skipping."))
            return

        self.stdout.write("🌱 Seeding database with test data...")

        # Create periods
        periods = []
        for month in range(1, 13):
            year = 2024 if month <= 6 else 2025
            due_date = timezone.make_aware(timezone.datetime(year, month, 28))
            p, created = ReportingPeriod.objects.get_or_create(
                name=f"Q{(month-1)//3 + 1} {year}",
                defaults={
                    'year': year,
                    'quarter': (month - 1) // 3 + 1,
                    'due_at': due_date,
                    'status': 'ACTIVE' if month <= 6 else 'UPCOMING'
                }
            )
            if created:
                periods.append(p)
                self.stdout.write(f"  ✓ Created period: {p.name}")

        # Create forms
        forms = {}
        form_names = [
            ('FORM-001', 'Quarterly Subscriber Report'),
            ('FORM-002', 'Network Coverage Report'),
            ('FORM-003', 'Financial Summary'),
        ]
        
        for code, name in form_names:
            f, created = FormTemplate.objects.get_or_create(
                form_code=code,
                defaults={'name': name, 'description': f'Template for {name}'}
            )
            if created:
                forms[code] = f
                # Create sample fields
                for i, field_name in enumerate(['Total Subscribers', 'Active Users', 'Revenue (GHS)', 'Infrastructure Cost']):
                    FormField.objects.get_or_create(
                        form_template=f,
                        field_name=field_name,
                        defaults={
                            'field_code': f'{code}-F{i+1}',
                            'field_type': 'NUMERIC' if 'GHS' in field_name or 'Cost' in field_name else 'NUMERIC',
                            'is_required': True,
                            'order': i,
                        }
                    )
                self.stdout.write(f"  ✓ Created form: {code}")

        # Create/Get providers
        providers = []
        provider_data = [
            ('Vodafone Ghana', 'VOD-001', 'MNO'),
            ('MTN Ghana', 'MTN-001', 'MNO'),
            ('AirtelTigo', 'ART-001', 'MNO'),
            ('Zain Ghana', 'ZAI-001', 'MNO'),
            ('Surfline', 'SUR-001', 'ISP'),
            ('Busy Internet', 'BSY-001', 'ISP'),
            ('StarTimes', 'STA-001', 'PAY_TV'),
        ]
        
        for name, lic_num, category in provider_data:
            p, created = ProviderProfile.objects.get_or_create(
                licence_number=lic_num,
                defaults={
                    'registered_name': name,
                    'category': category,
                    'status': 'ACTIVE',
                    'primary_email': f'admin@{name.lower().replace(" ", "")}.com.gh',
                    'primary_phone': '+233 XX XXX XXXX'
                }
            )
            if created:
                providers.append(p)
                self.stdout.write(f"  ✓ Created provider: {name}")

        # Create expected submissions
        created_count = 0
        for provider in providers:
            for period in periods[:4]:  # Only recent periods
                es, created = ExpectedSubmission.objects.get_or_create(
                    provider=provider,
                    period=period,
                    form_template=random.choice(list(forms.values())),
                    defaults={
                        'workflow_status': random.choice(['NOT_STARTED', 'DRAFT', 'SUBMITTED']),
                        'due_state': 'ON_TIME' if period.due_at > timezone.now() else 'OVERDUE',
                        'due_at_override': None
                    }
                )
                if created:
                    created_count += 1
                    # Create sample submission if status is DRAFT or SUBMITTED
                    if es.workflow_status in ['DRAFT', 'SUBMITTED']:
                        sub = Submission.objects.create(
                            expected_submission=es,
                            provider=provider,
                            status='SUBMITTED' if es.workflow_status == 'SUBMITTED' else 'DRAFT'
                        )
                        # Add sample values
                        form_fields = es.form_template.formfield_set.all()
                        for field in form_fields:
                            SubmissionValue.objects.create(
                                submission=sub,
                                form_field=field,
                                value=str(random.randint(10000, 999999)),
                                grid_row_id='row1' if field.field_type == 'GRID' else None
                            )

        self.stdout.write(f"  ✓ Created {created_count} expected submissions with sample data")
        self.stdout.write(self.style.SUCCESS("✅ Data seeding complete!"))
