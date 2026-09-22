import calendar
import os
from datetime import timedelta

from celery import shared_task
from django.core.management import call_command
from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from apps.audit.services import anchor_day, record_audit
from apps.compliance.models import EmailTemplate
from apps.data_requests.models import DataRequestArtifact
from apps.submissions.models import ExpectedSubmission, ReminderPolicy, SubmissionEvent, SubmissionOverride
from .models import LegalHold, OperationalTaskRun, RECORD_CLASSES, RecordRetentionPolicy


def _start(name, key):
    run, created = OperationalTaskRun.objects.get_or_create(
        idempotency_key=f"{name}:{key}",
        defaults={"task_name": name, "status": "RUNNING", "details": {"attempts": 1}},
    )
    if not created:
        details = dict(run.details); details["attempts"] = int(details.get("attempts", 1)) + 1
        run.details = details; run.save(update_fields=["details"])
        return run, False
    return run, True


def _finish(run, count=0, details=None):
    run.status = "SUCCEEDED"; run.processed_count = count; run.completed_at = timezone.now()
    if details: run.details = {**run.details, **details}
    run.save(update_fields=["status", "processed_count", "completed_at", "details"])


def _fail(run, exc):
    run.status = "FAILED"; run.completed_at = timezone.now()
    run.details = {**run.details, "error": str(exc)}
    run.save(update_fields=["status", "completed_at", "details"])


def _one_calendar_month_before(value):
    year = value.year if value.month > 1 else value.year - 1
    month = value.month - 1 if value.month > 1 else 12
    return value.replace(year=year, month=month, day=min(value.day, calendar.monthrange(year, month)[1]))


@shared_task(bind=True, max_retries=3)
def evaluate_reminders(self, scheduled_key=None):
    key = scheduled_key or timezone.now().strftime("%Y%m%d%H")
    run, execute = _start("evaluate_reminders", key)
    if not execute: return {"status": "SKIPPED", "run": run.id}
    count = 0
    try:
        for policy in ReminderPolicy.objects.filter(status="APPROVED").select_related("period", "approved_by", "prepared_by"):
            for rule_index, rule in enumerate(policy.rules):
                offset = int(rule.get("offset_days", 0))
                for expected in policy.period.expected_submissions.exclude(workflow_status__in=["SUBMITTED", "UNDER_REVIEW", "RESUBMITTED", "APPROVED", "ARCHIVED"]):
                    if (expected.effective_due_at.date() - timezone.localdate()).days != offset: continue
                    template_type = "OVERDUE" if offset < 0 else "REMINDER"
                    template = EmailTemplate.objects.filter(
                        template_type=template_type,
                        version=rule["template_version"],
                        status="APPROVED",
                    ).first()
                    if not template: continue
                    identity = f"reminder:{policy.id}:{rule_index}:{expected.id}:{timezone.localdate().isoformat()}"
                    if SubmissionEvent.objects.filter(
                        submission__expected=expected, event_type=template_type,
                        metadata__policy_id=policy.id, metadata__rule_index=rule_index,
                        metadata__run_date=timezone.localdate().isoformat(),
                    ).exists(): continue
                    actor = policy.approved_by or policy.prepared_by
                    submission = expected.versions.order_by("-version", "-id").first()
                    if not submission:
                        continue
                    from apps.submissions.workflow import emit_submission_event
                    from apps.compliance.communications import create_system_record, queue_automatic_communication
                    event = emit_submission_event(
                        submission=submission, actor=actor, event_type=template_type,
                        message=f"{template.get_template_type_display()} for {submission.submission_reference}.",
                        from_status=expected.workflow_status, to_status=expected.workflow_status,
                        audience="PROVIDER", notify=["PROVIDER_DATA_ENTRY", "PROVIDER_APPROVER"],
                        metadata={"policy_id": policy.id, "rule_index": rule_index, "offset_days": offset,
                                  "run_date": timezone.localdate().isoformat()},
                    )
                    create_system_record(submission=submission, event=event)
                    queue_automatic_communication(
                        submission=submission, event=event, action=template_type,
                        actor=actor, payload={"next_action": "Review and complete the assigned form in the portal."},
                        template=template, idempotency_key=identity,
                    )
                    count += 1
        # Bi-annual forms have a governed notice exactly one calendar month
        # before their 30 June or 31 December deadline. This does not depend on
        # a manually configured day-offset policy.
        today = timezone.localdate()
        template = EmailTemplate.objects.filter(
            template_type="REMINDER", status="APPROVED",
        ).order_by("-version", "-id").first()
        if template:
            semi_annual = ExpectedSubmission.objects.filter(
                form_template__frequency="SEMI_ANNUAL",
            ).exclude(workflow_status__in=[
                "SUBMITTED", "UNDER_REVIEW", "RESUBMITTED", "APPROVED", "ARCHIVED",
            ]).select_related("period", "form_template", "provider").prefetch_related("versions")
            for expected in semi_annual:
                if _one_calendar_month_before(expected.effective_due_at.date()) != today:
                    continue
                if SubmissionEvent.objects.filter(
                    submission__expected=expected, event_type="REMINDER",
                    metadata__run_date=today.isoformat(),
                ).exists():
                    continue
                submission = expected.versions.order_by("-version", "-id").first()
                if not submission:
                    continue
                from apps.submissions.workflow import emit_submission_event
                from apps.compliance.communications import create_system_record, queue_automatic_communication
                actor = expected.period.created_by
                event = emit_submission_event(
                    submission=submission, actor=actor, event_type="REMINDER",
                    message=f"Bi-annual filing notice for {submission.submission_reference}.",
                    from_status=expected.workflow_status, to_status=expected.workflow_status,
                    audience="PROVIDER", notify=["PROVIDER_DATA_ENTRY", "PROVIDER_APPROVER"],
                    metadata={"automatic_bi_annual": True, "months_before": 1,
                              "run_date": today.isoformat()},
                )
                create_system_record(submission=submission, event=event)
                queue_automatic_communication(
                    submission=submission, event=event, action="REMINDER", actor=actor,
                    payload={"next_action": "Complete the bi-annual form before its deadline."},
                    template=template,
                    idempotency_key=f"bi-annual-reminder:{expected.id}:{today.isoformat()}",
                )
                count += 1
        _finish(run, count, {"external_handoff": "AVAILABLE"})
        return {"status": "SUCCEEDED", "count": count}
    except Exception as exc:
        _fail(run, exc); raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3)
