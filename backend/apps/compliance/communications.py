from __future__ import annotations

import hashlib
import json
import re

from django.db.models import Q

from apps.users.models import User
from .emailing import render_template
from .models import CommunicationRecord, EmailTemplate, ExternalEmailHandoff


ACTION_TEMPLATE = {
    "FORM_ASSIGNED": "FORM_ASSIGNED",
    "SUBMITTED_FOR_APPROVAL": "SUBMITTED_FOR_APPROVAL",
    "PROVIDER_RESUBMITTED": "PROVIDER_RESUBMITTED",
    "PROVIDER_CHANGES_REQUESTED": "CORRECTION_REQUEST",
    "OFFICIALLY_SUBMITTED": "SUBMITTED_TO_NCA",
    "CORRECTION_REQUESTED": "NCA_CORRECTION_REQUEST",
    "SUBMISSION_REJECTED": "SUBMISSION_REJECTED",
    "SUBMISSION_APPROVED": "SUBMISSION_APPROVED",
    "DEADLINE_CHANGED": "DEADLINE_CHANGED",
    "COMPLIANCE_NOTICE": "COMPLIANCE_NOTICE",
    "SUBMISSION_CORRESPONDENCE": "SUBMISSION_CORRESPONDENCE",
    "NCA_ACKNOWLEDGEMENT": "NCA_ACKNOWLEDGEMENT",
    "REMINDER": "REMINDER",
    "OVERDUE": "OVERDUE",
}


def _user_dict(user):
    return {"id": str(user.id), "email": user.email, "name": user.name, "role": user.role}


def recipients_for(submission, action, actor=None):
    organization_id = submission.expected.provider.organization_id
    provider_both = Q(role__in=["PROVIDER_DATA_ENTRY", "PROVIDER_APPROVER"], organization_id=organization_id)
    if action in {"SUBMITTED_FOR_APPROVAL", "PROVIDER_RESUBMITTED"}:
        query = Q(role="PROVIDER_APPROVER", organization_id=organization_id)
    elif action == "PROVIDER_CHANGES_REQUESTED":
        query = Q(role="PROVIDER_DATA_ENTRY", organization_id=organization_id)
    elif action in {"OFFICIALLY_SUBMITTED"}:
        if submission.expected.assigned_officer_id:
            query = Q(pk=submission.expected.assigned_officer_id)
        else:
            query = Q(role__in=["NCA_ADMIN", "NCA_OFFICER"])
    elif action in {"CORRECTION_REQUESTED", "COMPLIANCE_NOTICE"}:
        query = Q(role="PROVIDER_APPROVER", organization_id=organization_id)
    elif action == "SUBMISSION_CORRESPONDENCE":
        query = Q(role__in=["NCA_ADMIN", "NCA_OFFICER"]) if getattr(actor, "is_provider", False) else Q(role="PROVIDER_APPROVER", organization_id=organization_id)
    else:
        query = provider_both
    recipients = [_user_dict(user) for user in User.objects.filter(query, is_active=True).exclude(email="").order_by("email")]
    if not recipients and action == "OFFICIALLY_SUBMITTED" and submission.expected.assigned_officer_id:
        recipients = [_user_dict(user) for user in User.objects.filter(
            role__in=["NCA_ADMIN", "NCA_OFFICER"], is_active=True,
        ).exclude(email="").order_by("email")]
    if recipients:
        return recipients
    provider = submission.expected.provider
    if actor and getattr(actor, "is_nca", False):
        contacts = provider.contacts.filter(is_active=True, notify_on_review=True).exclude(email="").order_by("email")
        recipients = [{"id": "", "email": row.email, "name": row.name, "role": "PROVIDER_CONTACT"} for row in contacts]
        if not recipients and provider.primary_email:
            recipients = [{"id": "", "email": provider.primary_email, "name": provider.registered_name, "role": "PROVIDER_PRIMARY"}]
    return recipients


