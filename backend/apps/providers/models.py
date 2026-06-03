import uuid
from django.db import models


class ProviderProfile(models.Model):
    CATEGORY_CHOICES = [
        ("MNO", "MNO"),
        ("ISP", "ISP"),
        ("PAY_TV", "Pay TV"),
        ("TOWER_OPERATOR", "Tower Operator"),
        ("TOWER_MAIN", "Tower Main"),
        ("DOMESTIC_FIBRE", "Domestic Fibre"),
        ("SUBMARINE_FIBRE", "Submarine Fibre"),
    ]
    STATUS_CHOICES = [
        ("ACTIVE", "Active"),
        ("INACTIVE", "Inactive"),
        ("SUSPENDED", "Suspended"),
        ("ARCHIVED", "Archived"),
    ]

    provider_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    organization = models.OneToOneField(
        "users.Organization", on_delete=models.PROTECT, null=True, blank=True,
        related_name="provider_profile"
    )
    registered_name = models.CharField(max_length=255)
    trade_name = models.CharField(max_length=255, blank=True)
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES)
    licence_type = models.CharField(max_length=100)
    licence_number = models.CharField(max_length=100)
    licence_issue_date = models.DateField(null=True, blank=True)
    licence_expiry_date = models.DateField(null=True, blank=True)
    physical_address = models.TextField(blank=True)
    digital_address = models.CharField(max_length=20, blank=True)
    postal_address = models.TextField(blank=True)
    website = models.URLField(blank=True)
    primary_email = models.EmailField()
    primary_phone = models.CharField(max_length=30)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="ACTIVE")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.registered_name

    class Meta:
        ordering = ["registered_name"]


class ProviderContact(models.Model):
    provider = models.ForeignKey(ProviderProfile, on_delete=models.CASCADE, related_name="contacts")
    name = models.CharField(max_length=255)
    designation = models.CharField(max_length=255)
    email = models.EmailField()
    phone = models.CharField(max_length=30)
    notification_role = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    notify_on_period_open = models.BooleanField(default=True)
    notify_on_reminder = models.BooleanField(default=True)
    notify_on_review = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.provider.registered_name})"

    class Meta:
        ordering = ["name"]
