from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("forms_engine", "0006_alter_prd_form_code_labels")]

    operations = [
        migrations.AddField(
            model_name="formtemplate",
            name="mapping_basis",
            field=models.CharField(
                choices=[("LEGACY", "Legacy"), ("PRD_SECTION_11", "PRD Section 11"), ("SOURCE_FORM", "Original source form")],
                default="LEGACY", max_length=30,
            ),
        ),
        migrations.AddField(
            model_name="formgrid", name="min_rows", field=models.PositiveIntegerField(default=0),
        ),
        migrations.AlterField(
            model_name="validationrule", name="parameters", field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AlterField(
            model_name="formrequirement", name="requirement_type",
            field=models.CharField(choices=[
                ("SECTION", "Section"), ("FIELD", "Field"), ("GRID", "Grid"),
                ("GRID_COLUMN", "Grid column"), ("FIXED_ROWS", "Fixed rows"),
                ("OPTION", "Option"), ("UNIT", "Unit"), ("VALIDATION", "Validation"),
                ("CONDITIONAL", "Conditional"), ("FORMULA", "Formula"),
                ("DECLARATION", "Declaration"), ("KMZ", "KMZ upload"),
                ("SOURCE_DECISION", "Source decision"), ("SPECIAL_HANDLING", "Special handling"),
            ], max_length=30),
        ),
    ]
