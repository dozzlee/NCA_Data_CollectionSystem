from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("forms_engine", "0004_formfamily_validationrule_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="FormRequirement",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("requirement_key", models.CharField(max_length=120)),
                ("requirement_type", models.CharField(choices=[("SECTION", "Section"), ("SPECIAL_HANDLING", "Special handling")], max_length=30)),
                ("label", models.CharField(max_length=255)),
                ("description", models.TextField()),
                ("severity", models.CharField(choices=[("BLOCKER", "Blocker"), ("HIGH", "High"), ("MEDIUM", "Medium"), ("LOW", "Low")], default="HIGH", max_length=10)),
                ("criteria", models.JSONField(blank=True, default=dict)),
                ("source_reference", models.CharField(default="Product Requirements Document - Development Ready.docx, Section 11", max_length=500)),
                ("sort_order", models.PositiveIntegerField(default=0)),
                ("family", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="requirements", to="forms_engine.formfamily")),
            ],
            options={"ordering": ["sort_order", "id"]},
        ),
        migrations.CreateModel(
            name="FormGapAssessment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("MISSING", "Missing"), ("PARTIAL", "Partial"), ("MATCHED", "Matched"), ("NOT_APPLICABLE", "Not applicable")], default="MISSING", max_length=20)),
                ("evidence", models.TextField(blank=True)),
                ("resolution_note", models.TextField(blank=True)),
                ("assessed_at", models.DateTimeField(blank=True, null=True)),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
                ("assessed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="form_gaps_assessed", to=settings.AUTH_USER_MODEL)),
                ("form_template", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="gap_assessments", to="forms_engine.formtemplate")),
                ("owner", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="form_gaps_owned", to=settings.AUTH_USER_MODEL)),
                ("requirement", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="assessments", to="forms_engine.formrequirement")),
                ("resolved_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="form_gaps_resolved", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["requirement__sort_order", "id"]},
        ),
        migrations.AddConstraint(model_name="formrequirement", constraint=models.UniqueConstraint(fields=("family", "requirement_key"), name="unique_family_requirement_key")),
        migrations.AddConstraint(model_name="formgapassessment", constraint=models.UniqueConstraint(fields=("form_template", "requirement"), name="unique_form_requirement_assessment")),
    ]
