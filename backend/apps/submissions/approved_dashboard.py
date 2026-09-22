"""Read-only projection of approved returns onto the preserved dashboard baseline.

Mappings are exact form/indicator codes; labels never match historical metrics.
Unmapped numeric indicators get independent form-scoped charts.
"""
from copy import deepcopy
from decimal import Decimal, InvalidOperation
import hashlib
import math
import re

from .models import Submission

SERVICES = {
    "mobile": "Mobile", "fixed": "Fixed Network", "bwa": "BWA",
    "broadcasting": "Broadcasting Services", "fibre": "Fibre Broadband",
    "infrastructure": "Infrastructure",
}
PROVIDER_NAMES = {"VOD": "Telecel", "MTN": "MTN", "ATG": "AT", "SUR": "Surfline"}
# Only historical charts with independently identifiable operator series can
# safely receive replacement observations. Aggregate-only historical totals
# remain intact because their provider contributions cannot be reconstructed.
HISTORICAL_MAPPINGS = {
    ("MNO-MONTHLY", "TOTAL_MOBILE_CELLULAR_VOICE_SUBSCRIPTIONS_PREPAID_POSTPAID"): ("voice-subs-market-share", "subscriptions", 1),
    ("MNO-MONTHLY", "TOTAL_MOBILE_CELLULAR_DATA_SUBSCRIPTIONS"): ("mobile-data-subs-operator-share", "subscriptions", 1),
    ("MNO-MONTHLY", "TOTAL_FIXED_TELEPHONE_SUBSCRIPTIONS"): ("fixed-voice-subs-market-share", "subscriptions", 1),
    ("MNO-MONTHLY", "TOTAL_FIXED_BROADBAND_SUBSCRIPTIONS"): ("fixed-bb-per-operator", "subscriptions", 1),
    ("MNO-MONTHLY", "TOTAL_MOBILE_DATA_INTERNET_VOLUMES"): ("mobile-data-traffic-operator", "TB", 0.000001),
    ("MNO-MONTHLY", "FIXED_BROADBAND_INTERNET_TRAFFIC_MB"): ("fixed-bb-traffic", "TB", 0.000001),
    ("MNO-MONTHLY", "SMS_ON_NET"): ("sms-on-net-per-mno", "messages", 1),
    ("DC-ISP06", "6_1_FIXED_WIRELESS_ACCESS_SUBSCRIPTIONS"): ("bwa-subs-operator", "subscriptions", 1),
}

DERIVED_TOTALS = [
    ("mobile-data-subs-operator-share", "mobile-data-subs-penetration", "Mobile data subscriptions"),
    ("mobile-data-traffic-operator", "mobile-data-traffic", "Total Mobile data usage"),
    ("fixed-voice-subs-market-share", "fixed-voice-subs-penetration", "Total Fixed Voice Subscriptions"),
    ("fixed-bb-per-operator", "fixed-bb-subs", "Total Fixed Broadband Subscriptions"),
    ("bwa-subs-operator", "bwa-industry-total", "Industry Total"),
    ("bwa-subs-operator", "bwa-subs-penetration", "BWA Subscriptions"),
]


def period_label(period):
    if period.frequency == "MONTHLY" and period.month:
        return f"{period.year}-{period.month:02d}"
    if period.frequency == "QUARTERLY" and period.quarter:
        return f"Q{period.quarter} {period.year}"
    if period.frequency == "ANNUAL":
        return str(period.year)
    return None


def period_key(label):
    year = re.search(r"(20\d{2})", label)
    quarter = re.search(r"Q([1-4])", label)
    month = re.fullmatch(r"20\d{2}-(\d{2})", label)
    return (int(year[1]) if year else 0, int(month[1]) if month else int(quarter[1]) * 3 if quarter else 12, label)


