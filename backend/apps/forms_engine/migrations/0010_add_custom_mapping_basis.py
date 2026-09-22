from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("forms_engine", "0009_workbook_import_and_custom_codes")]

    operations = [
        migrations.AlterField(
            model_name="formtemplate",
            name="mapping_basis",
            field=models.CharField(
                choices=[
                    ("LEGACY", "Legacy"),
                    ("PRD_SECTION_11", "PRD Section 11"),
                    ("SOURCE_FORM", "Original source form"),
                    ("CUSTOM", "Custom NCA form"),
                ],
                default="LEGACY",
                max_length=30,
            ),
        ),
    ]
