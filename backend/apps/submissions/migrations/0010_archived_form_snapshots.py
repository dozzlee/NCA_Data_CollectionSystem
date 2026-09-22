from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("submissions", "0009_submission_reference")]

    operations = [
        migrations.AlterField(
            model_name="expectedsubmission", name="form_template",
            field=models.ForeignKey(
                blank=True, help_text="Null only for archived obligations whose immutable form identity/schema was snapshotted.",
                null=True, on_delete=django.db.models.deletion.SET_NULL, to="forms_engine.formtemplate",
            ),
        ),
        migrations.AddField(model_name="expectedsubmission", name="form_code_snapshot", field=models.CharField(blank=True, max_length=50)),
        migrations.AddField(model_name="expectedsubmission", name="form_name_snapshot", field=models.CharField(blank=True, max_length=255)),
        migrations.AddField(model_name="expectedsubmission", name="form_version_snapshot", field=models.CharField(blank=True, max_length=20)),
        migrations.AddField(model_name="expectedsubmission", name="form_frequency_snapshot", field=models.CharField(blank=True, max_length=15)),
        migrations.AddField(model_name="expectedsubmission", name="form_sector_snapshot", field=models.CharField(blank=True, max_length=20)),
        migrations.AddField(model_name="expectedsubmission", name="form_provider_category_snapshot", field=models.CharField(blank=True, max_length=30)),
        migrations.AddField(model_name="expectedsubmission", name="form_source_reference_snapshot", field=models.CharField(blank=True, max_length=500)),
        migrations.AddField(model_name="expectedsubmission", name="form_created_at_snapshot", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="submission", name="form_schema_snapshot", field=models.JSONField(blank=True, default=dict)),
        migrations.AddField(model_name="submission", name="form_schema_sha256", field=models.CharField(blank=True, editable=False, max_length=64)),
        migrations.AddField(model_name="submission", name="form_schema_snapshot_version", field=models.PositiveSmallIntegerField(default=1)),
        migrations.AddField(model_name="submissionvalue", name="target_key_snapshot", field=models.CharField(blank=True, db_index=True, max_length=255)),
        migrations.AddField(model_name="submissionvalue", name="target_snapshot", field=models.JSONField(blank=True, default=dict)),
        migrations.RemoveConstraint(model_name="submissionvalue", name="submission_value_exactly_one_target"),
        migrations.AddConstraint(
            model_name="submissionvalue",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(("field__isnull", False), ("grid__isnull", True), ("grid_column__isnull", True))
                    | models.Q(("field__isnull", True), ("grid__isnull", False), ("grid_column__isnull", False))
                    | models.Q(("field__isnull", True), ("grid__isnull", True), ("grid_column__isnull", True), ("target_key_snapshot__gt", ""))
                ),
                name="submission_value_exactly_one_target",
            ),
        ),
        migrations.AlterField(
            model_name="monthlyreportartifact", name="baseline",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="artifacts", to="submissions.providerworkbookbaseline"),
        ),
        migrations.AddField(model_name="monthlyreportartifact", name="baseline_snapshot", field=models.JSONField(blank=True, default=dict)),
    ]
