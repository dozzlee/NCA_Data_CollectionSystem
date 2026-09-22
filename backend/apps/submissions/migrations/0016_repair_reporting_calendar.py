from datetime import datetime, timezone as dt_timezone

from django.db import migrations


UTC = dt_timezone.utc


def at_end(year, month, day):
    return datetime(year, month, day, 23, 59, 59, tzinfo=UTC)


def repair_calendar(apps, schema_editor):
    Period = apps.get_model("submissions", "ReportingPeriod")
    User = apps.get_model("users", "User")

    # Repair legacy records that were named as quarters but stored as annual.
    for year in (2024, 2025):
        for quarter in range(1, 5):
            Period.objects.filter(
                name=f"Q{quarter} {year}", frequency="ANNUAL",
            ).update(frequency="QUARTERLY", quarter=quarter, month=None)

    creator = User.objects.filter(role="NCA_ADMIN").order_by("created_at", "id").first()
    if creator is None:
        creator = User.objects.order_by("created_at", "id").first()
    if creator is None:
        return

    schedule = {
        7: (datetime(2026, 7, 1, tzinfo=UTC), at_end(2026, 8, 10)),
        8: (datetime(2026, 8, 1, tzinfo=UTC), at_end(2026, 9, 10)),
        9: (datetime(2026, 9, 1, tzinfo=UTC), at_end(2026, 10, 10)),
        10: (datetime(2026, 10, 1, tzinfo=UTC), at_end(2026, 11, 10)),
        11: (datetime(2026, 11, 1, tzinfo=UTC), at_end(2026, 12, 10)),
        12: (datetime(2026, 12, 1, tzinfo=UTC), at_end(2027, 1, 10)),
    }
    month_names = {
        7: "July 2026", 8: "August 2026", 9: "September 2026",
        10: "October 2026", 11: "November 2026", 12: "December 2026",
    }
    for month, (opens_at, due_at) in schedule.items():
        matching = Period.objects.filter(
            frequency="MONTHLY", year=2026, month=month,
        ).order_by("id")
        period = matching.first()
        if period is None and month == 10:
            period = Period.objects.filter(
                frequency="MONTHLY", year=2026, name__iexact="October",
            ).order_by("id").first()
        if period is None and month >= 10:
            period = Period(created_by_id=creator.id, status="DRAFT")
        if period is None:
            continue
        period.name = month_names[month]
        period.frequency = "MONTHLY"
        period.year = 2026
        period.month = month
        period.quarter = None
        period.opens_at = opens_at
        period.due_at = due_at
        period.save()
        matching.exclude(pk=period.pk).filter(
            expected_submissions__isnull=True,
            manual_form_assignments__isnull=True,
        ).delete()

    Period.objects.get_or_create(
        name="July-December 2026",
        frequency="SEMI_ANNUAL",
        year=2026,
        defaults={
            "month": None, "quarter": None,
            "opens_at": datetime(2026, 7, 1, tzinfo=UTC),
            "due_at": at_end(2026, 12, 31),
            "status": "DRAFT", "created_by_id": creator.id,
        },
    )


class Migration(migrations.Migration):
    dependencies = [
        ("forms_engine", "0024_convert_annual_forms_to_biannual"),
        ("submissions", "0015_expectedsubmission_penalty"),
    ]
    operations = [migrations.RunPython(repair_calendar, migrations.RunPython.noop)]
