from __future__ import annotations

import hashlib
import json
from datetime import timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.submissions.models import Submission
from .models import GeneratedReport, ReportPreparation, ReportPublicationMetadata, ReportTemplate


QUARTER_MONTHS = {1: (1, 2, 3), 2: (4, 5, 6), 3: (7, 8, 9), 4: (10, 11, 12)}
QUARTER_NAMES = {1: "FIRST QUARTER", 2: "SECOND QUARTER", 3: "THIRD QUARTER", 4: "FOURTH QUARTER"}
MONTH_NAMES = {1: "JANUARY", 2: "FEBRUARY", 3: "MARCH", 4: "APRIL", 5: "MAY", 6: "JUNE", 7: "JULY", 8: "AUGUST", 9: "SEPTEMBER", 10: "OCTOBER", 11: "NOVEMBER", 12: "DECEMBER"}


def quarter_shift(year, quarter, offset):
    index = year * 4 + quarter - 1 + offset
    return index // 4, index % 4 + 1


def period_context(report_type, year, quarter=None):
    if report_type == "CIR":
        return {"year": year, "historical_years": list(range(year - 4, year + 1)), "period_label": str(year)}
    if quarter not in QUARTER_MONTHS:
        raise ValueError("Quarter must be between 1 and 4.")
    previous_year, previous_quarter = quarter_shift(year, quarter, -1)
    prior_year, prior_quarter = year - 1, quarter
    rolling = [quarter_shift(year, quarter, offset) for offset in range(-4, 1)]
    months = QUARTER_MONTHS[quarter]
    return {
        "year": year, "quarter": quarter, "period_label": f"Q{quarter} {year}",
        "quarter_name": QUARTER_NAMES[quarter],
        "month_range": f"{MONTH_NAMES[months[0]]} - {MONTH_NAMES[months[-1]]}, {year}",
        "months": list(months), "previous_period": f"Q{previous_quarter} {previous_year}",
        "prior_year_period": f"Q{prior_quarter} {prior_year}",
        "rolling_five_quarters": [f"Q{q} {y}" for y, q in rolling],
    }


def active_template(report_type, year, quarter=None):
    """Return the report-family template used for a newly prepared report.

    Effective dates describe when a template version became the publication
    standard; they do not restrict which reporting period can be regenerated.
    The one ACTIVE definition for the family is therefore used for every
    selected quarter/year. Archived definitions remain attached to historical
    preparations and generated artifacts, but are never selected implicitly.
    """
    return ReportTemplate.objects.filter(
        report_type=report_type,
        status="ACTIVE",
    ).order_by("-version", "-id").first()


def approved_submissions():
    return Submission.objects.filter(
        regulatory_status="APPROVED", expected__workflow_status="APPROVED", submitted_at__isnull=False,
    ).select_related("expected__provider", "expected__period", "expected__form_template").prefetch_related("values__field")


def _periods_for_window(report_type, year, quarter, window):
    if report_type == "CIR":
        years = list(range(year - 4, year + 1)) if window == "HISTORICAL_5Y" else [year]
        return [(item, month) for item in years for month in range(1, 13)]
    target_year, target_quarter = year, quarter
    if window == "PREVIOUS": target_year, target_quarter = quarter_shift(year, quarter, -1)
    elif window == "PRIOR_YEAR": target_year -= 1
    months = QUARTER_MONTHS[target_quarter]
    return [(target_year, month) for month in months]


def _value_index(submissions):
    index, source_rows = {}, []
    seen = set()
    for submission in submissions.order_by("expected__provider_id", "expected__period__year", "expected__period__month", "-version", "-id"):
        expected, period = submission.expected, submission.expected.period
        identity = (expected.provider_id, expected.form_template_id, period.id)
        if identity in seen: continue
        seen.add(identity)
        value_fingerprint = []
        for value in submission.values.all():
            if not value.field_id or value.value_status not in {"PROVIDED", "SYSTEM_CALCULATED"}: continue
            try: numeric = Decimal(value.value)
            except (InvalidOperation, TypeError): continue
            index[(expected.provider_id, expected.form_template.form_code, value.field.field_code, period.year, period.month)] = numeric
            value_fingerprint.append((value.field.field_code, str(numeric), value.value_status))
        source_rows.append({
            "submission_id": submission.id,
            "reference": submission.submission_reference,
            "revision": submission.revision,
            "schema_sha256": submission.form_schema_sha256,
            "values_sha256": hashlib.sha256(json.dumps(sorted(value_fingerprint)).encode()).hexdigest(),
        })
    return index, source_rows