def add_complete_quarters(series):
    """Replace a provider quarter only once all three approved months exist."""
    buckets = {}
    for point in series["values"]:
        if re.fullmatch(r"\d{4}-\d{2}", point["period"]):
            year, month = map(int, point["period"].split("-"))
            buckets.setdefault((year, (month - 1) // 3 + 1), []).append(point)
    for (year, quarter), points in buckets.items():
        if len(points) != 3:
            continue
        values = [p["value"] for p in sorted(points, key=lambda p: p["period"])]
        amount = sum(values) if series["aggregation"] == "sum" else sum(values) / 3 if series["aggregation"] == "average" else values[-1]
        period = f"Q{quarter} {year}"
        series["values"] = [p for p in series["values"] if p["period"] != period] + [{"period": period, "value": amount}]
    series["values"].sort(key=lambda p: period_key(p["period"]))


def service_for(form_code, category, code):
    if category in {"PAY_TV", "BROADCASTING"} or form_code == "DC-TB02":
        return "broadcasting"
    if category in {"DOMESTIC_FIBRE", "SUBMARINE_FIBRE"}:
        return "fibre"
    if category in {"TOWER_MAIN", "TOWER_OPERATOR"}:
        return "infrastructure"
    if "FIBRE" in code or "FIBER" in code:
        return "fibre"
    if "WIRELESS" in code or "WIMAX" in code or category == "BWA":
        return "bwa"
    if "FIXED" in code or "DSL" in code or "COPPER" in code:
        return "fixed"
    return "mobile" if category == "MNO" else "bwa" if category == "ISP" else None


def schema_targets(submission):
    schema = submission.form_schema_snapshot
    if not schema and submission.expected.form_template_id:
        from apps.forms_engine.serializers import FormTemplateDetailSerializer
        schema = FormTemplateDetailSerializer(submission.expected.form_template).data
    targets = {}
    for section in schema.get("sections", []):
        for field in section.get("fields", []):
            targets[("field", str(field["id"]))] = (section, field, field["field_code"], field["label"])
        for grid in section.get("grids", []):
            for column in grid.get("columns", []):
                for row in grid.get("fixed_rows", []):
                    targets[("grid", str(grid["id"]), str(row["id"]), str(column["id"]))] = (
                        section, column, f"{grid['grid_code']}:{row['row_label']}:{column['column_code']}",
                        f"{grid['title']} / {row['row_label']} / {column['label']}",
                    )
    return schema, targets


def overlay_approved_submissions(baseline):
    result = deepcopy(baseline)
    sectors = {item["id"]: item for item in result.setdefault("sectors", [])}
    for service, label in SERVICES.items():
        if service not in sectors:
            sectors[service] = {"id": service, "label": label, "dashboardTitle": label,
                "scope": "NCA-approved provider returns", "defaultRange": "12",
                "defaultForecastMetric": "", "indicatorSections": [], "sections": []}
            result["sectors"].append(sectors[service])
    charts = {item["id"]: item for item in result.setdefault("charts", [])}
    fibre_ids = {c["id"] for c in charts.values() if c.get("sectorId") == "mobile"
                 and re.search(r"fibre|fiber", c.get("title", ""), re.I)}
    if fibre_ids:
        for section in sectors["mobile"]["sections"]:
            section["chartIds"] = [i for i in section["chartIds"] if i not in fibre_ids]
        sectors["fibre"]["sections"].append({"id":"fibre-overview","label":"Overview","chartIds":sorted(fibre_ids)})
        for chart_id in fibre_ids:
            charts[chart_id]["sectorId"] = "fibre"
            for context in charts[chart_id].get("placementContexts", []):
                context.update(sectorId="fibre", sector="Fibre Broadband")
    operators = {item["name"] for item in result.setdefault("operators", [])}
    periods = set(result.get("periods", []))
    seen = set()
    contributions = {}
    submissions = Submission.objects.filter(
        regulatory_status="APPROVED", submitted_at__isnull=False,
        expected__form_template__isnull=False,
    ).exclude(expected__workflow_status="ARCHIVED").select_related(
        "expected__provider", "expected__period", "expected__form_template",
    ).prefetch_related("values").order_by("-reviewed_at", "-version", "-id")
    for submission in submissions:
        expected = submission.expected
        period = period_label(expected.period)
        if not period:
            continue
        schema, targets = schema_targets(submission)
        form = schema.get("form_code", expected.form_template.form_code)
        identity = (expected.provider_id, form, period)
        if identity in seen:
            continue
        seen.add(identity)
        provider = PROVIDER_NAMES.get(expected.provider.provider_code, expected.provider.registered_name)
        if provider not in operators:
            result["operators"].append({"name": provider, "color": "#1677ff"})
            operators.add(provider)
        for value in submission.values.all():
            key = ("field", str(value.field_id)) if value.field_id else (
                "grid", str(value.grid_id), value.grid_row_id, str(value.grid_column_id))
            target = targets.get(key)
            if not target:
                continue
            section, field, code, label = target
            if field.get("field_type") not in {"number", "currency", "percentage"}:
                continue
            if value.value_status not in {"PROVIDED", "SYSTEM_CALCULATED"} or not value.value.strip():
                continue
            try:
                numeric = Decimal(value.value)
            except InvalidOperation:
                continue
            if not numeric.is_finite():
                continue
            if not math.isfinite(float(numeric)):
                continue
            service = service_for(form, schema.get("provider_category", ""), code)
            if not service:
                continue
            mapping = HISTORICAL_MAPPINGS.get((form, code))
            if mapping and mapping[0] in charts:
                chart = charts[mapping[0]]
                numeric *= Decimal(str(mapping[2]))
            else:
                chart_id = "approved-" + hashlib.sha256(
                    f"{form}:{section['section_code']}:{code}".encode()).hexdigest()[:20]
                chart = charts.get(chart_id)
                if not chart:
                    unit = field.get("unit") or ("%" if field["field_type"] == "percentage" else "GHS" if field["field_type"] == "currency" else "")
                    chart = {"id": chart_id, "title": label, "wordGraphTitle": label,
                        "sectorId": service, "type": "line", "unit": unit, "unitLabel": unit,
                        "axisLabel": unit, "secondaryUnit": None, "secondaryAxisLabel": None,
                        "presentation": {"kind": "lineBand", "emphasis": "standard",
                            "showComposition": False, "showRanking": False, "averageBand": False},
                        "sourceSheet": section["title"], "sourceWorkbook": "",
                        "note": "NCA-approved returns. Latest approved version per provider and reporting period.",
                        "annotations": [], "series": [], "shareSeries": [], "coverageIds": [],
                        "placementContexts": [], "isSupporting": False, "parentId": None,
                        "supportingChartIds": [], "hasTargets": False,
                        "providerAggregation": "average" if field["field_type"] == "percentage" else "sum"}
                    charts[chart_id] = chart
                    result["charts"].append(chart)
                    section_id = f"approved-{form}-{section['section_code']}"
                    destination = next((s for s in sectors[service]["sections"] if s["id"] == section_id), None)
                    if destination is None:
                        destination = {"id": section_id, "label": f"{form} · {section['title']}", "chartIds": []}
                        sectors[service]["sections"].append(destination)
                    destination["chartIds"].append(chart_id)
            series = next((s for s in chart["series"] if s["name"] == provider), None)
            if series is None:
                aggregation = chart["series"][0]["aggregation"] if chart["series"] else (
                    "average" if field["field_type"] == "percentage" or "RATE" in code else
                    "sum" if any(token in code for token in ["TRAFFIC", "VOLUME", "REVENUE", "TRANSACTIONS", "CAPEX"]) else "yearEnd")
                series = {"name": provider, "aggregation": aggregation, "values": []}
                chart["series"].append(series)
            point = {"period": period, "value": float(numeric)}
            series["values"] = [p for p in series["values"] if p["period"] != period] + [point]
            series["values"].sort(key=lambda p: period_key(p["period"]))
            contributions.setdefault(chart["id"], []).append({
                "submission_id": submission.id, "submission_reference": submission.submission_reference,
                "provider_id": expected.provider_id, "period": period})
            periods.add(period)
    for chart in result["charts"]:
        if chart["id"] in contributions:
            chart["approvedSources"] = contributions[chart["id"]]
            for series in chart["series"]:
                add_complete_quarters(series)
                periods.update(p["period"] for p in series["values"])
            # Recalculate a total using provider-level deltas when a historical
            # breakdown exists, retaining the baseline's other contributors.
            original = next((c for c in baseline.get("charts", []) if c["id"] == chart["id"]), {})
            old_series = {s["name"]: {p["period"]: p["value"] for p in s["values"]} for s in original.get("series", [])}
            for total in [s for s in chart["series"] if s["name"].lower() in {"total", "industry total"}]:
                for point in total["values"]:
                    if point["value"] is None:
                        continue
                    for series in chart["series"]:
                        if series["name"] not in operators:
                            continue
                        old = old_series.get(series["name"], {}).get(point["period"])
                        new = next((p["value"] for p in series["values"] if p["period"] == point["period"]), None)
                        if old is not None and new is not None:
                            point["value"] += new - old
            # Provider shares must be recalculated from the current operator figures.
            for share in chart.get("shareSeries", []):
                for point in share["values"]:
                    if any(source["period"] == point["period"] for source in contributions[chart["id"]]):
                        rows = [p["value"] for s in chart["series"] if s["name"] in operators
                                for p in s["values"] if p["period"] == point["period"] and p["value"] is not None]
                        own = next((p["value"] for s in chart["series"] if s["name"] == share["name"]
                                    for p in s["values"] if p["period"] == point["period"]), None)
                        point["value"] = own / sum(rows) * 100 if own is not None and sum(rows) else None
    # Update headline totals from their operator series. For existing historical
    # totals apply only known provider deltas, preserving all other history.
    for source_id, destination_id, series_name in DERIVED_TOTALS:
        if source_id not in contributions or destination_id not in charts:
            continue
        source = charts[source_id]
        destination = charts[destination_id]
        target = next((s for s in destination["series"] if s["name"] == series_name), None)
        if target is None:
            continue
        original = next((c for c in baseline["charts"] if c["id"] == source_id), {})
        old = {(s["name"],p["period"]):p["value"] for s in original.get("series",[]) for p in s["values"]}
        existing = {p["period"]:p["value"] for p in target["values"]}
        source_periods = {p["period"] for s in source["series"] for p in s["values"]}
        for period in source_periods:
            values = [(s["name"],p["value"]) for s in source["series"] if s["name"] in operators
                      for p in s["values"] if p["period"]==period and p["value"] is not None]
            if not values:
                continue
            if period not in existing or existing[period] is None:
                existing[period] = sum(v for _,v in values)
            else:
                existing[period] += sum(v-old[name,period] for name,v in values if old.get((name,period)) is not None)
        target["values"] = [{"period":p,"value":v} for p,v in sorted(existing.items(), key=lambda item:period_key(item[0]))]
        destination["approvedSources"] = contributions[source_id]
    result["periods"] = sorted(periods, key=period_key)
    result["metadata"]["monthlyDataAvailable"] = any(re.fullmatch(r"\d{4}-\d{2}", p) for p in periods)
    result["metadata"]["approvedSubmissionCount"] = len(seen)
    return result
