from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("forms_engine", "0009_workbook_import_and_custom_codes"),
        ("providers", "0003_providerformassignment"),
        ("submissions", "0005_provider_workspace"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.AddField(model_name="reportingperiod", name="quarter", field=models.PositiveIntegerField(blank=True, null=True)),
        migrations.AlterField(
            model_name="reportingperiod", name="frequency",
            field=models.CharField(choices=[("MONTHLY", "Monthly"), ("QUARTERLY", "Quarterly"), ("SEMI_ANNUAL", "Semi-Annual"), ("ANNUAL", "Annual")], max_length=15),
        ),
        migrations.CreateModel(
            name="PeriodFormAssignment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("mismatch_override_reason", models.TextField(blank=True)), ("created_at", models.DateTimeField(auto_now_add=True)),
                ("assigned_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="period_form_assignments", to=settings.AUTH_USER_MODEL)),
                ("form_template", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="period_assignments", to="forms_engine.formtemplate")),
                ("period", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="manual_form_assignments", to="submissions.reportingperiod")),
                ("provider", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="period_form_assignments", to="providers.providerprofile")),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddConstraint(model_name="periodformassignment", constraint=models.UniqueConstraint(fields=("period", "form_template", "provider"), name="unique_manual_period_form_provider")),
        migrations.AddField(
            model_name="expectedsubmission", name="manual_assignment",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="expected_submissions", to="submissions.periodformassignment"),
        ),
        migrations.AddField(
            model_name="expectedsubmission", name="recurring_assignment",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="expected_submissions", to="providers.providerformassignment"),
        ),
    ]
