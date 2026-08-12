from django.db import migrations, models


FORM_CODES = [
    ("MNO-MONTHLY", "MNO Monthly Return"),
    ("DC-TB02", "Pay TV Broadcasting Annual"),
    ("DC-ISP06", "Internet Service Provider Annual"),
    ("DC-ITC04", "Infrastructure Tower Operator Annual"),
    ("TOWER-MAIN-ANNUAL", "Infrastructure Tower Main Annual"),
    ("DC-DBS05", "Domestic/Inland Fibre Annual"),
    ("DC-SUB03", "International Submarine Fibre Annual"),
]


class Migration(migrations.Migration):
    dependencies = [("forms_engine", "0005_formrequirement_formgapassessment")]

    operations = [
        migrations.AlterField(
            model_name="formfamily",
            name="code",
            field=models.CharField(choices=FORM_CODES, max_length=20, unique=True),
        ),
        migrations.AlterField(
            model_name="formtemplate",
            name="form_code",
            field=models.CharField(choices=FORM_CODES, max_length=20),
        ),
    ]
