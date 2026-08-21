import re

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
    ("attachment", "Document attachment"),
]

FORM_CODES = [
    ("MNO-MONTHLY", "MNO Monthly Return"),
    ("DC-TB02", "Pay TV Broadcasting Annual"),
    ("DC-ISP06", "Internet Service Provider Annual"),
    ("DC-ITC04", "Infrastructure Tower Operator Annual"),
    ("TOWER-MAIN-ANNUAL", "Infrastructure Tower Main Annual"),
    ("DC-DBS05", "Domestic/Inland Fibre Annual"),
    ("DC-SUB03", "International Submarine Fibre Annual"),
]

# Section 11 only requires KMZ route/topology evidence for the domestic fibre form.
KMZ_ELIGIBLE_FORMS = {"DC-DBS05"}


class FormCodeCatalog(models.Model):
    """Governed form identity; exists independently of created template versions."""

    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=255)
    sector = models.CharField(max_length=20, choices=[("TELECOM", "Telecom"), ("BROADCASTING", "Broadcasting")])
    provider_category = models.CharField(max_length=30)
    frequency = models.CharField(
        max_length=15,
        choices=[("MONTHLY", "Monthly"), ("QUARTERLY", "Quarterly"), ("SEMI_ANNUAL", "Semi-Annual"), ("ANNUAL", "Annual")],
    )
    source_filename = models.CharField(max_length=255)
    code_status = models.CharField(
        max_length=15, choices=[("CONFIRMED", "Confirmed"), ("PROVISIONAL", "Provisional")],
        default="CONFIRMED",
    )
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "code"]

    def __str__(self):
        return self.code

    @property
    def next_version(self):
        versions = FormTemplate.objects.filter(form_code=self.code).values_list("version", flat=True)
        majors = []
        for version in versions:
            match = re.fullmatch(r"(\d+)(?:\.\d+)?", version.strip())
            if match:
                majors.append(int(match.group(1)))
        return f"{max(majors, default=0) + 1}.0"


