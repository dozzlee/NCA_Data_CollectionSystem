from django.db import migrations


def rename_mno(apps, schema_editor):
    Catalog = apps.get_model("forms_engine", "FormCodeCatalog")
    Catalog.objects.filter(code="MNO-MONTHLY").update(name="MNO-Monthly")


class Migration(migrations.Migration):
    dependencies = [("forms_engine", "0018_form_code_catalog")]
    operations = [migrations.RunPython(rename_mno, migrations.RunPython.noop)]
