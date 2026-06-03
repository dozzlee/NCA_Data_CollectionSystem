from django.db import models

FIELD_TYPES = [
    ("text", "Text"),
    ("number", "Number"),
    ("currency", "Currency (GH₵)"),
    ("percentage", "Percentage"),
    ("date", "Date"),
    ("boolean", "Boolean (Yes/No)"),
    ("select", "Select"),
    ("multiselect", "Multi-select"),
    ("textarea", "Textarea"),
    ("coordinate", "Coordinate"),
    ("formula", "Formula (Calculated)"),
    ("declaration", "Declaration / Checkbox"),
]

FORM_CODES = [
    ("MNO-MONTHLY", "MNO Monthly Return"),
    ("DC-TB02", "Pay TV Broadcasting Annual"),
    ("DC-ISP06", "Internet Service Provider Annual"),
    ("DC-ITC04", "Infrastructure Tower Operator Annual"),
    ("TOWER-MAIN-ANNUAL", "Infrastructure Tower Main Annual"),
    ("DC-DBS05", "Domestic/Inland Fibre Semi-Annual"),
    ("DC-SUB03", "International Submarine Fibre Annual"),
]

# KMZ is only allowed for these two form codes
KMZ_ELIGIBLE_FORMS = {"DC-DBS05", "DC-SUB03"}


class FormTemplate(models.Model):
    FREQUENCY_CHOICES = [
        ("MONTHLY", "Monthly"),
        ("SEMI_ANNUAL", "Semi-Annual"),
        ("ANNUAL", "Annual"),
    ]
    STATUS_CHOICES = [
        ("DRAFT", "Draft"),
        ("ACTIVE", "Active"),
        ("ARCHIVED", "Archived"),
    ]

    form_code = models.CharField(max_length=20, choices=FORM_CODES, unique=True)
    name = models.CharField(max_length=255)
    provider_category = models.CharField(max_length=30)
    frequency = models.CharField(max_length=15, choices=FREQUENCY_CHOICES)
    version = models.CharField(max_length=20, default="1.0")
    effective_from = models.DateField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="DRAFT")
    kmz_required = models.BooleanField(default=False)
    excel_backup_enabled = models.BooleanField(default=True)
    instructions = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        # Enforce KMZ restriction — only fibre forms
        if self.form_code not in KMZ_ELIGIBLE_FORMS:
            self.kmz_required = False
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.form_code} v{self.version}"

    class Meta:
        ordering = ["form_code"]


class FormSection(models.Model):
    form_template = models.ForeignKey(FormTemplate, on_delete=models.CASCADE, related_name="sections")
    section_code = models.CharField(max_length=50)
    title = models.CharField(max_length=255)
    instructions = models.TextField(blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    kmz_upload_required = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.form_template.form_code} / {self.title}"

    class Meta:
        ordering = ["sort_order"]
        unique_together = [["form_template", "section_code"]]


class FormField(models.Model):
    section = models.ForeignKey(FormSection, on_delete=models.CASCADE, related_name="fields")
    field_code = models.CharField(max_length=100)
    label = models.CharField(max_length=255)
    field_type = models.CharField(max_length=20, choices=FIELD_TYPES)
    unit = models.CharField(max_length=50, blank=True)
    is_required = models.BooleanField(default=True)
    help_text = models.TextField(blank=True)
    formula = models.TextField(blank=True)
    conditional_on_field = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="conditional_children"
    )
    conditional_on_value = models.CharField(max_length=100, blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    export_name = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return f"{self.section.section_code} / {self.field_code}"

    class Meta:
        ordering = ["sort_order"]
        unique_together = [["section", "field_code"]]


class SelectOption(models.Model):
    field = models.ForeignKey(FormField, on_delete=models.CASCADE, related_name="options")
    value = models.CharField(max_length=100)
    label = models.CharField(max_length=255)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order"]


class FormGrid(models.Model):
    ROW_MODE_CHOICES = [
        ("FIXED", "Fixed rows (e.g. Ghana regions)"),
        ("REPEATABLE", "Repeatable rows (provider adds rows)"),
    ]

    section = models.ForeignKey(FormSection, on_delete=models.CASCADE, related_name="grids")
    grid_code = models.CharField(max_length=100)
    title = models.CharField(max_length=255)
    row_mode = models.CharField(max_length=15, choices=ROW_MODE_CHOICES)
    sort_order = models.PositiveIntegerField(default=0)
    instructions = models.TextField(blank=True)

    def __str__(self):
        return f"{self.section.section_code} / {self.grid_code}"

    class Meta:
        ordering = ["sort_order"]
        unique_together = [["section", "grid_code"]]


class GridColumn(models.Model):
    grid = models.ForeignKey(FormGrid, on_delete=models.CASCADE, related_name="columns")
    column_code = models.CharField(max_length=100)
    label = models.CharField(max_length=255)
    field_type = models.CharField(max_length=20, choices=FIELD_TYPES)
    unit = models.CharField(max_length=50, blank=True)
    is_required = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order"]
        unique_together = [["grid", "column_code"]]


class GridRow(models.Model):
    """Pre-populated row labels for FIXED grids (e.g. Ghana regions)."""
    grid = models.ForeignKey(FormGrid, on_delete=models.CASCADE, related_name="fixed_rows")
    row_label = models.CharField(max_length=255)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order"]


class KMZUploadRequirement(models.Model):
    """Only created for DC-DBS05 and DC-SUB03."""
    CATEGORY_CHOICES = [
        ("ROUTE", "Route"),
        ("TOPOLOGY", "Topology"),
        ("COVERAGE", "Coverage"),
        ("NETWORK_MAP", "Network Map"),
    ]

    form_template = models.ForeignKey(FormTemplate, on_delete=models.CASCADE, related_name="kmz_requirements")
    section = models.ForeignKey(FormSection, null=True, blank=True, on_delete=models.SET_NULL)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    description = models.TextField(blank=True)
    is_required = models.BooleanField(default=True)
    max_file_size_mb = models.PositiveIntegerField(default=50)

    def __str__(self):
        return f"{self.form_template.form_code} / KMZ / {self.category}"