def _content_hash(subject, body, recipients, attachments):
    canonical = json.dumps({"subject": subject, "body": body, "recipients": recipients, "attachments": attachments}, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _fallback_content(submission, event):
    expected = submission.expected
    template = expected.form_template
    form_code = template.form_code if template else expected.form_code_snapshot
    subject = f"{event.get_event_type_display() if hasattr(event, 'get_event_type_display') else event.event_type.replace('_', ' ').title()} - {form_code} - {expected.period.name}"
    body = f"{event.message}\n\nForm: {template.name if template else expected.form_name_snapshot} ({form_code})\nReporting period: {expected.period.name}\nReference: {submission.submission_reference}\nStatus: {event.to_status or expected.workflow_status}"
    return subject, body


def without_submission_link(body):
    """Remove portal submission links from correspondence and external drafts."""
    body = re.sub(
        r"https?://[^\s]+/(?:provider/)?submissions/\d+(?:/review)?/?",
        "",
        body or "",
        flags=re.IGNORECASE,
    )
    lines = [
        line for line in body.splitlines()
        if line.strip().lower() not in {"open the submission:", "open submission:", "view submission:"}
    ]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def with_flag_details(body, event):
    """Ensure flag emails include the reviewer's message and every flagged target."""
    if event.event_type != "CORRECTION_REQUESTED":
        return body
    metadata = event.metadata or {}
    targets = metadata.get("target_labels") or metadata.get("targets") or []
    if not isinstance(targets, list):
        targets = []
    if not targets:
        # Legacy correction events stored only a target count. Recover their
        # labels and reasons from the compatible CorrectionItem records.
        from apps.forms_engine.models import FormField, FormGrid, GridColumn
        from apps.submissions.models import CorrectionItem

        template = event.submission.expected.form_template
        for correction in CorrectionItem.objects.filter(source_submission=event.submission).order_by("created_at", "id"):
            target_id = str(correction.target_id or "")
            label = "Flagged indicator"
            if correction.target_type == "SECTION" and template:
                section = template.sections.filter(section_code=target_id).first()
                label = f"Section: {section.title}" if section else "Section"
            elif correction.target_type == "FIELD" and template:
                field = FormField.objects.filter(section__form_template=template, pk=target_id).first()
                label = f"Indicator: {field.label}" if field else "Indicator"
            elif correction.target_type == "GRID_CELL" and template:
                parts = target_id.split(":")
                if len(parts) == 3:
                    grid = FormGrid.objects.filter(section__form_template=template, pk=parts[0]).first()
                    column = GridColumn.objects.filter(grid=grid, pk=parts[2]).first() if grid else None
                    row = grid.fixed_rows.filter(pk=parts[1]).first() if grid and grid.row_mode == "FIXED" else None
                    if grid and column:
                        label = f"Indicator: {grid.title} / {row.row_label if row else parts[1]} / {column.label}"
            targets.append({"label": label, "reason": correction.instruction})
    reviewer_message = str(metadata.get("comments") or metadata.get("reason") or "").strip()
    lines = []
    for index, item in enumerate(targets, start=1):
        if isinstance(item, dict):
            label = str(item.get("label") or item.get("target_label") or "Flagged indicator").strip()
            reason = str(item.get("reason") or item.get("comment") or item.get("instruction") or "").strip()
        else:
            label, reason = str(item).strip(), ""
        lines.append(f"{index}. {label}")
        if reason:
            lines.append(f"   Reason: {reason}")
    if not lines:
        return body
    details = []
    if reviewer_message:
        details.extend(["Reviewer message:", reviewer_message, ""])
    details.extend(["Flagged indicators:", *lines])
    # Templates may already support these details. Avoid appending the same block twice.
    if all(str(item.get("label", "")) in body for item in targets if isinstance(item, dict)):
        return body
    return f"{body.rstrip()}\n\n" + "\n".join(details)


def _submission_target_label(submission, target_type, target_id):
    """Resolve an audited target identifier to a stable, human-readable label."""
    from apps.forms_engine.models import FormField, FormGrid, GridColumn

    template = submission.expected.form_template
    target_id = str(target_id or "")
    if target_type == "FIELD":
        field = FormField.objects.filter(
            section__form_template=template, pk=target_id,
        ).first() if template else None
        return field.label if field else f"Indicator {target_id}"
    if target_type == "GRID_CELL":
        parts = target_id.split(":")
        if template and len(parts) == 3:
            grid = FormGrid.objects.filter(
                section__form_template=template, pk=parts[0],
            ).first()
            column = GridColumn.objects.filter(grid=grid, pk=parts[2]).first() if grid else None
            row = grid.fixed_rows.filter(pk=parts[1]).first() if grid and grid.row_mode == "FIXED" else None
            if grid and column:
                return f"{grid.title} / {row.row_label if row else parts[1]} / {column.label}"
        return f"Grid indicator {target_id}"
    if target_type == "SECTION" and template:
        section = template.sections.filter(section_code=target_id).first()
        return f"Section: {section.title}" if section else f"Section {target_id}"
    return "Submission" if target_type == "SUBMISSION" else target_id


def _audit_value(snapshot):
    snapshot = snapshot or {}
    status = str(snapshot.get("value_status") or "").replace("_", " ").title()
    value = snapshot.get("value")
    if value not in (None, ""):
        return str(value)
    return status or "Blank"


def with_provider_change_details(body, submission, event):
    """Add corrected flags and audited provider value changes to NCA handoffs."""
    if event.event_type != "OFFICIALLY_SUBMITTED":
        return body
    if "Corrected flags:" in body or "Provider indicator changes:" in body:
        return body

    from apps.submissions.models import CorrectionItem

    corrections = CorrectionItem.objects.filter(
        Q(source_submission=submission) | Q(resolution_submission=submission),
        status__in=["ADDRESSED", "VERIFIED"],
    ).order_by("created_at", "id")
    correction_lines = [
        f"{index}. {_submission_target_label(submission, item.target_type, item.target_id)}\n"
        f"   Flag: {item.instruction}\n"
        f"   Resolution: {item.get_status_display()}"
        for index, item in enumerate(corrections, start=1)
    ]

    # Collapse repeated autosaves of the same target into its earliest before and
    # latest after value so the email communicates the effective provider change.
    changes = {}
    for batch in submission.provider_edit_batches.prefetch_related("items").order_by("created_at", "id"):
        for item in batch.items.all():
            key = (item.target_type, item.target_id)
            if key not in changes:
                changes[key] = {"before": item.before, "after": item.after}
            else:
                changes[key]["after"] = item.after
    change_lines = [
        f"{index}. {_submission_target_label(submission, target_type, target_id)}: "
        f"{_audit_value(change['before'])} -> {_audit_value(change['after'])}"
        for index, ((target_type, target_id), change) in enumerate(changes.items(), start=1)
        if change["before"] != change["after"]
    ]

    details = []
    if correction_lines:
        details.extend(["Corrected flags:", *correction_lines])
    if change_lines:
        if details:
            details.append("")
        details.extend(["Provider indicator changes:", *change_lines])
    return f"{body.rstrip()}\n\n" + "\n".join(details) if details else body


PROVIDER_PENALTY_ACTIONS = {
    "FORM_ASSIGNED", "CORRECTION_REQUESTED", "PROVIDER_CHANGES_REQUESTED",
    "SUBMISSION_REJECTED", "SUBMISSION_APPROVED", "COMPLIANCE_NOTICE",
    "OVERDUE", "ESCALATION", "PENALTY_WARNING", "FINAL_NOTICE", "DEADLINE_CHANGED",
}


def with_penalty_details(body, submission, event):
    """Append governed obligation penalty information to provider-directed notices."""
    if event.event_type not in PROVIDER_PENALTY_ACTIONS or "Penalty amount:" in body:
        return body
    expected = submission.expected
    amount = expected.penalty_amount_ghs or 0
    if amount:
        lines = [f"Penalty amount: GH₵{amount:,.2f}"]
        if expected.penalty_reference:
            lines.append(f"Penalty reference: {expected.penalty_reference}")
    else:
        lines = ["Penalty amount: GH₵0.00", "No penalty assigned."]
    return f"{body.rstrip()}\n\n" + "\n".join(lines)


def content_for_event(submission, event, recipients=None):
    explicit_subject = str((event.metadata or {}).get("communication_subject") or "").strip()
    explicit_body = str((event.metadata or {}).get("communication_body") or "").strip()
    if explicit_subject or explicit_body:
        fallback_subject, fallback_body = _fallback_content(submission, event)
        body = without_submission_link(explicit_body or fallback_body)
        body = with_flag_details(body, event)
        body = with_provider_change_details(body, submission, event)
        return explicit_subject or fallback_subject, with_penalty_details(body, submission, event)
    template_type = ACTION_TEMPLATE.get(event.event_type)
    template = EmailTemplate.objects.filter(template_type=template_type, status="APPROVED").order_by("-version").first() if template_type else None
    if template:
        try:
            first_recipient = (recipients or [{}])[0]
            payload = {**(event.metadata or {}), "action": event.event_type,
                       "recipient_name": first_recipient.get("name", ""),
                       "recipient_email": first_recipient.get("email", "")}
            subject, body = render_template(template, submission.expected, actor=event.actor, payload=payload, submission=submission)[:2]
            body = with_flag_details(without_submission_link(body), event)
            body = with_provider_change_details(body, submission, event)
            return subject, with_penalty_details(body, submission, event)
        except (ValueError, TypeError):
            pass
    subject, body = _fallback_content(submission, event)
    body = with_flag_details(without_submission_link(body), event)
    body = with_provider_change_details(body, submission, event)
    return subject, with_penalty_details(body, submission, event)


def create_system_record(*, submission, event):
    recipients = [
        _user_dict(item.recipient)
        for item in event.notifications.select_related("recipient").all()
    ]
    subject, body = content_for_event(submission, event, recipients)
    record, _ = CommunicationRecord.objects.get_or_create(
        submission_event=event,
        defaults={
            "submission": submission,
            "expected_submission": submission.expected,
            "event_type": event.event_type,
            "channel": "SYSTEM",
            "direction": "INTERNAL" if event.audience in {"NCA", "INTERNAL"} else "OUTBOUND",
            "sender": event.actor,
            "sender_snapshot": _user_dict(event.actor) if event.actor else {"name": "System", "role": "SYSTEM"},
            "recipients": recipients,
            "subject": subject,
            "body": body,
            "from_status": event.from_status,
            "to_status": event.to_status,
            "submission_reference": submission.submission_reference,
            "content_sha256": _content_hash(subject, body, recipients, []),
        },
    )
    event.notifications.update(title=subject[:255], message=body)
    return record


def ensure_email_handoff(*, submission, event, actor=None):
    """Return the one optional mail-client draft for a completed event."""
    record = create_system_record(submission=submission, event=event)
    recipients = recipients_for(submission, event.event_type, actor or event.actor)
    handoff, _ = ExternalEmailHandoff.objects.get_or_create(
        event=event,
        defaults={
            "communication": record,
            "submission": submission,
            "action": event.event_type,
            "recipients": recipients,
            "subject": record.subject,
            "body": record.body,
            "created_by": actor or event.actor,
        },
    )
    return handoff


def handoff_data(handoff):
    # Existing drafts may predate per-indicator template support. Enrich the returned
    # draft without mutating immutable correspondence history.
    body = with_flag_details(handoff.body, handoff.event)
    body = with_provider_change_details(body, handoff.submission, handoff.event)
    body = with_penalty_details(body, handoff.submission, handoff.event)
    return {
        "id": handoff.id,
        "event": handoff.event_id,
        "submission": handoff.submission_id,
        "action": handoff.action,
        "recipients": handoff.recipients,
        "subject": handoff.subject,
        "body": body,
        "status": handoff.status,
        "opened_at": handoff.opened_at,
        "deferred_at": handoff.deferred_at,
        "created_at": handoff.created_at,
    }


def finalize_event_communication(*, request, submission, event):
    return create_system_record(submission=submission, event=event)


def queue_automatic_communication(*, submission, event, action, actor, payload=None, template=None, idempotency_key=None):
    """Save a handoff draft for an automatic event; never send external email."""
    return ensure_email_handoff(submission=submission, event=event, actor=actor)
