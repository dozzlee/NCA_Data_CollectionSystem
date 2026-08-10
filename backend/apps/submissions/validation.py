import operator
from datetime import date
from decimal import Decimal, InvalidOperation
from django.utils import timezone
from apps.forms_engine.models import ValidationRule
from .models import SubmissionValue, ValidationRun, ValidationResult


OPS = {"+": operator.add, "-": operator.sub, "*": operator.mul, "/": operator.truediv,
       "==": operator.eq, "!=": operator.ne, ">": operator.gt, ">=": operator.ge, "<": operator.lt, "<=": operator.le}


def _decimal(value):
    try: return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError): raise ValueError("Expected a number.")


def _expression(node, values):
    if isinstance(node, (int, float, str)): return _decimal(node)
    if not isinstance(node, dict): raise ValueError("Invalid expression node.")
    if "field" in node: return _decimal(values.get(int(node["field"]), ""))
    op = node.get("op")
    if op not in OPS: raise ValueError("Unsupported expression operator.")
    args = [_expression(arg, values) for arg in node.get("args", [])]
    if len(args) != 2: raise ValueError("Expressions require two operands.")
    if op == "/" and args[1] == 0: raise ValueError("Division by zero.")
    return OPS[op](args[0], args[1])


def _type_valid(field_type, value):
    if value in (None, ""): return True
    if field_type in {"number", "currency", "percentage", "formula"}: _decimal(value)
    elif field_type == "date": date.fromisoformat(str(value))
    elif field_type == "boolean" and str(value).lower() not in {"true", "false", "yes", "no", "1", "0"}: raise ValueError("Expected a boolean.")
    elif field_type == "coordinate":
        lat, lon = [Decimal(x.strip()) for x in str(value).split(",", 1)]
        if not (-90 <= lat <= 90 and -180 <= lon <= 180): raise ValueError("Coordinate is outside valid latitude/longitude bounds.")
    return True


def run_validation(submission, scope="FULL"):
    values_qs = submission.values.select_related("field", "grid_column", "grid")
    values = {v.field_id: v.value for v in values_qs if v.field_id}
    grid_values = list(values_qs.filter(grid__isnull=False))
    rule_query = ValidationRule.objects.filter(form_template=submission.expected.form_template, is_active=True)
    if scope != "FULL":
        from django.db.models import Q
        rule_query = rule_query.filter(Q(field__section__section_code=scope) | Q(grid__section__section_code=scope))
    rules = list(rule_query.select_related("field", "grid"))
    run = ValidationRun.objects.create(submission=submission, scope=scope, status="PASS",
        ruleset_snapshot=[{"id": r.id, "version": r.version, "type": r.rule_type, "parameters": r.parameters} for r in rules])
    failures = []
    for rule in rules:
        target_id = str(rule.field_id or rule.grid_id or "")
        try:
            value = values.get(rule.field_id, "") if rule.field_id else ""
            params = rule.parameters or {}
            if rule.rule_type == "TYPE" and rule.field: _type_valid(params.get("field_type", rule.field.field_type), value)
            elif rule.rule_type == "RANGE" and value not in (None, ""):
                number = _decimal(value)
                if params.get("min") is not None and number < _decimal(params["min"]): raise ValueError("Value is below the minimum.")
                if params.get("max") is not None and number > _decimal(params["max"]): raise ValueError("Value is above the maximum.")
            elif rule.rule_type == "OPTION" and value not in (None, "") and value not in params.get("allowed", []): raise ValueError("Value is not an approved option.")
            elif rule.rule_type == "DATE" and value:
                parsed = date.fromisoformat(value)
                if params.get("min") and parsed < date.fromisoformat(params["min"]): raise ValueError("Date is too early.")
                if params.get("max") and parsed > date.fromisoformat(params["max"]): raise ValueError("Date is too late.")
            elif rule.rule_type == "COORDINATE" and value not in (None, ""): _type_valid("coordinate", value)
            elif rule.rule_type == "CONDITIONAL":
                if str(values.get(int(params["when_field"]), "")) == str(params.get("equals")) and not str(value).strip(): raise ValueError("Value is required by a conditional rule.")
            elif rule.rule_type == "FORMULA" and rule.field:
                calculated = _expression(params.get("expression"), values)
                obj, _ = SubmissionValue.objects.update_or_create(submission=submission, field=rule.field,
                    defaults={"value": str(calculated), "value_status": "SYSTEM_CALCULATED"})
                values[rule.field_id] = obj.value
            elif rule.rule_type == "COMPARISON":
                left = _decimal(values.get(int(params.get("left_field", rule.field_id)), "")); right = _decimal(values.get(int(params["right_field"]), ""))
                op = params.get("operator")
                if op not in OPS or not OPS[op](left, right): raise ValueError("Cross-field comparison failed.")
            elif rule.rule_type == "GRID_TOTAL":
                column_id = int(params["column_id"]); total = sum((_decimal(v.value) for v in grid_values if v.grid_column_id == column_id and v.value), Decimal(0))
                expected = _decimal(values.get(int(params["equals_field"]), ""))
                if total != expected: raise ValueError(f"Grid total {total} does not match {expected}.")
        except (ValueError, KeyError, TypeError, InvalidOperation) as exc:
            result = ValidationResult.objects.create(run=run, rule=rule, severity=rule.severity,
                target_type="FIELD" if rule.field_id else "GRID", target_id=target_id,
                code=f"VALIDATION_{rule.rule_type}", message=rule.message or str(exc), details={"reason": str(exc)})
            failures.append(result)
    run.status = "FAIL" if any(x.severity == "BLOCK" for x in failures) else "WARN" if failures else "PASS"
    run.completed_at = timezone.now(); run.save(update_fields=["status", "completed_at"])
    return run
