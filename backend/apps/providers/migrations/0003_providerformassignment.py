from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("forms_engine", "0004_formfamily_validationrule_and_more"),
        ("providers", "0002_providerprofile_sector"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProviderFormAssignment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("obligation", models.CharField(choices=[("REQUIRED", "Required"), ("OPTIONAL", "Optional"), ("EXEMPT", "Exempt")], default="REQUIRED", max_length=20)),
                ("effective_from", models.DateField()),
                ("effective_to", models.DateField(blank=True, null=True)),
                ("source_reference", models.CharField(max_length=500)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("confirmed_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="confirmed_provider_form_assignments", to=settings.AUTH_USER_MODEL)),
                ("form_family", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="provider_assignments", to="forms_engine.formfamily")),
                ("provider", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="form_assignments", to="providers.providerprofile")),
            ],
            options={"ordering": ["provider__registered_name", "form_family__code", "-effective_from"]},
        ),
        migrations.AddConstraint(
            model_name="providerformassignment",
            constraint=models.UniqueConstraint(fields=("provider", "form_family", "effective_from"), name="unique_official_provider_form_effective_date"),
        ),
    ]
