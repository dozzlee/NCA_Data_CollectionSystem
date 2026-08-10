from django.db import migrations


def migrate_provider_admins(apps, schema_editor):
    User = apps.get_model("users", "User")
    User.objects.filter(role="PROVIDER_ADMIN").update(role="PROVIDER_APPROVER")


class Migration(migrations.Migration):
    dependencies = [("users", "0001_initial")]
    operations = [migrations.RunPython(migrate_provider_admins, migrations.RunPython.noop)]
