from django.db import migrations


def rename_existing_forms(apps, schema_editor):
    Family = apps.get_model("forms_engine", "FormFamily")
    Template = apps.get_model("forms_engine", "FormTemplate")
    Family.objects.filter(code="MNO-MONTHLY").update(name="MNO-Monthly")
    Template.objects.filter(form_code="MNO-MONTHLY").update(name="MNO-Monthly")


class Migration(migrations.Migration):
    dependencies = [("forms_engine", "0019_rename_mno_catalog")]
    operations = [migrations.RunPython(rename_existing_forms, migrations.RunPython.noop)]
