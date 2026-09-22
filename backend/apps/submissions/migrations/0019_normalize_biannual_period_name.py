from django.db import migrations


def normalize_name(apps, schema_editor):
    Period = apps.get_model("submissions", "ReportingPeriod")
    Period.objects.filter(
        frequency="SEMI_ANNUAL", year=2026, due_at__month=12,
    ).update(name="July-December 2026")


class Migration(migrations.Migration):
    dependencies = [("submissions", "0018_clean_period_names")]
    operations = [migrations.RunPython(normalize_name, migrations.RunPython.noop)]
