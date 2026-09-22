import re

from django.db import migrations, models


def populate_submission_references(apps, schema_editor):
    Submission = apps.get_model("submissions", "Submission")
    for submission in Submission.objects.select_related(
        "expected__provider", "expected__form_template", "expected__period"
    ).order_by("id"):
        expected = submission.expected
        period = expected.period
        if period.frequency == "MONTHLY":
            period_token = f"{period.year}-{period.month:02d}"
        elif period.frequency == "QUARTERLY":
            period_token = f"{period.year}-Q{period.quarter}"
        elif period.frequency == "ANNUAL":
            period_token = str(period.year)
        else:
            period_token = f"{period.year}-SA-{period.id}"
        form_code = re.sub(r"[^A-Z0-9-]+", "-", expected.form_template.form_code.upper()).strip("-")
        version = re.sub(r"[^A-Z0-9.-]+", "-", expected.form_template.version.upper()).strip("-")
        reference = (
            f"{form_code}-{expected.provider.provider_code}-{period_token}"
            f"-V{version}-S{submission.id}"
        )
        Submission.objects.filter(pk=submission.pk).update(submission_reference=reference)


class Migration(migrations.Migration):
    dependencies = [
        ("providers", "0004_providerprofile_provider_code"),
        ("submissions", "0008_providerworkbookbaseline_monthlyreportartifact_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="submission",
            name="submission_reference",
            field=models.CharField(max_length=180, null=True),
        ),
        migrations.RunPython(populate_submission_references, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="submission",
            name="submission_reference",
            field=models.CharField(editable=False, max_length=180, unique=True),
        ),
    ]
