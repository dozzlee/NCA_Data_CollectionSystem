import hashlib
from datetime import date
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.users.models import User
from apps.forms_engine.gaps import recalculate_form_gaps
from apps.forms_engine.models import (
    FormFamily, FormTemplate, FormSection, FormField, FormGrid, GridColumn,
    GridRow, KMZUploadRequirement, SelectOption, ValidationRule, FormRequirement,
)


GHANA_REGIONS = ["Ahafo", "Ashanti", "Bono", "Bono East", "Central", "Eastern", "Greater Accra", "North East", "Northern", "Oti", "Savannah", "Upper East", "Upper West", "Volta", "Western", "Western North"]
PHONE_BRANDS = ["Samsung", "Apple", "Huawei", "Honor", "Nokia", "Xiaomi", "OPPO", "LG", "Vivo", "Lenovo", "Tecno", "Infinix", "Google", "Motorola", "Sony", "Realme", "Hisense", "TCL", "HTC", "OnePlus", "BLU", "Itel", "Others"]
OPERATORS = ["MTN", "Vodafone", "AirtelTigo", "Glo", "ICH"]
WEST_AFRICA = ["Benin", "Burkina Faso", "Cape Verde", "Cote D'Ivoire", "Gambia", "Guinea", "Guinea-Bissau", "Liberia", "Mali", "Mauritania", "Niger", "Nigeria", "Senegal", "Sierra Leone", "Togo"]
TOP_COUNTRIES = ["Canada", "China", "France", "Germany", "Italy", "Nigeria", "South Africa", "UAE", "UK", "USA"]
OTT_APPS = ["Amazon", "BitTorrent", "Facebook", "Google", "Google Classroom", "Google Duo", "Instagram", "Microsoft Teams", "Netflix", "Signal", "Skype", "Snapchat", "Telegram", "TikTok", "Twitter", "Webex", "WhatsApp", "YouTube", "Zoom"]


def f(code, label, field_type="number", unit="", required=True, options=None, help_text=""):
    return {"code": code, "label": label, "type": field_type, "unit": unit, "required": required,
            "options": options or [], "help": help_text}


def col(code, label, field_type="number", unit="", required=True):
    return {"code": code, "label": label, "type": field_type, "unit": unit, "required": required}


def grid(code, title, columns, rows=None, min_rows=0):
    return {"code": code, "title": title, "columns": columns, "rows": rows or [],
            "row_mode": "FIXED" if rows else "REPEATABLE", "min_rows": min_rows}


COMMON_COMPANY = [f("registered_name", "Registered company name", "text"), f("contact_name", "Contact person", "text"), f("contact_email", "Contact email", "text")]
COMMON_EMPLOYMENT = [f("male_employees", "Male employees"), f("female_employees", "Female employees"), f("total_employees", "Total employees", "formula")]
COMMON_FINANCIALS = [f("revenue", "Revenue", "currency", "GHS"), f("operating_cost", "Operating cost", "currency", "GHS"), f("capital_expenditure", "Capital expenditure", "currency", "GHS")]
DECLARATION = [f("declarant_name", "Declarant name", "text"), f("declaration_date", "Declaration date", "date"), f("confirmed", "Information is complete and accurate", "declaration")]


