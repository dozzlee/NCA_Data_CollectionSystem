from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("forms_engine", "0021_update_isp_catalog_source")]
    operations = [
        migrations.AlterField(
            model_name="formworkbookimport",
            name="parser_version",
            field=models.CharField(max_length=50, default="xlsx-worksheet-v7-data-entry-tables"),
        ),
    ]
