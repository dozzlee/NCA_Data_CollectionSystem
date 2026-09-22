import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("forms_engine", "0022_data_entry_table_parser"),
        ("submissions", "0011_expected_original_workflow_status"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("uploads", "0003_archived_requirement_snapshots"),
    ]

    operations = [
        migrations.CreateModel(
            name="SubmissionFieldAttachment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("file_name", models.CharField(max_length=255)),
                ("file_size", models.PositiveIntegerField()),
                ("mime_type", models.CharField(max_length=150)),
                ("storage_path", models.CharField(max_length=500)),
                ("sha256", models.CharField(max_length=64)),
                ("uploaded_at", models.DateTimeField(auto_now_add=True)),
                ("is_current", models.BooleanField(default=True)),
                ("scan_status", models.CharField(choices=[("PENDING", "Pending"), ("CLEAN", "Clean"), ("INFECTED", "Infected"), ("ERROR", "Scan error")], default="PENDING", max_length=20)),
                ("scan_engine", models.CharField(blank=True, max_length=100)),
                ("scan_details", models.TextField(blank=True)),
                ("scanned_at", models.DateTimeField(blank=True, null=True)),
                ("field", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="submission_attachments", to="forms_engine.formfield")),
                ("submission", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="field_attachments", to="submissions.submission")),
                ("uploaded_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="field_attachments", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-uploaded_at"]},
        ),
        migrations.AddConstraint(
            model_name="submissionfieldattachment",
            constraint=models.UniqueConstraint(condition=models.Q(("is_current", True)), fields=("submission", "field"), name="one_current_attachment_per_field"),
        ),
    ]