class FormFamily(models.Model):
    """Stable identity shared by immutable form versions."""
    FREQUENCY_DECISIONS = [
        ("PENDING_DECISION", "Pending source-owner decision"),
        ("APPROVED", "Approved"),
    ]

    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=255)
    canonical_frequency = models.CharField(
        max_length=15, choices=[("MONTHLY", "Monthly"), ("QUARTERLY", "Quarterly"), ("SEMI_ANNUAL", "Semi-Annual"), ("ANNUAL", "Annual")],
        blank=True,
    )
    frequency_decision_status = models.CharField(max_length=25, choices=FREQUENCY_DECISIONS, default="APPROVED")
    frequency_decision_reference = models.CharField(max_length=255, blank=True)
    source_owner = models.CharField(max_length=255, blank=True)
    code_status = models.CharField(
        max_length=15,
        choices=[("CONFIRMED", "Confirmed"), ("PROVISIONAL", "Provisional")],
        default="CONFIRMED",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.code


class FormTemplate(models.Model):
    SECTOR_CHOICES = [
        ("TELECOM", "Telecom"),
        ("BROADCASTING", "Broadcasting"),
    ]
    FREQUENCY_CHOICES = [
        ("MONTHLY", "Monthly"),
        ("QUARTERLY", "Quarterly"),
        ("SEMI_ANNUAL", "Semi-Annual"),
        ("ANNUAL", "Annual"),
    ]
    STATUS_CHOICES = [
        ("DRAFT", "Draft"),
        ("ACTIVE", "Active"),
        ("ARCHIVED", "Archived"),
    ]

    family = models.ForeignKey(FormFamily, null=True, blank=True, on_delete=models.PROTECT, related_name="versions")
    # Compatibility mirror. FormFamily.code is the source of truth for new versions.
    form_code = models.CharField(max_length=50)
    name = models.CharField(max_length=255)
    sector = models.CharField(max_length=20, choices=SECTOR_CHOICES, default="TELECOM")
    provider_category = models.CharField(max_length=30)
    frequency = models.CharField(max_length=15, choices=FREQUENCY_CHOICES)
    version = models.CharField(max_length=20, default="1.0")
    effective_from = models.DateField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="DRAFT")
    kmz_required = models.BooleanField(default=False)
    excel_backup_enabled = models.BooleanField(default=True)
    instructions = models.TextField(blank=True)
    source_reference = models.CharField(max_length=500, blank=True)
    source_sha256 = models.CharField(max_length=64, blank=True)
    mapping_complete = models.BooleanField(default=False)
    mapping_basis = models.CharField(
        max_length=30,
        choices=[
            ("LEGACY", "Legacy"),
            ("PRD_SECTION_11", "PRD Section 11"),
            ("SOURCE_FORM", "Original source form"),
            ("CUSTOM", "Custom NCA form"),
        ],
        default="LEGACY",
    )
    approval_status = models.CharField(
        max_length=20,
        choices=[("DRAFT", "Draft"), ("PENDING_APPROVAL", "Pending approval"), ("APPROVED", "Approved")],
        default="DRAFT",
    )
    prepared_by = models.ForeignKey("users.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="form_versions_prepared")
    approved_by = models.ForeignKey("users.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="form_versions_approved")
    approved_at = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        self.form_code = (self.form_code or "").strip().upper()
        # Enforce KMZ restriction — only fibre forms
        if self.form_code not in KMZ_ELIGIBLE_FORMS:
            self.kmz_required = False
        if not self.family_id and self.form_code:
            decision = "PENDING_DECISION" if self.form_code == "DC-DBS05" else "APPROVED"
            canonical = "" if decision == "PENDING_DECISION" else self.frequency
            self.family, _ = FormFamily.objects.get_or_create(
                code=self.form_code,
                defaults={"name": self.name, "canonical_frequency": canonical, "frequency_decision_status": decision},
            )
        if self.family_id:
            self.form_code = self.family.code
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.form_code} v{self.version}"

    class Meta:
        ordering = ["form_code"]
        constraints = [
            models.UniqueConstraint(fields=["family", "version"], name="unique_form_family_version"),
            models.UniqueConstraint(
                fields=["family"], condition=models.Q(status="ACTIVE"),
                name="one_active_version_per_form_family",
            ),
        ]


class ValidationRule(models.Model):
    RULE_TYPES = [
        ("TYPE", "Data type"), ("RANGE", "Range"), ("OPTION", "Allowed option"),
        ("DATE", "Date"), ("COORDINATE", "Coordinate"), ("CONDITIONAL", "Conditional"),
        ("FORMULA", "Formula"), ("COMPARISON", "Cross-field comparison"), ("GRID_TOTAL", "Grid total"),
    ]
    form_template = models.ForeignKey(FormTemplate, on_delete=models.CASCADE, related_name="validation_rules")
    field = models.ForeignKey("FormField", null=True, blank=True, on_delete=models.CASCADE, related_name="validation_rules")
    grid = models.ForeignKey("FormGrid", null=True, blank=True, on_delete=models.CASCADE, related_name="validation_rules")
    rule_type = models.CharField(max_length=20, choices=RULE_TYPES)
    severity = models.CharField(max_length=10, choices=[("BLOCK", "Blocking"), ("WARN", "Warning")], default="BLOCK")
    parameters = models.JSONField(default=dict, blank=True)
    message = models.CharField(max_length=500)
    version = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]

    def clean(self):
        from .rules import validate_rule_definition
        validate_rule_definition(self.rule_type, self.parameters, self.form_template, self.field, self.grid)


class FormRequirement(models.Model):
    REQUIREMENT_TYPES = [
        ("SECTION", "Section"), ("FIELD", "Field"), ("GRID", "Grid"),
        ("GRID_COLUMN", "Grid column"), ("FIXED_ROWS", "Fixed rows"),
        ("OPTION", "Option"), ("UNIT", "Unit"), ("VALIDATION", "Validation"),
        ("CONDITIONAL", "Conditional"), ("FORMULA", "Formula"),
        ("DECLARATION", "Declaration"), ("KMZ", "KMZ upload"),
        ("SOURCE_DECISION", "Source decision"), ("SPECIAL_HANDLING", "Special handling"),
    ]
    family = models.ForeignKey(FormFamily, on_delete=models.CASCADE, related_name="requirements")
    requirement_key = models.CharField(max_length=120)
    requirement_type = models.CharField(max_length=30, choices=REQUIREMENT_TYPES)
    label = models.CharField(max_length=255)
    description = models.TextField()
    severity = models.CharField(max_length=10, choices=[("BLOCKER", "Blocker"), ("HIGH", "High"), ("MEDIUM", "Medium"), ("LOW", "Low")], default="HIGH")
    criteria = models.JSONField(default=dict, blank=True)
    source_reference = models.CharField(max_length=500, default="Product Requirements Document - Development Ready.docx, Section 11")
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]
        constraints = [models.UniqueConstraint(fields=["family", "requirement_key"], name="unique_family_requirement_key")]


