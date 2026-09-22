from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("forms_engine", "0016_formfield_source_row_formfield_source_sheet_and_more")]

    operations = [
        migrations.AddConstraint(
            model_name="formtemplate",
            constraint=models.UniqueConstraint(
                condition=models.Q(("status", "ACTIVE")), fields=("family",),
                name="one_active_version_per_form_family",
            ),
        ),
    ]
