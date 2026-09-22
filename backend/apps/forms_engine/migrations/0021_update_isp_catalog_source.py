from django.db import migrations


def update_isp_source(apps, schema_editor):
    Catalog = apps.get_model("forms_engine", "FormCodeCatalog")
    Catalog.objects.filter(code="DC-ISP06").update(
        source_filename="NCA_ISP_DC-ISP06_Annual_Template.xlsx"
    )


class Migration(migrations.Migration):
    dependencies = [("forms_engine", "0020_rename_existing_mno_forms")]
    operations = [migrations.RunPython(update_isp_source, migrations.RunPython.noop)]
