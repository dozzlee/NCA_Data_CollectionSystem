from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("forms_engine", "0011_semantic_workbook_parser_default")]

    operations = [
        migrations.AlterField(
            model_name="formworkbookimport",
            name="parser_version",
            field=models.CharField(default="xlsx-worksheet-v3", max_length=30),
        ),
    ]
