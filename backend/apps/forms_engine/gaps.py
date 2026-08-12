from django.utils import timezone

from .models import FormGapAssessment


def _check_requirement(form, requirement):
    criteria = requirement.criteria or {}
    kind = requirement.requirement_type
    failures = []

    section_code = criteria.get("section_code")
    section = form.sections.filter(section_code=section_code).first() if section_code else None
    if section_code and not section:
        failures.append(f"section {section_code} is missing")

    if kind == "SECTION":
        expected = criteria.get("section_codes") or ([section_code] if section_code else [])
        actual = set(form.sections.values_list("section_code", flat=True))
        failures.extend(f"section {code} is missing" for code in expected if code not in actual)
    elif kind in {"FIELD", "OPTION", "UNIT", "DECLARATION", "CONDITIONAL", "FORMULA"}:
        field = section.fields.filter(field_code=criteria.get("field_code")).first() if section else None
        if not field:
            failures.append(f"field {criteria.get('field_code')} is missing")
        else:
            for attr in ("field_type", "unit", "is_required", "conditional_on_value"):
                if attr in criteria and getattr(field, attr) != criteria[attr]:
                    failures.append(f"{attr} expected {criteria[attr]!r}, found {getattr(field, attr)!r}")
            if criteria.get("conditional_on_field"):
                actual_parent = field.conditional_on_field.field_code if field.conditional_on_field_id else None
                if actual_parent != criteria["conditional_on_field"]:
                    failures.append(f"conditional parent expected {criteria['conditional_on_field']!r}, found {actual_parent!r}")
            if "options" in criteria:
                actual = list(field.options.order_by("sort_order").values_list("label", flat=True))
                if actual != criteria["options"]:
                    failures.append("configured options do not match the PRD list")
            if kind == "FORMULA" and not (field.formula or field.validation_rules.filter(rule_type="FORMULA", is_active=True).exists()):
                failures.append("formula rule is missing")
    elif kind in {"GRID", "GRID_COLUMN", "FIXED_ROWS"}:
        grid = section.grids.filter(grid_code=criteria.get("grid_code")).first() if section else None
        if not grid:
            failures.append(f"grid {criteria.get('grid_code')} is missing")
        else:
            if criteria.get("row_mode") and grid.row_mode != criteria["row_mode"]:
                failures.append(f"row mode expected {criteria['row_mode']}, found {grid.row_mode}")
            if "min_rows" in criteria and grid.min_rows != criteria["min_rows"]:
                failures.append(f"minimum rows expected {criteria['min_rows']}, found {grid.min_rows}")
            if "fixed_rows" in criteria:
                actual_rows = list(grid.fixed_rows.order_by("sort_order").values_list("row_label", flat=True))
                if actual_rows != criteria["fixed_rows"]:
                    failures.append("fixed rows do not exactly match the PRD list")
            for expected in criteria.get("columns", []):
                column = grid.columns.filter(column_code=expected["column_code"]).first()
                if not column:
                    failures.append(f"grid column {expected['column_code']} is missing")
                    continue
                for attr in ("field_type", "unit", "is_required"):
                    if attr in expected and getattr(column, attr) != expected[attr]:
                        failures.append(f"column {expected['column_code']} {attr} does not match")
    elif kind == "VALIDATION":
        rules = form.validation_rules.filter(rule_type=criteria.get("rule_type"), is_active=True)
        if criteria.get("field_code"):
            rules = rules.filter(field__field_code=criteria["field_code"])
        if criteria.get("grid_code"):
            rules = rules.filter(grid__grid_code=criteria["grid_code"])
        if not rules.exists():
            failures.append(f"validation {criteria.get('rule_type')} is missing")
    elif kind == "KMZ":
        requirement_qs = form.kmz_requirements.filter(category=criteria.get("category", "TOPOLOGY"))
        if criteria.get("section_code"):
            requirement_qs = requirement_qs.filter(section__section_code=criteria["section_code"])
        if criteria.get("required", True) != requirement_qs.filter(is_required=True).exists():
            failures.append("KMZ requirement does not match Section 11")
    elif kind == "SOURCE_DECISION":
        provisional_is_accepted = criteria.get("allow_provisional", False) and form.family.code_status == "PROVISIONAL"
        if not criteria.get("confirmed", False) and not provisional_is_accepted:
            failures.append(criteria.get("message", "source-owner decision is pending"))
    else:
        expected_sections = set(criteria.get("section_codes", []))
        expected_grids = set(criteria.get("grid_codes", []))
        expected_validations = set(criteria.get("validation_types", []))
        actual_sections = set(form.sections.values_list("section_code", flat=True))
        actual_grids = set(form.sections.values_list("grids__grid_code", flat=True))
        actual_validations = set(form.validation_rules.filter(is_active=True).values_list("rule_type", flat=True))
        failures.extend(f"section {x} is missing" for x in expected_sections - actual_sections)
        failures.extend(f"grid {x} is missing" for x in expected_grids - actual_grids)
        failures.extend(f"validation {x} is missing" for x in expected_validations - actual_validations)

    return failures


def recalculate_form_gaps(form_template, actor=None):
    assessments = []
    for requirement in form_template.family.requirements.all():
        failures = _check_requirement(form_template, requirement)
        status = "MATCHED" if not failures else "MISSING"
        evidence = "Exact Section 11 requirement matched." if not failures else "; ".join(failures)
        assessment, _ = FormGapAssessment.objects.update_or_create(
            form_template=form_template,
            requirement=requirement,
            defaults={"status": status, "evidence": evidence, "assessed_by": actor, "assessed_at": timezone.now()},
        )
        assessments.append(assessment)
    return assessments
