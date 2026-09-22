from django.db import migrations, models
from django.utils.text import slugify


def migrate_divisions(apps, schema_editor):
    DataRequest = apps.get_model("data_requests", "DataRequest")
    NCADivision = apps.get_model("users", "NCADivision")
    User = apps.get_model("users", "User")
    names = sorted({name.strip() for name in DataRequest.objects.exclude(requesting_division="").values_list("requesting_division", flat=True) if name.strip()})
    divisions = {}
    for name in names:
        base = slugify(name)[:70] or "division"
        code = base
        suffix = 2
        while NCADivision.objects.filter(code=code).exclude(name=name).exists():
            code = f"{base[:70-len(str(suffix))-1]}-{suffix}"
            suffix += 1
        division, _ = NCADivision.objects.get_or_create(name=name, defaults={"code": code})
        divisions[name] = division
    for user in User.objects.filter(role="NCA_VIEWER", division__isnull=True):
        requester_divisions = list(DataRequest.objects.filter(requester_id=user.id).exclude(requesting_division="")
            .values_list("requesting_division", flat=True).distinct())
        if len(requester_divisions) == 1 and requester_divisions[0].strip() in divisions:
            user.division_id = divisions[requester_divisions[0].strip()].id
            user.save(update_fields=["division"])


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0004_ncadivision_user_division_user_grade"),
        ("data_requests", "0001_initial"),
    ]

    operations = [
        migrations.AddField(model_name="datarequest", name="requester_grade_snapshot", field=models.CharField(blank=True, max_length=120)),
        migrations.RunPython(migrate_divisions, migrations.RunPython.noop),
    ]
