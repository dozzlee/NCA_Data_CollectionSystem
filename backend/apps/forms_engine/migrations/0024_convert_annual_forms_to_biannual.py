from django.db import migrations


def convert_to_biannual(apps, schema_editor):
    Catalog = apps.get_model("forms_engine", "FormCodeCatalog")
    Family = apps.get_model("forms_engine", "FormFamily")
    Template = apps.get_model("forms_engine", "FormTemplate")

    Catalog.objects.filter(frequency="ANNUAL").update(frequency="SEMI_ANNUAL")
    Family.objects.filter(canonical_frequency="ANNUAL").update(
        canonical_frequency="SEMI_ANNUAL",
    )
    Template.objects.filter(frequency="ANNUAL").update(frequency="SEMI_ANNUAL")

    for model in (Catalog, Family, Template):
        for row in model.objects.filter(name__icontains="Annual"):
            row.name = row.name.replace("Annual", "Bi-Annual").replace(
                "annual", "bi-annual",
            )
            row.save(update_fields=["name"])


class Migration(migrations.Migration):
    dependencies = [("forms_engine", "0023_alter_formfield_field_type_and_more")]
    operations = [migrations.RunPython(convert_to_biannual, migrations.RunPython.noop)]