class FormGapAssessment(models.Model):
    STATUSES = [("MISSING", "Missing"), ("PARTIAL", "Partial"), ("MATCHED", "Matched"), ("NOT_APPLICABLE", "Not applicable")]
    form_template = models.ForeignKey(FormTemplate, on_delete=models.CASCADE, related_name="gap_assessments")
    requirement = models.ForeignKey(FormRequirement, on_delete=models.PROTECT, related_name="assessments")
    status = models.CharField(max_length=20, choices=STATUSES, default="MISSING")
    evidence = models.TextField(blank=True)
    owner = models.ForeignKey("users.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="form_gaps_owned")
    resolution_note = models.TextField(blank=True)
    assessed_by = models.ForeignKey("users.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="form_gaps_assessed")
    assessed_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey("users.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="form_gaps_resolved")
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["requirement__sort_order", "id"]
        constraints = [models.UniqueConstraint(fields=["form_template", "requirement"], name="unique_form_requirement_assessment")]


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


class FormHeading(models.Model):
    """Non-interactive workbook heading used to group fields inside a section."""

    section = models.ForeignKey(FormSection, on_delete=models.CASCADE, related_name="headings")
    heading_code = models.CharField(max_length=100)
    title = models.CharField(max_length=255)
    level = models.PositiveSmallIntegerField(default=1)
    sort_order = models.PositiveIntegerField(default=0)
    source_row = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.section.section_code} / {self.title}"

    class Meta:
        ordering = ["sort_order", "id"]
        constraints = [
            models.UniqueConstraint(fields=["section", "heading_code"], name="unique_section_heading_code"),
            models.CheckConstraint(condition=models.Q(level__gte=1, level__lte=3), name="form_heading_level_1_to_3"),
        ]


class FormField(models.Model):
    section = models.ForeignKey(FormSection, on_delete=models.CASCADE, related_name="fields")
    heading = models.ForeignKey(
        FormHeading, null=True, blank=True, on_delete=models.SET_NULL, related_name="fields",
    )
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
    source_sheet = models.CharField(max_length=255, blank=True)
    source_row = models.PositiveIntegerField(null=True, blank=True)

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
    min_rows = models.PositiveIntegerField(default=0)
    source_sheet = models.CharField(max_length=255, blank=True)
    source_row = models.PositiveIntegerField(null=True, blank=True)

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
    source_sheet = models.CharField(max_length=255, blank=True)
    source_row = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["sort_order"]
        unique_together = [["grid", "column_code"]]


class GridRow(models.Model):
    """Pre-populated row labels for FIXED grids (e.g. Ghana regions)."""
    grid = models.ForeignKey(FormGrid, null=True, blank=True, on_delete=models.CASCADE, related_name="fixed_rows")
    row_label = models.CharField(max_length=255)
    sort_order = models.PositiveIntegerField(default=0)
    source_sheet = models.CharField(max_length=255, blank=True)
    source_rows = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["sort_order"]


class KMZUploadRequirement(models.Model):
    """Section 11 KMZ evidence requirement for domestic fibre submissions."""
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


class FormWorkbookImport(models.Model):
    """Private workbook and editable, schema-only interpretation used to build a draft form."""
    SCAN_STATUSES = [("PENDING", "Pending"), ("CLEAN", "Clean"), ("INFECTED", "Infected"), ("ERROR", "Error")]
    PARSE_STATUSES = [("PENDING", "Pending"), ("READY", "Ready"), ("FAILED", "Failed"), ("CONFIRMED", "Confirmed")]

    form_code = models.CharField(max_length=50)
    name = models.CharField(max_length=255)
    version = models.CharField(max_length=20)
    sector = models.CharField(max_length=20, choices=FormTemplate.SECTOR_CHOICES)
    provider_category = models.CharField(max_length=30)
    frequency = models.CharField(max_length=15, choices=FormTemplate.FREQUENCY_CHOICES)
    file_name = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField()
    storage_path = models.CharField(max_length=500)
    sha256 = models.CharField(max_length=64)
    scan_status = models.CharField(max_length=20, choices=SCAN_STATUSES, default="PENDING")
    scan_engine = models.CharField(max_length=100, blank=True)
    scan_details = models.TextField(blank=True)
    parse_status = models.CharField(max_length=20, choices=PARSE_STATUSES, default="PENDING")
    parser_version = models.CharField(max_length=50, default="xlsx-worksheet-v7-data-entry-tables")
    detected_schema = models.JSONField(default=dict, blank=True)
    warnings = models.JSONField(default=list, blank=True)
    mapping_decisions = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey("users.User", on_delete=models.PROTECT, related_name="form_workbook_imports")
    resulting_template = models.OneToOneField(FormTemplate, null=True, blank=True, on_delete=models.PROTECT, related_name="workbook_import")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