def refresh_due_states(self, scheduled_key=None):
    key = scheduled_key or timezone.localdate().isoformat(); run, execute = _start("refresh_due_states", key)
    if not execute: return {"status": "SKIPPED", "run": run.id}
    try:
        count = 0
        for expected in ExpectedSubmission.objects.all().iterator():
            before = expected.due_state; expected.refresh_due_state(); count += int(before != expected.due_state)
        _finish(run, count); return {"status": "SUCCEEDED", "count": count}
    except Exception as exc: _fail(run, exc); raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3)
def reconcile_compliance(self, scheduled_key=None):
    key = scheduled_key or timezone.localdate().isoformat(); run, execute = _start("reconcile_compliance", key)
    if not execute: return {"status": "SKIPPED", "run": run.id}
    try:
        call_command("flag_missing_data"); _finish(run); return {"status": "SUCCEEDED"}
    except Exception as exc: _fail(run, exc); raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3)
def evaluate_expiry_and_retention(self, scheduled_key=None):
    key = scheduled_key or timezone.localdate().isoformat(); run, execute = _start("evaluate_expiry_and_retention", key)
    if not execute: return {"status": "SKIPPED", "run": run.id}
    try:
        now = timezone.now(); overrides = SubmissionOverride.objects.filter(status="APPROVED", expires_at__lte=now).update(status="EXPIRED")
        artifacts = 0
        all_policies_approved = set(RecordRetentionPolicy.objects.filter(status="APPROVED").values_list("record_class", flat=True)) == {key for key, _ in RECORD_CLASSES}
        deletion_enabled = bool(getattr(settings, "RETENTION_DISPOSITION_ENABLED", False) and all_policies_approved)
        for artifact in DataRequestArtifact.objects.filter(expired_at__isnull=True, expires_at__lte=now).select_related("request"):
            request_item = artifact.request
            held = LegalHold.objects.filter(status="ACTIVE", starts_at__lte=now).filter(Q(ends_at__isnull=True) | Q(ends_at__gt=now)).filter(
                Q(record_class="") | Q(record_class="DATA_REQUEST")
            ).filter(Q(target_ids=[]) | Q(target_ids__contains=[str(request_item.id)])).exists()
            deleted = False
            if deletion_enabled and not held and artifact.private_path and os.path.exists(artifact.private_path):
                os.remove(artifact.private_path); deleted = True
            artifact.expired_at = now; artifact.save(update_fields=["expired_at"])
            artifact.request.status = "EXPIRED"; artifact.request.save(update_fields=["status", "updated_at"])
            record_audit(user=artifact.generated_by, action="DATA_REQUEST_ARTIFACT_EXPIRED", entity_type="DataRequestArtifact", entity_id=artifact.id,
                after={"sha256": artifact.sha256, "file_deleted": deleted, "legal_hold": held})
            artifacts += 1
        approved_policies = RecordRetentionPolicy.objects.filter(status="APPROVED").count()
        _finish(run, overrides + artifacts, {"expired_overrides": overrides, "expired_artifacts": artifacts,
            "approved_retention_policies": approved_policies, "record_deletion_enabled": deletion_enabled})
        return {"status": "SUCCEEDED", "expired": overrides + artifacts}
    except Exception as exc: _fail(run, exc); raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3)
def create_daily_audit_anchor(self, scheduled_key=None):
    day = timezone.localdate() - timedelta(days=1); key = scheduled_key or day.isoformat()
    run, execute = _start("create_daily_audit_anchor", key)
    if not execute: return {"status": "SKIPPED", "run": run.id}
    try:
        anchor = anchor_day(day); _finish(run, anchor.event_count, {"anchor_id": anchor.id, "signed": anchor.signature != "UNSIGNED"})
        return {"status": "SUCCEEDED", "anchor": anchor.id}
    except Exception as exc: _fail(run, exc); raise self.retry(exc=exc)