FORM_DEFINITIONS = {
    "MNO-MONTHLY": {
        "version": "3.0", "name": "Analysis Sheet / MNO Monthly", "frequency": "MONTHLY", "sector": "TELECOM", "category": "MNO",
        "sections": [
            ("operator_details", "Operator and Contact Details", COMMON_COMPANY),
            ("industry_subscriptions", "Industry Subscriptions", [], [grid("subscription_metrics", "Industry subscription indicators", [col("value", "Subscriptions", "number", "count")], ["Mobile voice", "Mobile data", "Prepaid 2G", "Prepaid 3G", "Prepaid 4G", "Postpaid 2G", "Postpaid 3G", "Postpaid 4G", "Newly activated SIMs", "Blocked subscriptions", "M2M", "Mobile broadband", "Mobile data traffic", "Fixed telephone", "Fixed line data", "Fixed broadband - fibre", "Fixed broadband - DSL", "Fixed broadband - wireless", "Smartphone users", "Feature/basic phone users"])]),
            ("phone_brands", "Smart and Feature/Basic Phone Counts by Brand", [f("smartphone_total", "Declared smartphone total"), f("feature_phone_total", "Declared feature/basic phone total")], [grid("phone_brand_counts", "Phone counts by brand", [col("smartphones", "Smart phones", "number", "count"), col("feature_phones", "Feature/basic phones", "number", "count")], PHONE_BRANDS)]),
            ("market_behavior", "Market and Consumer Behavior", [f("gross_additions", "Gross additions", "number", "count"), f("churn", "Churn", "number", "count"), f("net_additions", "Net additions", "formula", "count")]),
            ("network_parameters", "Network Parameters", [f("network_availability", "Network availability", "percentage", "%"), f("call_setup_success", "Call setup success rate", "percentage", "%"), f("dropped_call_rate", "Dropped call rate", "percentage", "%")]),
            ("sms_counts", "SMS Counts", [], [grid("sms_by_operator", "SMS traffic by operator", [col("on_net", "On-net", "number", "count"), col("off_net", "Off-net", "number", "count"), col("international", "International", "number", "count")], OPERATORS)]),
            ("pricing_arpu", "Pricing and ARPU", [f("voice_arpu", "Voice ARPU", "currency", "GHS"), f("data_arpu", "Data ARPU", "currency", "GHS"), f("average_voice_price", "Average voice price", "currency", "GHS"), f("average_data_price", "Average data price", "currency", "GHS")]),
            ("domestic_roaming", "Domestic Voice Traffic and Roaming", [], [grid("operator_traffic", "Domestic and roaming traffic", [col("mobile_incoming", "Mobile incoming", "number", "minutes"), col("mobile_outgoing", "Mobile outgoing", "number", "minutes"), col("fixed_incoming", "Fixed incoming", "number", "minutes"), col("fixed_outgoing", "Fixed outgoing", "number", "minutes"), col("roaming_inbound", "Inbound roaming", "number", "minutes"), col("roaming_outbound", "Outbound roaming", "number", "minutes"), col("roaming_data", "Roaming data", "number", "MB")], OPERATORS)]),
            ("international_traffic", "International Traffic", [], [grid("international_traffic", "International traffic minutes and counts", [col("minutes", "Minutes", "number", "minutes"), col("calls", "Calls", "number", "count")], ["Incoming", "Outgoing", "Transit"])]),
            ("west_africa", "West Africa Regional Traffic", [], [grid("west_africa_traffic", "West Africa traffic", [col("incoming", "Incoming", "number", "minutes"), col("outgoing", "Outgoing", "number", "minutes")], WEST_AFRICA)]),
            ("top_countries", "Top 10 International Country Traffic", [], [grid("top_country_traffic", "Top-country traffic", [col("incoming", "Incoming", "number", "minutes"), col("outgoing", "Outgoing", "number", "minutes")], TOP_COUNTRIES)]),
            ("ott_usage", "OTT Application and Website Data Usage", [], [grid("ott_usage", "OTT data usage", [col("data_usage", "Data usage", "number", "MB")], OTT_APPS)]),
            ("mobile_money", "Mobile Money Payment", [], [grid("mobile_money_metrics", "Mobile money metrics", [col("subscriptions", "Subscriptions", "number", "count"), col("transaction_count", "Transactions", "number", "count"), col("transaction_value", "Transaction value", "currency", "GHS"), col("fees", "Fees", "currency", "GHS")], ["Mobile money"])]),
        ],
        "rules": [
            {"type": "GRID_TOTAL", "grid": "phone_brand_counts", "column": "smartphones", "equals": "smartphone_total", "message": "Phone-brand smartphone counts must equal the declared total."},
            {"type": "GRID_TOTAL", "grid": "phone_brand_counts", "column": "feature_phones", "equals": "feature_phone_total", "message": "Phone-brand feature/basic counts must equal the declared total."},
            {"type": "FORMULA", "field": "net_additions", "expression": {"op": "-", "args": [{"field_code": "gross_additions"}, {"field_code": "churn"}]}, "message": "Net additions are calculated from gross additions less churn."},
        ],
    },
    "DC-ISP06": {
        "version": "3.0", "name": "Internet / Public Data Service Providers", "frequency": "SEMI_ANNUAL", "sector": "TELECOM", "category": "ISP",
        "sections": [
            ("company_details", "Company Details", COMMON_COMPANY), ("employment", "Employment", COMMON_EMPLOYMENT), ("financials", "Financials", COMMON_FINANCIALS),
            ("upstream_transit", "Upstream Transit", [], [grid("supplier_rows", "Upstream suppliers", [col("supplier", "Supplier", "text"), col("capacity", "Capacity", "number", "Gbps"), col("cost", "Cost", "currency", "GHS")], min_rows=1)]),
            ("iru_contracts", "IRU Contracts", [f("has_iru", "Has IRU contracts", "boolean"), f("iru_details", "IRU contract details", "textarea")]),
            ("gix", "Local Internet Service and GIX", [f("connected_to_gix", "Connected to GIX", "boolean"), f("gix_capacity", "GIX capacity", "number", "Gbps")]),
            ("bandwidth", "Bandwidth Deployment and Usage", [f("deployed_bandwidth", "Deployed bandwidth", "number", "Gbps"), f("used_bandwidth", "Used bandwidth", "number", "Gbps")]),
            ("subscribers", "Subscriber Base", [f("residential_subscribers", "Residential subscribers", "number", "count"), f("business_subscribers", "Business subscribers", "number", "count")]),
            ("broadband", "Fixed Broadband by Technology and Speed", [], [grid("broadband_by_technology", "Broadband subscriptions", [col("subscribers", "Subscribers", "number", "count")], ["Fibre", "DSL", "Fixed wireless", "Satellite", "Other"]), grid("broadband_by_speed", "Broadband by speed", [col("subscribers", "Subscribers", "number", "count")], ["Below 2 Mbps", "2-10 Mbps", "10-50 Mbps", "50-100 Mbps", "Above 100 Mbps"])]),
            ("retail_services", "Retail Services and Installation Fees", [], [grid("package_tariffs", "Retail packages and tariffs", [col("package", "Package", "text"), col("speed", "Speed", "number", "Mbps"), col("installation_fee", "Installation fee", "currency", "GHS"), col("monthly_price", "Monthly price", "currency", "GHS")], min_rows=1)]),
            ("pops", "Points of Presence", [], [grid("pop_locations", "Points of presence", [col("location", "Location", "text"), col("latitude", "Latitude", "number", "degrees"), col("longitude", "Longitude", "number", "degrees")], min_rows=1)]),
            ("backhaul", "Backhaul Links and Frequencies", [], [grid("backhaul_links", "Backhaul links", [col("from", "From", "text"), col("to", "To", "text"), col("technology", "Technology", "text"), col("frequency", "Frequency", "number", "MHz")], min_rows=1)]),
            ("towers", "Tower Distribution", [], [grid("tower_distribution", "Tower distribution", [col("towers", "Towers", "number", "count")], GHANA_REGIONS)]),
            ("vsat", "VSAT Hub", [f("operates_vsat", "Operates a VSAT hub", "boolean"), f("vsat_location", "VSAT hub location", "text")]),
            ("tariffs", "Tariffs", [], [grid("tariff_schedule", "Tariff schedule", [col("service", "Service", "text"), col("tariff", "Tariff", "currency", "GHS")], min_rows=1)]),
            ("comments", "Comments", [f("comments", "Comments", "textarea", required=False)]),
        ],
        "conditions": [("iru_details", "has_iru", "true"), ("gix_capacity", "connected_to_gix", "true"), ("vsat_location", "operates_vsat", "true")],
        "rules": [{"type": "COORDINATE", "grid": "pop_locations", "message": "PoP latitude and longitude must be valid coordinates."}],
    },
    "DC-ITC04": {
        "version": "3.0", "name": "Infrastructure Tower Companies", "frequency": "SEMI_ANNUAL", "sector": "TELECOM", "category": "TOWER_OPERATOR",
        "sections": [
            ("company_details", "Company Details", COMMON_COMPANY), ("employment", "Employment", COMMON_EMPLOYMENT), ("financials", "Financials", COMMON_FINANCIALS),
            ("maintenance", "Site Maintenance", [f("maintenance_cost", "Site maintenance cost", "currency", "GHS"), f("maintained_sites", "Sites maintained", "number", "count")]),
            ("power", "On-grid and Off-grid Sites and Power Mode", [], [grid("power_mode", "Sites by power mode", [col("sites", "Sites", "number", "count")], ["On-grid", "Solar", "Generator", "Hybrid", "Other"])]),
            ("regional_towers", "Regional Owned and Managed Tower Distribution", [], [grid("regional_tower_distribution", "Regional tower distribution", [col("owned", "Owned", "number", "count"), col("managed", "Managed", "number", "count")], GHANA_REGIONS)]),
            ("tenants", "Tenant Groups", [], [grid("tenant_groups", "Tenant groups", [col("tenant", "Tenant", "text"), col("sites", "Sites", "number", "count")], min_rows=1)]),
            ("permits", "Permits", [f("permitted_sites", "Sites with permits", "number", "count"), f("pending_permits", "Pending permits", "number", "count")]),
            ("added_towers", "Added Towers", [], [grid("tower_additions", "Tower additions", [col("site", "Site", "text"), col("region", "Region", "text"), col("latitude", "Latitude", "number", "degrees"), col("longitude", "Longitude", "number", "degrees"), col("commissioned", "Commissioned", "date")], min_rows=1)]),
            ("decommissioned", "Decommissioned Towers", [], [grid("decommissioned_towers", "Decommissioned towers", [col("site", "Site", "text"), col("region", "Region", "text"), col("date", "Date", "date"), col("reason", "Reason", "text")], min_rows=0)]),
            ("acquisitions", "Acquisitions", [], [grid("tower_acquisitions", "Tower acquisitions", [col("seller", "Seller", "text"), col("sites", "Sites", "number", "count"), col("date", "Date", "date")], min_rows=0)]),
            ("declaration", "Declaration", DECLARATION),
        ],
        "rules": [{"type": "COORDINATE", "grid": "tower_additions", "message": "Tower coordinates must be valid."}],
    },
    "TOWER-MAIN-ANNUAL": {
        "version": "2.0", "name": "Infrastructure Main Companies Bi-Annual", "frequency": "SEMI_ANNUAL", "sector": "TELECOM", "category": "TOWER_MAIN", "source_decision": False,
        "sections": [("owned_sites", "Owned Sites", [], [grid("owned_sites_grid", "Owned sites", [col("value", "Sites", "number", "count")], GHANA_REGIONS)]),
            ("owned_rent", "Owned Average Rent", [], [grid("owned_rent_grid", "Owned average rent", [col("value", "Average rent", "currency", "GHS")], GHANA_REGIONS)]),
            ("managed_sites", "Managed Sites", [], [grid("managed_sites_grid", "Managed sites", [col("value", "Sites", "number", "count")], GHANA_REGIONS)]),
            ("managed_rent", "Managed Average Rent", [], [grid("managed_rent_grid", "Managed average rent", [col("value", "Average rent", "currency", "GHS")], GHANA_REGIONS)]),
            ("decommissioned", "Decommissioned Towers", [], [grid("decommissioned_grid", "Decommissioned towers", [col("value", "Towers", "number", "count")], GHANA_REGIONS)])],
    },
    "DC-DBS05": {
        "version": "2.0", "name": "Domestic / National Inland Fibre", "frequency": "SEMI_ANNUAL", "sector": "TELECOM", "category": "DOMESTIC_FIBRE", "kmz": ("topology", "TOPOLOGY"),
        "sections": [("company_details", "Company Details", COMMON_COMPANY), ("employment", "Employment", COMMON_EMPLOYMENT), ("financials", "Financials", COMMON_FINANCIALS),
            ("capacity", "Capacity", [f("backbone_capacity", "Backbone capacity", "number", "Gbps")]), ("fibre_lengths", "Fibre Lengths", [f("owned_fibre_length", "Owned fibre length", "number", "km"), f("leased_fibre_length", "Leased fibre length", "number", "km")]),
            ("leased_cables", "Leased Cables", [], [grid("leased_cables", "Leased cables", [col("supplier", "Supplier", "text"), col("length", "Length", "number", "km"), col("capacity", "Capacity", "number", "Gbps")], min_rows=0)]),
            ("microwave", "Microwave Capacity", [f("microwave_capacity", "Microwave capacity", "number", "Gbps")]), ("topology", "Backbone Topology", [f("topology_description", "Backbone topology description", "textarea")]),
            ("last_mile", "Last-mile Deployment", [f("last_mile_length", "Last-mile fibre", "number", "km")]),
            ("ftth_regions", "FTTH Regional Distribution", [], [grid("ftth_distribution", "FTTH regional distribution", [col("premises", "Premises passed", "number", "count"), col("subscribers", "Subscribers", "number", "count")], GHANA_REGIONS)]),
            ("regional_network", "Regional Fibre Network", [], [grid("regional_fibre_network", "Regional fibre network", [col("length", "Length", "number", "km"), col("capacity", "Capacity", "number", "Gbps")], GHANA_REGIONS)]),
            ("fibre_cuts", "Regional Fibre Cuts", [], [grid("regional_fibre_cuts", "Regional fibre cuts", [col("cuts", "Cuts", "number", "count"), col("repair_time", "Repair time", "number", "hours"), col("repair_cost", "Repair cost", "currency", "GHS")], GHANA_REGIONS)]),
            ("repair", "Repair Cost and Time", [f("average_repair_cost", "Average repair cost", "currency", "GHS"), f("average_repair_hours", "Average repair time", "number", "hours")]),
            ("cut_causes", "Fibre Cut Causes", [], [grid("cut_cause_classification", "Fibre cut causes", [col("count", "Count", "number", "count")], ["Road works", "Construction", "Vandalism", "Natural event", "Other"])]),
            ("coverage", "Coverage", [f("population_coverage", "Population coverage", "percentage", "%"), f("geographic_coverage", "Geographic coverage", "percentage", "%")]),
            ("declaration", "Declaration", DECLARATION)],
        "rules": [{"type": "RANGE", "field": "population_coverage", "min": 0, "max": 100, "message": "Population coverage must be between 0 and 100."}, {"type": "RANGE", "field": "geographic_coverage", "min": 0, "max": 100, "message": "Geographic coverage must be between 0 and 100."}],
    },
    "DC-SUB03": {
        "version": "2.0", "name": "International Submarine Fibre", "frequency": "SEMI_ANNUAL", "sector": "TELECOM", "category": "SUBMARINE_FIBRE",
        "sections": [("company_details", "Company Details", COMMON_COMPANY), ("employment", "Employment", COMMON_EMPLOYMENT), ("financials", "Financials", COMMON_FINANCIALS),
            ("circuit_costs", "Circuit Costs", [f("circuit_cost", "Circuit cost", "currency", "GHS")]), ("cable_metadata", "Cable Metadata", [f("cable_name", "Cable name", "text"), f("landing_station", "Landing station", "text"), f("ready_for_service", "Ready-for-service date", "date")]),
            ("global_capacity", "Total Cable Capacity", [f("global_total_capacity", "Total cable capacity", "number", "Gbps"), f("global_lit_capacity", "Total lit capacity", "number", "Gbps")]),
            ("ghana_capacity", "Ghana Segment Capacity", [f("ghana_total_capacity", "Ghana segment capacity", "number", "Gbps"), f("ghana_lit_capacity", "Ghana lit capacity", "number", "Gbps")]),
            ("client_categories", "Client Category Counts", [], [grid("client_category_counts", "Client categories", [col("clients", "Clients", "number", "count"), col("capacity", "Capacity", "number", "Gbps")], ["MNO", "ISP", "Government", "Enterprise", "Other"])]),
            ("fibre_cuts", "Fibre Cuts", [], [grid("fibre_cut_events", "Fibre cut events", [col("date", "Date", "date"), col("location", "Location", "text"), col("duration", "Duration", "number", "hours"), col("impact", "Impact", "text")], min_rows=0)]),
            ("checklist", "Completion Checklist", [f("financials_complete", "Financial information complete", "declaration"), f("capacity_complete", "Capacity information complete", "declaration")]),
            ("comments", "Comments", [f("comments", "Comments", "textarea", required=False)]), ("declaration", "Declaration", DECLARATION)],
        "rules": [{"type": "COMPARISON", "field": "ghana_total_capacity", "left": "ghana_total_capacity", "right": "global_total_capacity", "operator": "<=", "message": "Ghana segment capacity cannot exceed total cable capacity."}],
    },
    "DC-TB02": {
        "version": "3.0", "name": "Pay Television Broadcasting", "frequency": "SEMI_ANNUAL", "sector": "BROADCASTING", "category": "PAY_TV",
        "sections": [("company_details", "Company and Contact Details", COMMON_COMPANY),
            ("service_type", "Television Broadcasting Service Type", [f("service_type", "Television broadcasting service", "multiselect", options=["Satellite", "Terrestrial", "Cable", "Internet streaming"])]),
            ("encryption_streaming", "Encryption and Internet Streaming", [f("encrypted", "Service is encrypted", "boolean"), f("internet_streaming", "Provides internet streaming", "boolean"), f("streaming_platform", "Streaming platform", "text", required=False)]),
            ("affiliations", "Affiliations and Media Group Ownership", [], [grid("affiliations", "Affiliations", [col("organization", "Organization", "text"), col("relationship", "Relationship", "text")], min_rows=0)]),
            ("employment", "Employment", COMMON_EMPLOYMENT), ("financials", "Financials", COMMON_FINANCIALS),
            ("services_cost", "Types of Services and Cost", [], [grid("service_costs", "Services and cost", [col("service", "Service", "text"), col("installation", "Installation", "currency", "GHS"), col("decoder", "Decoder", "currency", "GHS"), col("monthly", "Monthly tariff", "currency", "GHS")], min_rows=1)]),
            ("dealers", "Regional Pay-TV Dealer Counts", [], [grid("regional_dealers", "Regional Pay-TV dealers", [col("dealers", "Dealers", "number", "count")], GHANA_REGIONS)]),
            ("bouquets", "Bouquet Subscriptions, Tariffs and Channel Counts", [], [grid("bouquet_services", "Bouquets", [col("bouquet", "Bouquet", "text"), col("subscriptions", "Subscriptions", "number", "count"), col("tariff", "Monthly tariff", "currency", "GHS"), col("channels", "Channels", "number", "count")], min_rows=1)]),
            ("satellite", "Satellite Services", [], [grid("satellite_providers", "Satellite services", [col("provider", "Provider", "text"), col("satellite", "Satellite", "text"), col("capacity", "Capacity", "number", "MHz")], min_rows=1)]),
            ("checklist", "Completion Checklist", [f("service_complete", "Service information complete", "declaration"), f("tariff_complete", "Tariff information complete", "declaration")]),
            ("comments", "Comments and Challenges", [f("comments", "Comments and challenges", "textarea", required=False)]), ("declaration", "Declaration", DECLARATION)],
        "conditions": [("streaming_platform", "internet_streaming", "true")],
    },
}


