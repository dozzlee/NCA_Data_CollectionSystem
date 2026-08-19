import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("submissions", "0006_period_form_assignments"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="SectionSaveReceipt",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("client_save_id", models.UUIDField()),
                ("section_code", models.CharField(max_length=50)),
                ("payload_sha256", models.CharField(max_length=64)),
                ("base_revision", models.PositiveIntegerField()),
                ("resulting_revision", models.PositiveIntegerField()),
                ("persisted_change_version", models.PositiveIntegerField(default=0)),
                ("response", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("actor", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="section_save_receipts", to=settings.AUTH_USER_MODEL)),
                ("submission", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="section_save_receipts", to="submissions.submission")),
            ],
            options={"ordering": ["-created_at", "-id"]},
        ),
        migrations.AddConstraint(
            model_name="sectionsavereceipt",
            constraint=models.UniqueConstraint(fields=("submission", "client_save_id"), name="unique_submission_client_section_save"),
        ),
    ]
