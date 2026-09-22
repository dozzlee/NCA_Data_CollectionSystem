from django.db import migrations


def clean_period_names(apps, schema_editor):
    Period = apps.get_model("submissions", "ReportingPeriod")
    for period in Period.objects.filter(name__contains="\u2013"):
        period.name = period.name.replace("\u2013", "-")
        period.save(update_fields=["name"])


class Migration(migrations.Migration):
    dependencies = [("submissions", "0017_normalize_monthly_deadlines")]
    operations = [migrations.RunPython(clean_period_names, migrations.RunPython.noop)]
