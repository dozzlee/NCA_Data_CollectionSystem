from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("forms_engine", "0014_visible_row_workbook_parser")]

    operations = [
        migrations.AlterField(
            model_name="formworkbookimport",
            name="parser_version",
            field=models.CharField(
                default="xlsx-worksheet-v6-visible-rows-matrix-grids",
                max_length=50,
            ),
        ),
    ]
