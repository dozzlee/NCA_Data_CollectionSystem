from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("compliance", "0008_incomingemailattachment"),
        ("submissions", "0012_submissionvalue_source_reference_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ExternalEmailHandoff",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("action", models.CharField(max_length=80)),
                ("recipients", models.JSONField(default=list)),
                ("subject", models.CharField(max_length=500)),
                ("body", models.TextField()),
                ("status", models.CharField(choices=[("AVAILABLE", "Available"), ("OPENED", "Opened in email application"), ("DEFERRED", "Deferred")], default="AVAILABLE", max_length=12)),
                ("opened_at", models.DateTimeField(blank=True, null=True)),
                ("deferred_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("communication", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="email_handoff", to="compliance.communicationrecord")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="email_handoffs_created", to=settings.AUTH_USER_MODEL)),
                ("event", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="email_handoff", to="submissions.submissionevent")),
                ("opened_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="email_handoffs_opened", to=settings.AUTH_USER_MODEL)),
                ("submission", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="email_handoffs", to="submissions.submission")),
            ],
            options={"ordering": ["-created_at", "-id"]},
        ),
    ]
