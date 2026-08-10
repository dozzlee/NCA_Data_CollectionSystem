import os
from datetime import timedelta

from celery import shared_task
from django.core.management import call_command
from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from apps.audit.services import anchor_day, record_audit
from apps.compliance.emailing import render_template
from apps.compliance.models import EmailLog, EmailTemplate, TransactionalOutbox
from apps.data_requests.models import DataRequestArtifact
from apps.submissions.models import ExpectedSubmission, ReminderPolicy, SubmissionOverride
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
                    if EmailLog.objects.filter(idempotency_key=identity).exists(): continue
                    subject, body, _ = render_template(template, expected)
                    contacts = expected.provider.contacts.filter(is_active=True, notify_on_reminder=True)
                    recipient_roles = [role.strip() for role in rule.get("recipient_roles", []) if role.strip()]
                    if recipient_roles:
                        contacts = contacts.filter(notification_role__in=recipient_roles)
                    recipients = [{"email": c.email, "name": c.name} for c in contacts] or [{"email": expected.provider.primary_email, "name": expected.provider.registered_name}]
                    actor = policy.approved_by or policy.prepared_by
                    email = EmailLog.objects.create(template=template, subject=subject, body=body, recipients=recipients,
                        provider=expected.provider, expected_submission=expected, period=expected.period,
                        generated_by=actor, status="QUEUED", queued_at=timezone.now(), idempotency_key=identity)
                    TransactionalOutbox.objects.create(topic="email.queued", aggregate_type="EmailLog", aggregate_id=str(email.id),
                        payload={"email_id": email.id, "provider_key": "UNCONFIGURED"}, idempotency_key=identity)
                    count += 1
        _finish(run, count, {"sending_enabled": False})
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