def _resolve_mapping(mapping, report_type, year, quarter, value_index, providers):
    periods = _periods_for_window(report_type, year, quarter, mapping.get("window", "CURRENT"))
    category = mapping.get("provider_category")
    relevant = [p for p in providers if not category or p[1] == category]
    if not relevant:
        return None, [f"{mapping['label']} - no active providers are configured for {category or 'the required scope'}"]
    missing, observations = [], []
    for provider_id, _category, provider_name in relevant:
        provider_values = []
        for period_year, month in periods:
            key = (provider_id, mapping["form_code"], mapping["field_code"], period_year, month)
            if key not in value_index:
                missing.append(f"{mapping['label']} - {provider_name} - {period_year}-{month:02d}")
            else:
                provider_values.append(value_index[key])
        if provider_values:
            mode = mapping.get("period_aggregation", "PERIOD_END")
            observations.append(sum(provider_values) if mode == "SUM" else sum(provider_values) / len(provider_values) if mode == "AVERAGE" else provider_values[-1])
    if missing: return None, missing
    mode = mapping.get("provider_aggregation", "SUM")
    value = sum(observations) if mode == "SUM" else sum(observations) / len(observations) if observations else None
    return value, []


def _format(value, mapping):
    places = int(mapping.get("decimal_places", 0))
    scale = Decimal(str(mapping.get("scale", 1)))
    adjusted = value * scale
    quantized = adjusted.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)
    return f"{quantized:,.{places}f}" + (mapping.get("suffix") or "")


@transaction.atomic
def prepare_report(*, report_type, year, quarter, user):
    template = active_template(report_type, year, quarter)
    if not template: raise ValueError("This report is not currently available.")
    context = period_context(report_type, year, quarter)
    submissions = approved_submissions()
    value_index, sources = _value_index(submissions)
    from apps.providers.models import ProviderProfile
    providers = list(ProviderProfile.objects.filter(status="ACTIVE").values_list("id", "category", "registered_name"))
    changes, missing, mapping_required = [], [], []
    for item in template.field_mappings:
        if not item.get("form_code") or not item.get("field_code"):
            mapping_required.append(item.get("label") or item.get("key") or "Unnamed mapping")
            continue
        value, absent = _resolve_mapping(item, report_type, year, quarter, value_index, providers)
        missing.extend(absent)
        if value is not None:
            changes.append({"key": item["key"], "section": item.get("section", ""), "location": item.get("location", ""),
                "field": item["label"], "template_value": item.get("template_value", ""), "new_value": _format(value, item),
                "raw_value": str(value), "source_period": item.get("window", "CURRENT"), "target_period": context["period_label"],
                "data_source": f"{item['form_code']}.{item['field_code']}", "mapping_status": "READY"})
    metadata = ReportPublicationMetadata.objects.filter(report_type=report_type, year=year, quarter=quarter if report_type != "CIR" else None).first()
    if report_type == "QUARTERLY_BULLETIN" and (not metadata or metadata.volume is None or metadata.issue is None):
        missing.append(f"Publication volume and issue - {context['period_label']}")
    period_changes = [{"key": key, "section": "Report metadata", "location": "All registered occurrences", "field": key.replace("_", " ").title(),
        "template_value": "", "new_value": value if not isinstance(value, list) else ", ".join(map(str, value)), "source_period": "TEMPLATE",
        "target_period": context["period_label"], "data_source": "Selected report period", "mapping_status": "READY"}
        for key, value in context.items() if key not in {"months", "historical_years"}]
    if metadata:
        period_changes.extend([{"key": "volume", "section": "Publication metadata", "location": "Cover", "field": "Volume", "template_value": "", "new_value": str(metadata.volume), "source_period": "CONFIGURATION", "target_period": context["period_label"], "data_source": "Report publication metadata", "mapping_status": "READY"},
            {"key": "issue", "section": "Publication metadata", "location": "Cover", "field": "Issue", "template_value": "", "new_value": str(metadata.issue), "source_period": "CONFIGURATION", "target_period": context["period_label"], "data_source": "Report publication metadata", "mapping_status": "READY"}])
    # Missing approved observations are the primary readiness condition. Mapping
    # gaps remain visible in the manifest and must also be cleared before READY.
    status = "MISSING_DATA" if missing else "MAPPING_REQUIRED" if mapping_required else "READY"
    fingerprint = hashlib.sha256(json.dumps({"template": template.source_sha256, "sources": sources}, sort_keys=True).encode()).hexdigest()
    manifest = {"context": context, "template": {"id": template.id, "name": template.name, "version": template.version, "source_reference": template.source_reference},
        "changes": period_changes + changes, "missing": sorted(set(missing)), "mapping_required": sorted(set(mapping_required)), "sources": sources}
    preparation = ReportPreparation.objects.create(template=template, report_type=report_type, year=year, quarter=quarter,
        status=status, manifest=manifest, source_fingerprint=fingerprint, created_by=user, expires_at=timezone.now() + timedelta(hours=24))
    return preparation


