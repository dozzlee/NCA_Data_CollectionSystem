from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("compliance", "0010_communicationrecord_unique_communication_per_submission_event")]

    operations = [
        migrations.AlterModelOptions(
            name="communicationrecord",
            options={"ordering": ["-created_at", "-id"]},
        ),
    ]
