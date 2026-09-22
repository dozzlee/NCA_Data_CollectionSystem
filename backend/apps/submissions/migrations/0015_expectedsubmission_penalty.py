from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("submissions", "0014_reconcile_formal_submission_statuses"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="expectedsubmission",
            name="penalty_amount_ghs",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=14),
        ),
        migrations.AddField(
            model_name="expectedsubmission",
            name="penalty_reference",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="expectedsubmission",
            name="penalty_note",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="expectedsubmission",
            name="penalty_updated_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="expectedsubmission",
            name="penalty_updated_by",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name="penalties_updated", to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
