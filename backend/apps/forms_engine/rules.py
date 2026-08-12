from django.core.exceptions import ValidationError

ALLOWED_PARAMETERS = {
    "TYPE": {"field_type"},
    "RANGE": {"min", "max"},
    "OPTION": {"allowed"},
    "DATE": {"min", "max"},
    "COORDINATE": set(),
    "CONDITIONAL": {"when_field", "equals"},
    "FORMULA": {"expression"},
    "COMPARISON": {"left_field", "right_field", "operator"},
    "GRID_TOTAL": {"column_id", "equals_field"},
}


def _validate_expression(node, depth=0):
    if depth > 12:
        raise ValidationError({"parameters": "Formula nesting is too deep."})
    if isinstance(node, (int, float, str)):
        return
    if not isinstance(node, dict) or set(node) - {"field", "op", "args"}:
        raise ValidationError({"parameters": "Invalid allow-listed formula structure."})
    if "field" in node:
        return
    if node.get("op") not in {"+", "-", "*", "/", "==", "!=", ">", ">=", "<", "<="} or len(node.get("args", [])) != 2:
        raise ValidationError({"parameters": "Invalid formula operator or operands."})
    for child in node["args"]:
        _validate_expression(child, depth + 1)


def validate_rule_definition(rule_type, parameters, form, field=None, grid=None):
    parameters = parameters or {}
    allowed = ALLOWED_PARAMETERS.get(rule_type)
    if allowed is None:
        raise ValidationError({"rule_type": "Unsupported rule type."})
    unknown = set(parameters) - allowed
    if unknown:
        raise ValidationError({"parameters": f"Unsupported parameters: {', '.join(sorted(unknown))}"})
    if field and field.section.form_template_id != form.id:
        raise ValidationError({"field": "The field must belong to this form version."})
    if grid and grid.section.form_template_id != form.id:
        raise ValidationError({"grid": "The grid must belong to this form version."})
    if rule_type in {"TYPE", "RANGE", "OPTION", "DATE", "CONDITIONAL", "FORMULA"} and not field:
        raise ValidationError({"field": f"{rule_type} rules require a target field."})
    if rule_type in {"COORDINATE", "GRID_TOTAL"} and not (field or grid):
        raise ValidationError({"grid": f"{rule_type} rules require a field or grid target."})
    if rule_type == "FORMULA":
        _validate_expression(parameters.get("expression"))
    if rule_type == "CONDITIONAL" and not {"when_field", "equals"}.issubset(parameters):
        raise ValidationError({"parameters": "Conditional rules require when_field and equals."})
    if rule_type == "COMPARISON" and not {"left_field", "right_field", "operator"}.issubset(parameters):
        raise ValidationError({"parameters": "Comparison rules require left_field, right_field and operator."})
    if rule_type == "GRID_TOTAL" and not {"column_id", "equals_field"}.issubset(parameters):
        raise ValidationError({"parameters": "Grid total rules require column_id and equals_field."})
