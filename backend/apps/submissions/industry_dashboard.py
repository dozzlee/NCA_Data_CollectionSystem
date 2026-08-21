import json
from copy import deepcopy
from pathlib import Path

from django.conf import settings


def dashboard_dataset_path():
    configured = getattr(settings, "INDUSTRY_DASHBOARD_DATASET", "")
    if configured:
        return Path(configured)
    return settings.BASE_DIR / "private_dashboard" / "industry-dashboard.json"


def load_dashboard_dataset():
    with dashboard_dataset_path().open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _aggregate_operator_series(series_items, periods):
    """Build one non-identifying industry series from operator observations."""
    if not series_items:
        return None

    values_by_period = {
        period: [
            observation.get("value")
            for series in series_items
            for observation in series.get("values", [])
            if observation.get("period") == period
            and isinstance(observation.get("value"), (int, float))
        ]
        for period in periods
    }
    return {
        "name": "Industry total",
        "aggregation": series_items[0].get("aggregation", "average"),
        "values": [
            {
                "period": period,
                "value": sum(values) if values else None,
            }
            for period, values in values_by_period.items()
        ],
    }


def dataset_for_user(dataset, user):
    """Return dashboard data with source/detail information appropriate to the actor."""
    role = getattr(user, "role", "")
    privileged = role in {"NCA_ADMIN", "NCA_OFFICER"}
    provider = role.startswith("PROVIDER_")
    result = deepcopy(dataset)
    if privileged:
        return result

    operator_names = {
        str(operator.get("name", "")).strip().casefold()
        for operator in result.get("operators", [])
        if operator.get("name")
    }
    metadata = result.get("metadata", {})
    for key in ("sourceDocument", "datasetOrigin", "generatedFrom", "sourceWorkbooks"):
        metadata.pop(key, None)
    metadata["definitionAuthority"] = "NCA aggregate dashboard"
    result["coverage"] = []
    result["operators"] = []
    result["commonElements"] = []

    for chart in result.get("charts", []):
        chart["sourceWorkbook"] = ""
        chart["sourceSheet"] = ""
        chart["placementContexts"] = []
        chart["coverageIds"] = []
        operator_series = [
            series for series in chart.get("series", [])
            if str(series.get("name", "")).strip().casefold() in operator_names
        ]
        aggregate_series = [
            series for series in chart.get("series", [])
            if str(series.get("name", "")).strip().casefold() not in operator_names
        ]
        # Some workbook indicators consist entirely of operator rows. Removing
        # those rows used to leave an empty chart for providers and requesters.
        # Return the period-by-period industry total instead, without returning
        # operator names or provider-level observations.
        if not aggregate_series and operator_series:
            periods = list(result.get("periods", []))
            known_periods = set(periods)
            for series in operator_series:
                for observation in series.get("values", []):
                    period = observation.get("period")
                    if period and period not in known_periods:
                        periods.append(period)
                        known_periods.add(period)
            aggregate = _aggregate_operator_series(operator_series, periods)
            aggregate_series = [aggregate] if aggregate else []
        chart["series"] = aggregate_series
        # Composition series are normally operator/provider shares and therefore
        # are intentionally excluded from non-NCA responses.
        chart["shareSeries"] = []
    if provider:
        overview_ids = set(result.get("industryOverview", {}).get("chartIds", []))
        result["charts"] = [chart for chart in result.get("charts", []) if chart.get("id") in overview_ids]
        result["sectors"] = []
        result["providerView"] = True
    return result


def aggregate_rows(dataset):
    for chart in dataset.get("charts", []):
        for series_kind, series_items in (
            ("value", chart.get("series", [])),
            ("share", chart.get("shareSeries", [])),
        ):
            for series in series_items:
                for observation in series.get("values", []):
                    yield {
                        "dashboard": chart.get("sectorId", "industry"),
                        "chart": chart.get("title", ""),
                        "unit": chart.get("unit", ""),
                        "period": observation.get("period", ""),
                        "series_kind": series_kind,
                        "series": series.get("name", ""),
                        "value": observation.get("value"),
                    }