def current_fingerprint(preparation):
    _, sources = _value_index(approved_submissions())
    return hashlib.sha256(json.dumps({"template": preparation.template.source_sha256, "sources": sources}, sort_keys=True).encode()).hexdigest()


def _direction(value):
    return "increased" if value > 0 else "decreased" if value < 0 else "remained unchanged"


def generate_report(preparation, user, idempotency_key):
    existing = GeneratedReport.objects.filter(idempotency_key=idempotency_key).first()
    if existing: return existing
    if preparation.status != "READY": raise ValueError("Resolve every missing value and mapping before generating the final report.")
    if preparation.expires_at <= timezone.now() or current_fingerprint(preparation) != preparation.source_fingerprint:
        preparation.status = "STALE"; preparation.save(update_fields=["status"])
        raise ValueError("Report data changed after preparation. Prepare the report again.")
    result = GeneratedReport.objects.create(preparation=preparation, source_fingerprint=preparation.source_fingerprint,
        idempotency_key=idempotency_key, generated_by=user, validation_result={"passed": True})
    try:
        content = render_pdf(preparation)
        filename = preparation.template.filename_pattern.format(year=preparation.year, quarter=preparation.quarter or "")
        root = Path(settings.PRIVATE_EXPORT_ROOT) / "reports" / preparation.report_type.lower()
        root.mkdir(parents=True, exist_ok=True)
        path = root / f"{result.id}.pdf"; path.write_bytes(content)
        result.status = "READY"; result.filename = filename; result.private_path = str(path); result.file_size = len(content)
        result.sha256 = hashlib.sha256(content).hexdigest(); result.completed_at = timezone.now(); result.save()
    except Exception as exc:
        result.status = "FAILED"; result.error_message = str(exc); result.completed_at = timezone.now(); result.save()
        raise
    return result


def render_pdf(preparation):
    import io
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    out = io.BytesIO(); styles = getSampleStyleSheet(); story = []
    context, template = preparation.manifest["context"], preparation.template
    story.extend([Spacer(1, 80), Paragraph(template.name.upper(), styles["Title"]), Spacer(1, 24), Paragraph(context["period_label"], styles["Heading1"])])
    if preparation.report_type == "QUARTERLY_BULLETIN": story.append(Paragraph(context["quarter_name"] + " - " + context["month_range"], styles["Heading2"]))
    story.append(Spacer(1, 36))
    for block in template.immutable_blocks:
        story.extend([Paragraph(block, styles["BodyText"]), Spacer(1, 10)])
    story.extend([PageBreak(), Paragraph("Report Changes", styles["Heading1"]), Paragraph("Every value below is tied to the approved source manifest captured during preparation.", styles["BodyText"]), Spacer(1, 12)])
    rows = [["Section", "Indicator", "Value", "Source"]] + [[c["section"], c["field"], c["new_value"], c["data_source"]] for c in preparation.manifest["changes"]]
    table = Table(rows, repeatRows=1, colWidths=[90, 190, 90, 150]); table.setStyle(TableStyle([("BACKGROUND", (0,0),(-1,0),colors.HexColor("#002d5b")),("TEXTCOLOR",(0,0),(-1,0),colors.white),("GRID",(0,0),(-1,-1),.25,colors.grey),("FONTSIZE",(0,0),(-1,-1),7),("VALIGN",(0,0),(-1,-1),"TOP")]))
    story.append(table)
    doc = SimpleDocTemplate(out, pagesize=A4, title=template.name); doc.build(story); return out.getvalue()