def _translate_expression(node, fields):
    if isinstance(node, dict):
        if "field_code" in node:
            return {"field": fields[node["field_code"]].id}
        return {key: [_translate_expression(x, fields) for x in value] if key == "args" else value for key, value in node.items()}
    return node


def _create_requirement(family, key, kind, label, description, criteria, order, severity="BLOCKER"):
    FormRequirement.objects.update_or_create(family=family, requirement_key=key, defaults={
        "requirement_type": kind, "label": label, "description": description,
        "severity": severity, "criteria": criteria, "sort_order": order,
    })


@transaction.atomic
def build_form(code, definition, source, source_hash, preparer, approver):
    family, _ = FormFamily.objects.get_or_create(code=code, defaults={"name": definition["name"]})
    family.name = definition["name"]
    family.canonical_frequency = definition["frequency"]
    family.frequency_decision_status = "APPROVED"
    family.frequency_decision_reference = "Product Requirements Document - Development Ready.docx, Section 11"
    family.source_owner = "NCA PRD"
    family.code_status = "PROVISIONAL" if code == "TOWER-MAIN-ANNUAL" else "CONFIRMED"
    family.save()
    # Older broad requirements remain attached to historical versions. They are
    # retained for audit but cease to be publication blockers until replaced by
    # the exact manifest entries below.
    family.requirements.update(severity="LOW")
    version = definition["version"]
    if family.versions.filter(version=version).exists():
        return family.versions.get(version=version), False

    form = FormTemplate.objects.create(
        family=family, form_code=code, name=definition["name"], sector=definition["sector"],
        provider_category=definition["category"], frequency=definition["frequency"], version=version,
        effective_from=date.today(), status="DRAFT", kmz_required=bool(definition.get("kmz")),
        excel_backup_enabled=True, instructions="PRD-derived manual web form. Original source-form fidelity remains pending.",
        source_reference=f"{source.name}, Section 11", source_sha256=source_hash,
        mapping_complete=True, mapping_basis="PRD_SECTION_11", approval_status="DRAFT", prepared_by=preparer,
    )
    fields, grids, columns = {}, {}, {}
    order = 0
    for section_index, (section_code, title, field_defs, *grid_defs) in enumerate(definition["sections"]):
        section = FormSection.objects.create(form_template=form, section_code=section_code, title=title,
            instructions=f"Complete the {title.lower()} requirements from PRD Section 11.", sort_order=section_index)
        _create_requirement(family, f"section:{section_code}", "SECTION", title, f"Section 11 requires {title}.", {"section_code": section_code}, order); order += 1
        for field_index, item in enumerate(field_defs):
            field = FormField.objects.create(section=section, field_code=item["code"], label=item["label"],
                field_type=item["type"], unit=item["unit"], is_required=item["required"], help_text=item["help"] or f"Required by PRD Section 11: {item['label']}.", sort_order=field_index)
            fields[item["code"]] = field
            for option_index, option in enumerate(item["options"]):
                SelectOption.objects.create(field=field, value=option.upper().replace(" ", "_"), label=option, sort_order=option_index)
            kind = "DECLARATION" if item["type"] == "declaration" else "OPTION" if item["options"] else "FIELD"
            criteria = {"section_code": section_code, "field_code": item["code"], "field_type": item["type"], "unit": item["unit"], "is_required": item["required"]}
            if item["options"]: criteria["options"] = item["options"]
            _create_requirement(family, f"field:{section_code}:{item['code']}", kind, item["label"], item["label"], criteria, order); order += 1
        for grid_index, item in enumerate(grid_defs[0] if grid_defs else []):
            model = FormGrid.objects.create(section=section, grid_code=item["code"], title=item["title"], row_mode=item["row_mode"], min_rows=item["min_rows"], sort_order=grid_index)
            grids[item["code"]] = model
            column_criteria = []
            for column_index, column in enumerate(item["columns"]):
                obj = GridColumn.objects.create(grid=model, column_code=column["code"], label=column["label"], field_type=column["type"], unit=column["unit"], is_required=column["required"], sort_order=column_index)
                columns[(item["code"], column["code"])] = obj
                column_criteria.append({"column_code": column["code"], "field_type": column["type"], "unit": column["unit"], "is_required": column["required"]})
            for row_index, row_label in enumerate(item["rows"]):
                GridRow.objects.create(grid=model, row_label=row_label, sort_order=row_index)
            _create_requirement(family, f"grid:{section_code}:{item['code']}", "GRID", item["title"], item["title"], {
                "section_code": section_code, "grid_code": item["code"], "row_mode": item["row_mode"], "min_rows": item["min_rows"],
                "fixed_rows": item["rows"], "columns": column_criteria,
            }, order); order += 1

    for child_code, parent_code, value in definition.get("conditions", []):
        child = fields[child_code]; child.conditional_on_field = fields[parent_code]; child.conditional_on_value = value; child.save(update_fields=["conditional_on_field", "conditional_on_value"])
        _create_requirement(family, f"conditional:{child_code}", "CONDITIONAL", child.label, f"{child.label} is conditional.", {
            "section_code": child.section.section_code, "field_code": child_code, "field_type": child.field_type,
            "conditional_on_field": parent_code, "conditional_on_value": value,
        }, order, "HIGH"); order += 1
        rule = ValidationRule(form_template=form, field=child, rule_type="CONDITIONAL", parameters={"when_field": fields[parent_code].id, "equals": value}, message=f"{child.label} is required when applicable.")
        rule.full_clean(); rule.save()

    for item in definition.get("rules", []):
        target_field = fields.get(item.get("field")); target_grid = grids.get(item.get("grid")); params = {}
        if item["type"] == "GRID_TOTAL": params = {"column_id": columns[(item["grid"], item["column"])].id, "equals_field": fields[item["equals"]].id}
        elif item["type"] == "FORMULA": params = {"expression": _translate_expression(item["expression"], fields)}
        elif item["type"] == "RANGE": params = {"min": item["min"], "max": item["max"]}
        elif item["type"] == "COMPARISON": params = {"left_field": fields[item["left"]].id, "right_field": fields[item["right"]].id, "operator": item["operator"]}
        elif item["type"] == "COORDINATE": params = {}
        rule = ValidationRule(form_template=form, field=target_field, grid=target_grid, rule_type=item["type"], parameters=params, message=item["message"])
        rule.full_clean(); rule.save()
        _create_requirement(family, f"validation:{order}:{item['type']}", "VALIDATION", item["message"], item["message"], {
            "rule_type": item["type"], "field_code": item.get("field"), "grid_code": item.get("grid")
        }, order, "HIGH"); order += 1

    if definition.get("kmz"):
        section_code, category = definition["kmz"]
        requirement = KMZUploadRequirement.objects.create(form_template=form, section=form.sections.get(section_code=section_code), category=category, description="Route/topology evidence required by PRD Section 11.")
        _create_requirement(family, "kmz:topology", "KMZ", "Topology KMZ", requirement.description, {"required": True, "section_code": section_code, "category": category}, order); order += 1

    if definition.get("source_decision") is False:
        _create_requirement(family, "source_decision:form_code", "SOURCE_DECISION", "Confirm the official form code", "The PRD requires confirmation of the tower-main form code.", {
            "confirmed": False, "allow_provisional": True,
            "message": "Official tower-main form code requires an NCA source-owner decision."
        }, order, "HIGH")

    assessments = recalculate_form_gaps(form, approver)
    unresolved = [item for item in assessments if item.status != "MATCHED" and item.requirement.severity in {"BLOCKER", "HIGH"}]
    if not unresolved:
        family.versions.exclude(pk=form.pk).filter(status="ACTIVE").update(status="ARCHIVED")
        form.status = "ACTIVE"; form.approval_status = "APPROVED"; form.approved_by = approver
        form.approved_at = timezone.now(); form.published_at = timezone.now(); form.save()
    return form, True


class Command(BaseCommand):
    help = "Create exact PRD Section 11 form versions without rewriting historical submissions."

    def add_arguments(self, parser):
        parser.add_argument("--source", required=True)

    def handle(self, *args, **options):
        source = Path(options["source"])
        if not source.exists() or source.suffix.lower() != ".docx":
            raise CommandError("The PRD DOCX source file was not found.")
        source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
        users = list(User.objects.filter(role__in=["NCA_ADMIN", "NCA_OFFICER"], is_active=True).order_by("created_at")[:2])
        if not users:
            raise CommandError("Create an active NCA Admin or Officer before loading forms.")
        preparer = users[0]; approver = users[1] if len(users) > 1 else users[0]
        for code, definition in FORM_DEFINITIONS.items():
            form, created = build_form(code, definition, source, source_hash, preparer, approver)
            state = "published" if form.status == "ACTIVE" else "draft with unresolved source decision"
            self.stdout.write(self.style.SUCCESS(f"{code} v{form.version}: {state}" if created else f"{code} v{form.version}: already exists"))
