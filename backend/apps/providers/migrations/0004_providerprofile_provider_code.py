import re

from django.db import migrations, models


KNOWN_CODES = {
    "vodafone ghana limited": "VOD",
    "mtn ghana limited": "MTN",
    "airteltigo ghana": "ATG",
    "surfline communications": "SUR",
}


def populate_provider_codes(apps, schema_editor):
    ProviderProfile = apps.get_model("providers", "ProviderProfile")
    used = set()
    for provider in ProviderProfile.objects.order_by("id"):
        base = KNOWN_CODES.get(provider.registered_name.strip().lower())
        if not base:
            source = provider.trade_name or provider.registered_name
            words = re.findall(r"[A-Za-z0-9]+", source.upper())
            base = "".join(word[0] for word in words)[:8] or f"P{provider.id}"
            if len(base) < 2:
                base = f"{base}P"
        candidate = base[:12]
        suffix = 1
        while candidate in used:
            suffix += 1
            candidate = f"{base[:max(2, 12-len(str(suffix)))]}{suffix}"
        used.add(candidate)
        ProviderProfile.objects.filter(pk=provider.pk).update(provider_code=candidate)


class Migration(migrations.Migration):
    dependencies = [("providers", "0003_providerformassignment")]

    operations = [
        migrations.AddField(
            model_name="providerprofile",
            name="provider_code",
            field=models.CharField(max_length=12, null=True),
        ),
        migrations.RunPython(populate_provider_codes, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="providerprofile",
            name="provider_code",
            field=models.CharField(default="", max_length=12, unique=True),
        ),
    ]
