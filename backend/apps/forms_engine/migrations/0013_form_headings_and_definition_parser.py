from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("forms_engine", "0012_workbook_parser_worksheet_tabs")]

    operations = [
        migrations.CreateModel(
            name="FormHeading",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("heading_code", models.CharField(max_length=100)),
                ("title", models.CharField(max_length=255)),
                ("level", models.PositiveSmallIntegerField(default=1)),
                ("sort_order", models.PositiveIntegerField(default=0)),
                ("source_row", models.PositiveIntegerField(default=0)),
                ("section", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="headings", to="forms_engine.formsection")),
            ],
            options={"ordering": ["sort_order", "id"]},
        ),
        migrations.AddField(
            model_name="formfield",
            name="heading",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="fields", to="forms_engine.formheading"),
        ),
        migrations.AddConstraint(
            model_name="formheading",
            constraint=models.UniqueConstraint(fields=("section", "heading_code"), name="unique_section_heading_code"),
        ),
        migrations.AddConstraint(
            model_name="formheading",
            constraint=models.CheckConstraint(condition=models.Q(("level__gte", 1), ("level__lte", 3)), name="form_heading_level_1_to_3"),
        ),
        migrations.AlterField(
            model_name="formworkbookimport",
            name="parser_version",
            field=models.CharField(default="xlsx-worksheet-v4-definition-headings", max_length=50),
        ),
    ]
