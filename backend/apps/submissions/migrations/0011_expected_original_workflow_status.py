from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("submissions", "0010_archived_form_snapshots")]

    operations = [
        migrations.AddField(
            model_name="expectedsubmission", name="workflow_status_snapshot",
            field=models.CharField(blank=True, max_length=30),
        ),
    ]
