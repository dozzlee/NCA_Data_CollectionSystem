from django.db import migrations, models


CATALOG = [
    ("DC-ISP06", "Internet / Public Data Service Providers", "TELECOM", "ISP", "ANNUAL", "Internet_Service_Provider_Annual.pdf", "CONFIRMED"),
    ("DC-TB02", "Pay Television Broadcasting", "BROADCASTING", "PAY_TV", "ANNUAL", "PAY_TV_BROADCASTING_TB02.pdf", "CONFIRMED"),
    ("DC-DBS05", "National Inland Fibre Optic Cable System Providers", "TELECOM", "DOMESTIC_FIBRE", "ANNUAL", "Domestic_Submarine_Fibre_Annual.pdf", "CONFIRMED"),
    ("DC-SUB03", "International Submarine Fibre Optic Cable Providers", "TELECOM", "SUBMARINE_FIBRE", "ANNUAL", "International_Submarine_Fibre_Annual.docx", "CONFIRMED"),
    ("DC-ITC04", "Infrastructure Tower Companies", "TELECOM", "TOWER_OPERATOR", "ANNUAL", "Infrastructure_Tower_Operator_Annual.pdf", "CONFIRMED"),
    ("TOWER-MAIN-ANNUAL", "Infrastructure Tower Main Annual", "TELECOM", "TOWER_MAIN", "ANNUAL", "Infrastructure_Tower_Main_Annual.xlsx", "PROVISIONAL"),
    ("MNO-MONTHLY", "Mobile Network Operators Monthly Data Reporting", "TELECOM", "MNO", "MONTHLY", "NCA_Monthly_Report.xlsx", "CONFIRMED"),
]


def seed_catalog(apps, schema_editor):
    Catalog = apps.get_model("forms_engine", "FormCodeCatalog")
    for order, row in enumerate(CATALOG, start=1):
        code, name, sector, category, frequency, filename, status = row
        Catalog.objects.update_or_create(code=code, defaults={
            "name": name, "sector": sector, "provider_category": category,
            "frequency": frequency, "source_filename": filename,
            "code_status": status, "is_active": True, "sort_order": order,
        })


class Migration(migrations.Migration):
    dependencies = [("forms_engine", "0017_one_active_version_per_family")]

    operations = [
        migrations.CreateModel(
            name="FormCodeCatalog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=50, unique=True)),
                ("name", models.CharField(max_length=255)),
                ("sector", models.CharField(choices=[("TELECOM", "Telecom"), ("BROADCASTING", "Broadcasting")], max_length=20)),
                ("provider_category", models.CharField(max_length=30)),
                ("frequency", models.CharField(choices=[("MONTHLY", "Monthly"), ("QUARTERLY", "Quarterly"), ("SEMI_ANNUAL", "Semi-Annual"), ("ANNUAL", "Annual")], max_length=15)),
                ("source_filename", models.CharField(max_length=255)),
                ("code_status", models.CharField(choices=[("CONFIRMED", "Confirmed"), ("PROVISIONAL", "Provisional")], default="CONFIRMED", max_length=15)),
                ("is_active", models.BooleanField(default=True)),
                ("sort_order", models.PositiveIntegerField(default=0)),
            ],
            options={"ordering": ["sort_order", "code"]},
        ),
        migrations.RunPython(seed_catalog, migrations.RunPython.noop),
    ]
