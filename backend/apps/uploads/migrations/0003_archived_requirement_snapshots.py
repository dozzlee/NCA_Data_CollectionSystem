from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("uploads", "0002_submissionexcelbackup_scan_details_and_more")]

    operations = [
        migrations.AlterField(
            model_name="submissionkmzupload", name="requirement",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="uploads", to="forms_engine.kmzuploadrequirement"),
        ),
        migrations.AddField(model_name="submissionkmzupload", name="requirement_snapshot", field=models.JSONField(blank=True, default=dict)),
    ]
