from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("forms_engine", "0010_add_custom_mapping_basis")]

    operations = [
        migrations.AlterField(
            model_name="formworkbookimport",
            name="parser_version",
            field=models.CharField(default="xlsx-semantic-v2", max_length=30),
        ),
    ]
