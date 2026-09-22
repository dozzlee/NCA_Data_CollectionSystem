from calendar import month_name
from datetime import datetime, timezone as dt_timezone

from django.db import migrations


UTC = dt_timezone.utc


def normalize_monthly_deadlines(apps, schema_editor):
    Period = apps.get_model("submissions", "ReportingPeriod")
    for period in Period.objects.filter(frequency="MONTHLY", month__isnull=False):
        due_year = period.year + 1 if period.month == 12 else period.year
        due_month = 1 if period.month == 12 else period.month + 1
        period.name = f"{month_name[period.month]} {period.year}"
        period.quarter = None
        period.opens_at = datetime(period.year, period.month, 1, tzinfo=UTC)
        period.due_at = datetime(due_year, due_month, 10, 23, 59, 59, tzinfo=UTC)
        period.save(update_fields=["name", "quarter", "opens_at", "due_at"])

    # Remove only empty duplicate period shells. A period carrying any
    # obligation or manual assignment remains immutable historical context.
    seen = set()
    for period in Period.objects.filter(frequency="MONTHLY").order_by(
        "year", "month", "-expected_submissions__id", "id",
    ).distinct():
        key = (period.year, period.month)
        if key not in seen:
            seen.add(key)
            continue
        if (
            not period.expected_submissions.exists()
            and not period.manual_form_assignments.exists()
            and not period.applicable_form_templates.exists()
            and not period.assigned_providers.exists()
        ):
            period.delete()


class Migration(migrations.Migration):
    dependencies = [("submissions", "0016_repair_reporting_calendar")]
    operations = [migrations.RunPython(normalize_monthly_deadlines, migrations.RunPython.noop)]
