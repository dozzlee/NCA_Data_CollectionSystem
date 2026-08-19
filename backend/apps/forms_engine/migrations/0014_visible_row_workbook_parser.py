from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("forms_engine", "0013_form_headings_and_definition_parser")]

    operations = [
        migrations.AlterField(
            model_name="formworkbookimport",
            name="parser_version",
            field=models.CharField(default="xlsx-worksheet-v5-visible-rows", max_length=50),
        ),
    ]
