from collections import Counter

from apps.submissions.models import Submission
from apps.uploads.excel_imports import (
    _convert,
    _materialize_repeatable_target,
    _rank,
    _shortlist,
    _targets,
    extract_candidates,
    normalize,
)


submission = Submission.objects.select_related(
    "expected__form_template", "expected__period", "expected__provider"
).get(pk=130)
candidates, warnings, fingerprint = extract_candidates(
    r"C:\Users\dozzl\Downloads\Vodafone_September_2026.xlsx",
    period=submission.expected.period,
)
targets = _targets(submission.expected.form_template)
used_targets = set()
counts = Counter()
matched = []
examples = []

for candidate in candidates:
    ranked = []
    for target in _shortlist(candidate, targets):
        score, evidence = _rank(candidate, target)
        ranked.append((score, target, evidence))
    ranked.sort(key=lambda item: (-item[0], item[1]["target_key"]))
    ranked = [
        (score, _materialize_repeatable_target(target, candidate), evidence)
        for score, target, evidence in ranked
    ]
    best_score, best, evidence = ranked[0] if ranked else (0.0, None, {})
    second_score = ranked[1][0] if len(ranked) > 1 else 0.0
    status = "UNMATCHED"
    if candidate["formula_without_cache"]:
        status = "INVALID"
    elif best and best_score >= 0.82 and best_score - second_score >= 0.05:
        status = "MATCHED"
    elif best and best_score >= 0.60:
        status = "AMBIGUOUS"
    if best and best["target_key"] in used_targets and status == "MATCHED":
        status = "DUPLICATE"
    converted, error = _convert(candidate["raw_value"], best) if best else ("", None)
    if error:
        status = "INVALID"
    if status == "MATCHED":
        used_targets.add(best["target_key"])
        matched.append((candidate, best, converted))
    elif len(examples) < 20:
        examples.append((status, candidate["source_locator"], candidate["indicator_name"], round(best_score, 3)))
    counts[status] += 1

current = {
    ("FIELD", value.field_id, None, None): value.value
    if value.field_id
    else None
    for value in submission.values.all()
}
changes = 0
for candidate, target, converted in matched:
    if target["field"]:
        old = submission.values.filter(field=target["field"]).values_list("value", flat=True).first() or ""
    else:
        old = submission.values.filter(
            grid=target["grid"], grid_row_id=target["grid_row_id"], grid_column=target["grid_column"]
        ).values_list("value", flat=True).first() or ""
    if old != converted:
        changes += 1

print({
    "submission": submission.submission_reference,
    "status": submission.regulatory_status,
    "candidate_count": len(candidates),
    "target_count": len(targets),
    "match_counts": dict(counts),
    "matched_changes": changes,
    "warnings": warnings,
    "fingerprint": fingerprint,
    "unresolved_examples": examples,
})
