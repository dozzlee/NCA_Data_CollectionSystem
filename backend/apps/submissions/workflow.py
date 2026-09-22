from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.audit.services import record_audit
from apps.users.models import User

from .models import (
    CorrectionItem,
    ExpectedSubmission,
    Submission,
    SubmissionEvent,
    SubmissionNotification,
    SubmissionValue,
)


def _notification_recipients(submission, recipient_groups):
    query = Q(pk__in=[])
    if "PROVIDER_DATA_ENTRY" in recipient_groups:
        query |= Q(
            role="PROVIDER_DATA_ENTRY",
            organization_id=submission.expected.provider.organization_id,
        )
    if "PROVIDER_APPROVER" in recipient_groups:
        query |= Q(
            role="PROVIDER_APPROVER",
            organization_id=submission.expected.provider.organization_id,
        )
    if "NCA_REVIEWER" in recipient_groups:
        if submission.expected.assigned_officer_id:
            query |= Q(pk=submission.expected.assigned_officer_id)
        else:
            query |= Q(role__in=["NCA_ADMIN", "NCA_OFFICER"])
    return User.objects.filter(query, is_active=True).distinct()


def emit_submission_event(
    *, submission, actor, event_type, message, from_status="", to_status="",
    audience="BOTH", metadata=None, notify=(), title=None,
):
    event = SubmissionEvent.objects.create(
        submission=submission,
        actor=actor,
        event_type=event_type,
        from_status=from_status,
        to_status=to_status,
        message=message,
        audience=audience,
        metadata=metadata or {},
    )
    notifications = [
        SubmissionNotification(
            recipient=recipient,
            submission=submission,
            event=event,
            title=title or message,
            message=message,
        )
        for recipient in _notification_recipients(submission, set(notify))
        if recipient.pk != getattr(actor, "pk", None)
    ]
    if notifications:
        SubmissionNotification.objects.bulk_create(notifications, ignore_conflicts=True)
    return event


def audit_transition(*, request, submission, event_type, message, from_status, to_status, audience="BOTH", notify=(), metadata=None):
    event = emit_submission_event(
        submission=submission,
        actor=request.user,
        event_type=event_type,
        message=message,
        from_status=from_status,
        to_status=to_status,
        audience=audience,
        notify=notify,
        metadata=metadata,
    )
    record_audit(
        user=request.user,
        action=event_type,
        entity_type="Submission",
        entity_id=submission.id,
        before={"workflow_status": from_status},
        after={"workflow_status": to_status, "event_id": event.id, **(metadata or {})},
        ip_address=request.META.get("REMOTE_ADDR"),
    )
    from apps.compliance.communications import finalize_event_communication
    finalize_event_communication(request=request, submission=submission, event=event)
    return event


def lock_submission(submission_id):
    submission = (
        Submission.objects.select_for_update()
        .select_related("expected__provider", "expected__form_template", "expected__period")
        .get(pk=submission_id)
    )
    submission.expected = ExpectedSubmission.objects.select_for_update().get(pk=submission.expected_id)
    return submission


def clone_for_nca_correction(source_submission):
    """Create the editable correction version while keeping the official source immutable."""
    new_submission = Submission.objects.create(
        expected=source_submission.expected,
        version=source_submission.version + 1,
        completion_pct=source_submission.completion_pct,
        supersedes=source_submission,
        regulatory_status="DRAFT",
    )
    SubmissionValue.objects.bulk_create([
        SubmissionValue(
            submission=new_submission,
            field=value.field,
            grid=value.grid,
            grid_row_id=value.grid_row_id,
            grid_column=value.grid_column,
            value=value.value,
            value_status=value.value_status,
            explanation=value.explanation,
            value_source=value.value_source,
            source_reference=value.source_reference,
            updated_by=value.updated_by,
        )
        for value in source_submission.values.all()
    ])
    return new_submission


def mark_matching_corrections_addressed(submission, *, section_code, target_keys):
    items = submission.resolved_correction_items.filter(status="OPEN") | submission.correction_items.filter(
        stage="PROVIDER_APPROVAL", status="OPEN"
    )
    for item in items.distinct():
        matches = (
            item.target_type == "SUBMISSION"
            or (item.target_type == "SECTION" and item.target_id == section_code)
            or item.target_id in target_keys
        )
        if matches:
            item.status = "ADDRESSED"
            item.resolution_submission = submission
            item.save(update_fields=["status", "resolution_submission"])


def complete_submission_revision(submission, actor=None):
    submission.revision += 1
    update_fields = ["revision"]
    if actor is not None:
        submission.last_edited_by = actor
        submission.last_edited_at = timezone.now()
        update_fields.extend(["last_edited_by", "last_edited_at"])
    submission.save(update_fields=update_fields)
    return submission.revision


def mark_notification_read(notification):
    if not notification.is_read:
        notification.is_read = True
        notification.read_at = timezone.now()
        notification.save(update_fields=["is_read", "read_at"])
    return notification
