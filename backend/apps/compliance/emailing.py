import re
from django.conf import settings
from django.utils import timezone
from apps.submissions.readiness import calculate_submission_readiness

PLACEHOLDERS = {"provider_name", "recipient_name", "recipient_email", "recipient_organization", "sender_name", "sender_role",
    "form_name", "form_code", "submission_reference", "period_name", "reporting_year", "due_date",
    "revised_due_date", "workflow_status", "action", "reason", "comments", "correction_targets",
    "next_action", "submitted_at", "reviewed_at", "days_until_due", "days_overdue", "missing_sections",
    "missing_fields", "missing_kmz", "portal_link", "penalty_reference", "penalty_amount"}
TOKEN = re.compile(r"{{\s*([a-zA-Z0-9_]+)\s*}}")

def validate_template(template):
    used=set(TOKEN.findall(template.subject+"\n"+template.body)); unknown=used-PLACEHOLDERS
    return {"valid":not unknown,"unknown":sorted(unknown),"used":sorted(used)}

def context_for(expected, *, actor=None, payload=None, submission=None):
    payload = payload or {}
    due=expected.effective_due_at; delta=(due.date()-timezone.localdate()).days
    submission=submission or expected.versions.order_by("-version").first(); readiness=calculate_submission_readiness(submission) if submission else {"blocking_issues":[]}
    issues=readiness.get("blocking_issues",[])
    template = expected.form_template
    form_name = template.name if template else expected.form_name_snapshot
    form_code = template.form_code if template else expected.form_code_snapshot
    target_labels = payload.get("target_labels") or payload.get("targets") or []
    if isinstance(target_labels, list):
        formatted_targets = []
        for item in target_labels:
            if isinstance(item, dict):
                label = str(item.get("label") or item.get("target_label") or item.get("instruction") or "Flagged item")
                reason = str(item.get("reason") or item.get("comment") or item.get("instruction") or "").strip()
                formatted_targets.append(f"- {label}: {reason}" if reason else f"- {label}")
            else:
                formatted_targets.append(f"- {item}")
        target_labels = "\n".join(formatted_targets)
    action = str(payload.get("action") or "")
    base_portal = getattr(settings,"PORTAL_URL","").rstrip("/")
    portal_link = f"{base_portal}/submissions/{submission.id}/review" if submission and action == "OFFICIALLY_SUBMITTED" else f"{base_portal}/provider/submissions/{expected.id}"
    return {"provider_name":expected.provider.registered_name,"recipient_name":payload.get("recipient_name", "Colleague"),
        "recipient_email":payload.get("recipient_email", ""),
        "recipient_organization":payload.get("recipient_organization", expected.provider.registered_name),
        "sender_name":getattr(actor,"name","") or "NCA Compliance System", "sender_role":getattr(actor,"get_role_display",lambda:"System")(),
        "form_name":form_name,"form_code":form_code,"submission_reference":getattr(submission,"submission_reference","") or "",
        "period_name":expected.period.name,"reporting_year":str(expected.period.year),
        "due_date":due.strftime("%d %B %Y"),"workflow_status":expected.workflow_status,"days_until_due":str(max(delta,0)),"days_overdue":str(max(-delta,0)),
        "revised_due_date":str(payload.get("revised_due_date") or ""), "action":action,
        "reason":str(payload.get("reason") or payload.get("comment") or ""), "comments":str(payload.get("comments") or payload.get("approval_note") or ""),
        "correction_targets":target_labels, "next_action":str(payload.get("next_action") or ""),
        "submitted_at":submission.submitted_at.strftime("%d %B %Y %H:%M") if submission and submission.submitted_at else "",
        "reviewed_at":submission.reviewed_at.strftime("%d %B %Y %H:%M") if submission and submission.reviewed_at else "",
        "missing_sections":", ".join(sorted({x.get("section_code","") for x in issues if x.get("section_code")})),
        "missing_fields":", ".join(x.get("label","") for x in issues if x.get("type") in {"FIELD","GRID_CELL"}),
        "missing_kmz":", ".join(x.get("label","") for x in issues if x.get("type")=="UPLOAD"),
        "portal_link":portal_link,
        "penalty_reference":expected.penalty_reference or getattr(settings,"APPROVED_PENALTY_REFERENCE",""),
        "penalty_amount":f"GH₵{expected.penalty_amount_ghs:,.2f}",
    }

def render_template(template,expected, *, actor=None, payload=None, submission=None):
    check=validate_template(template)
    if not check["valid"]: raise ValueError(f"Unknown placeholders: {', '.join(check['unknown'])}")
    context=context_for(expected, actor=actor, payload=payload, submission=submission); render=lambda text:TOKEN.sub(lambda m:context.get(m.group(1),""),text)
    return render(template.subject),render(template.body),context
