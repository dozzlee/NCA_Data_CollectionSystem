import re
from django.conf import settings
from django.utils import timezone
from apps.submissions.readiness import calculate_submission_readiness

PLACEHOLDERS = {"provider_name", "form_name", "period_name", "due_date", "workflow_status", "days_until_due",
    "days_overdue", "missing_sections", "missing_fields", "missing_kmz", "portal_link", "penalty_reference"}
TOKEN = re.compile(r"{{\s*([a-zA-Z0-9_]+)\s*}}")

def validate_template(template):
    used=set(TOKEN.findall(template.subject+"\n"+template.body)); unknown=used-PLACEHOLDERS
    return {"valid":not unknown,"unknown":sorted(unknown),"used":sorted(used)}

def context_for(expected):
    due=expected.effective_due_at; delta=(due.date()-timezone.localdate()).days
    submission=expected.versions.order_by("-version").first(); readiness=calculate_submission_readiness(submission) if submission else {"blocking_issues":[]}
    issues=readiness.get("blocking_issues",[])
    return {"provider_name":expected.provider.registered_name,"form_name":expected.form_template.name,"period_name":expected.period.name,
        "due_date":due.strftime("%d %B %Y"),"workflow_status":expected.workflow_status,"days_until_due":str(max(delta,0)),"days_overdue":str(max(-delta,0)),
        "missing_sections":", ".join(sorted({x.get("section_code","") for x in issues if x.get("section_code")})),
        "missing_fields":", ".join(x.get("label","") for x in issues if x.get("type") in {"FIELD","GRID_CELL"}),
        "missing_kmz":", ".join(x.get("label","") for x in issues if x.get("type")=="UPLOAD"),
        "portal_link":getattr(settings,"PORTAL_URL",""),"penalty_reference":getattr(settings,"APPROVED_PENALTY_REFERENCE","")}

def render_template(template,expected):
    check=validate_template(template)
    if not check["valid"]: raise ValueError(f"Unknown placeholders: {', '.join(check['unknown'])}")
    context=context_for(expected); render=lambda text:TOKEN.sub(lambda m:context.get(m.group(1),""),text)
    return render(template.subject),render(template.body),context
