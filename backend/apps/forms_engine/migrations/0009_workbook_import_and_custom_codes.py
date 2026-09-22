from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("forms_engine", "0008_formfamily_code_status"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.AlterField(model_name="formfamily", name="code", field=models.CharField(max_length=50, unique=True)),
        migrations.AlterField(
            model_name="formfamily", name="canonical_frequency",
            field=models.CharField(blank=True, choices=[("MONTHLY", "Monthly"), ("QUARTERLY", "Quarterly"), ("SEMI_ANNUAL", "Semi-Annual"), ("ANNUAL", "Annual")], max_length=15),
        ),
        migrations.AlterField(model_name="formtemplate", name="form_code", field=models.CharField(max_length=50)),
        migrations.AlterField(
            model_name="formtemplate", name="frequency",
            field=models.CharField(choices=[("MONTHLY", "Monthly"), ("QUARTERLY", "Quarterly"), ("SEMI_ANNUAL", "Semi-Annual"), ("ANNUAL", "Annual")], max_length=15),
        ),
        migrations.CreateModel(
            name="FormWorkbookImport",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("form_code", models.CharField(max_length=50)), ("name", models.CharField(max_length=255)),
                ("version", models.CharField(max_length=20)),
                ("sector", models.CharField(choices=[("TELECOM", "Telecom"), ("BROADCASTING", "Broadcasting")], max_length=20)),
                ("provider_category", models.CharField(max_length=30)),
                ("frequency", models.CharField(choices=[("MONTHLY", "Monthly"), ("QUARTERLY", "Quarterly"), ("SEMI_ANNUAL", "Semi-Annual"), ("ANNUAL", "Annual")], max_length=15)),
                ("file_name", models.CharField(max_length=255)), ("file_size", models.PositiveIntegerField()),
                ("storage_path", models.CharField(max_length=500)), ("sha256", models.CharField(max_length=64)),
                ("scan_status", models.CharField(choices=[("PENDING", "Pending"), ("CLEAN", "Clean"), ("INFECTED", "Infected"), ("ERROR", "Error")], default="PENDING", max_length=20)),
                ("scan_engine", models.CharField(blank=True, max_length=100)), ("scan_details", models.TextField(blank=True)),
                ("parse_status", models.CharField(choices=[("PENDING", "Pending"), ("READY", "Ready"), ("FAILED", "Failed"), ("CONFIRMED", "Confirmed")], default="PENDING", max_length=20)),
                ("parser_version", models.CharField(default="xlsx-schema-v1", max_length=30)),
                ("detected_schema", models.JSONField(blank=True, default=dict)), ("warnings", models.JSONField(blank=True, default=list)),
                ("mapping_decisions", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="form_workbook_imports", to=settings.AUTH_USER_MODEL)),
                ("resulting_template", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="workbook_import", to="forms_engine.formtemplate")),
            ],
            options={"ordering": ["-created_at"]},
        ),
    ]
