import hashlib
import json
from datetime import timedelta
from django.conf import settings
from django.db import models
from django.utils import timezone
from apps.audit.services import record_audit, verify_chain
from .models import RECORD_CLASSES, RecordRetentionPolicy, LegalHold, BackupRun, RestoreDrill, OperationalTaskRun


def readiness_report():
    required = {value for value, _ in RECORD_CLASSES}
    approved = set(RecordRetentionPolicy.objects.filter(status="APPROVED", retention_days__isnull=False).values_list("record_class", flat=True))
    active_holds = LegalHold.objects.filter(status="ACTIVE").count()
    backup = BackupRun.objects.filter(status__in=["SUCCEEDED", "VERIFIED"]).order_by("-completed_at").first()
    restore = RestoreDrill.objects.filter(status="PASSED").order_by("-completed_at").first()
    blockers = []
    if required - approved: blockers.append({"code": "RETENTION_POLICIES", "detail": f"Missing approved policies: {', '.join(sorted(required-approved))}"})
    if not getattr(settings, "TARGET_RPO_MINUTES", None): blockers.append({"code": "RPO", "detail": "TARGET_RPO_MINUTES is not configured."})
    if not getattr(settings, "TARGET_RTO_MINUTES", None): blockers.append({"code": "RTO", "detail": "TARGET_RTO_MINUTES is not configured."})
    if not backup: blockers.append({"code": "BACKUP", "detail": "No successful backup evidence."})
    if not restore: blockers.append({"code": "RESTORE", "detail": "No passed restore drill."})
    elif settings.TARGET_RTO_MINUTES and (restore.measured_rto_minutes is None or restore.measured_rto_minutes > settings.TARGET_RTO_MINUTES):
        blockers.append({"code": "RTO_RESULT", "detail": "The latest restore drill does not meet the configured RTO."})
    if backup and (not backup.encrypted or not backup.immutable_copy): blockers.append({"code": "BACKUP_CONTROLS", "detail": "Latest backup evidence is not encrypted and immutable."})
    if not getattr(settings, "RECOVERY_STORAGE_CONFIGURED", False): blockers.append({"code": "RECOVERY_STORAGE", "detail": "Immutable backup/WAL storage is not configured."})
    if not getattr(settings, "IMMUTABLE_AUDIT_STORAGE_REFERENCE", ""): blockers.append({"code": "AUDIT_ANCHOR_STORAGE", "detail": "Immutable audit-anchor storage is not configured."})
    if not getattr(settings, "MAIL_PROVIDER_CONFIGURED", False): blockers.append({"code": "MAIL_PROVIDER", "detail": "Microsoft Graph shared-mailbox delivery is not configured; messages cannot be sent."})
    if not getattr(settings, "APPROVED_PENALTY_REFERENCE", ""): blockers.append({"code": "PENALTY_REFERENCE", "detail": "Approved penalty wording/reference is not configured."})
    if not getattr(settings, "UAT_SIGNOFF_REFERENCE", ""): blockers.append({"code": "UAT_SIGNOFF", "detail": "Business/provider UAT sign-off is outstanding."})
    from apps.forms_engine.models import FormFamily, FormTemplate
    pending_families = list(FormFamily.objects.exclude(frequency_decision_status="APPROVED").values_list("code", flat=True))
    if pending_families: blockers.append({"code": "FREQUENCY_DECISIONS", "detail": "Pending source-owner decisions: " + ", ".join(pending_families)})
    incomplete_forms = list(FormTemplate.objects.filter(status="ACTIVE").filter(
        models.Q(mapping_complete=False) | ~models.Q(approval_status="APPROVED") | models.Q(source_reference__startswith="LEGACY-DEMO")
    ).values_list("form_code", "version"))
    if incomplete_forms: blockers.append({"code": "FORM_MAPPINGS", "detail": "Production form mappings are incomplete or demo-only: " + ", ".join(f"{code} v{version}" for code, version in incomplete_forms)})
    stale_before = timezone.now() - timedelta(hours=26)
    expected_tasks = {"refresh_due_states", "reconcile_compliance", "evaluate_expiry_and_retention", "create_daily_audit_anchor"}
    stale = [name for name in expected_tasks if not OperationalTaskRun.objects.filter(task_name=name, status="SUCCEEDED", completed_at__gte=stale_before).exists()]
    if stale: blockers.append({"code": "STALE_TASKS", "detail": "No recent successful run: " + ", ".join(sorted(stale))})
    if verify_chain(): blockers.append({"code": "AUDIT_CHAIN", "detail": "Audit-chain verification failed."})
    if not getattr(settings, "RETENTION_DISPOSITION_ENABLED", False): blockers.append({"code": "DISPOSITION_DISABLED", "detail": "Automated disposition is disabled."})
    return {"ready": not blockers, "blockers": blockers, "approved_policy_count": len(approved), "required_policy_count": len(required),
        "active_legal_holds": active_holds, "last_backup": backup.completed_at if backup else None, "last_restore": restore.completed_at if restore else None}


def preview_disposition(run):
    policy = run.policy
    if policy.status != "APPROVED" or policy.retention_days is None:
        raise ValueError("An approved policy with a retention duration is required.")
    cutoff = timezone.now() - timedelta(days=policy.retention_days)
    candidates = _retention_candidates(policy.record_class, cutoff)
    holds = list(LegalHold.objects.filter(status="ACTIVE", starts_at__lte=timezone.now()).filter(
        models.Q(ends_at__isnull=True) | models.Q(ends_at__gt=timezone.now())).filter(record_class__in=["", policy.record_class]))
    held = []
    for candidate in candidates:
        for hold in holds:
            target_ids = {str(value) for value in hold.target_ids}
            if target_ids and str(candidate["id"]) not in target_ids: continue
            if hold.provider_id and candidate.get("provider_id") != hold.provider_id: continue
            if hold.reporting_period_id and candidate.get("period_id") != hold.reporting_period_id: continue
            if hold.submission_id and candidate.get("submission_id") != hold.submission_id: continue
            if hold.target_date_from and candidate.get("recorded_at") and candidate["recorded_at"] < hold.target_date_from: continue
            if hold.target_date_to and candidate.get("recorded_at") and candidate["recorded_at"] > hold.target_date_to: continue
            held.append(candidate); break
    eligible = [candidate for candidate in candidates if candidate not in held]
    details = {"record_class": policy.record_class, "cutoff": cutoff.isoformat(), "candidate_count":len(candidates),
        "held_count":len(held), "eligible_count":len(eligible), "sample_candidate_ids":[str(x["id"]) for x in eligible[:100]],
        "execution_enabled": False, "deletion_performed": False}
    run.candidate_count = len(candidates); run.held_count = len(held); run.status = "PREVIEWED"; run.details = details
    run.certificate_sha256 = hashlib.sha256(json.dumps(details, sort_keys=True).encode()).hexdigest(); run.completed_at = timezone.now(); run.save()
    record_audit(user=run.requested_by, action="RETENTION_PREVIEWED", entity_type="DispositionRun", entity_id=run.id, after=details)
    return run


def _retention_candidates(record_class, cutoff):
    """Return non-sensitive candidate coordinates; never deletes records."""
    if record_class == "FORM_VERSION":
        from apps.forms_engine.models import FormTemplate
        return [{"id": row.id,"recorded_at":row.updated_at} for row in FormTemplate.objects.filter(updated_at__lt=cutoff)]
    if record_class == "SUBMISSION":
        from apps.submissions.models import Submission
        return [{"id": row.id, "provider_id":row.expected.provider_id, "period_id":row.expected.period_id, "submission_id":row.id,"recorded_at":row.created_at}
            for row in Submission.objects.filter(created_at__lt=cutoff).select_related("expected")]
    if record_class == "AUDIT":
        from apps.audit.models import AuditEvent
        return [{"id": row.id,"recorded_at":row.timestamp} for row in AuditEvent.objects.filter(timestamp__lt=cutoff)]
    if record_class == "PRIVATE_UPLOAD":
        from apps.uploads.models import SubmissionKMZUpload, SubmissionExcelBackup
        rows=[]
        for prefix, query in (("KMZ",SubmissionKMZUpload.objects.filter(uploaded_at__lt=cutoff)),("EXCEL",SubmissionExcelBackup.objects.filter(uploaded_at__lt=cutoff))):
            rows.extend({"id":f"{prefix}:{row.id}","provider_id":row.submission.expected.provider_id,"period_id":row.submission.expected.period_id,"submission_id":row.submission_id,"recorded_at":row.uploaded_at} for row in query.select_related("submission__expected"))
        return rows
    mappings = {
        "RECEIPT": ("apps.submissions.models", "SubmissionReceipt", "created_at"),
        "EXPORT": ("apps.exports.models", "ExportLog", "generated_at"),
        "EMAIL": ("apps.compliance.models", "EmailLog", "generated_at"),
        "DATA_REQUEST": ("apps.data_requests.models", "DataRequest", "submitted_at"),
        "SUPPORT": ("apps.feedback.models", "SystemIssueTicket", "reported_at"),
    }
    module_name, model_name, date_field = mappings[record_class]
    from importlib import import_module
    model = getattr(import_module(module_name), model_name)
    return [{"id": row.id,"recorded_at":getattr(row,date_field)} for row in model.objects.filter(**{f"{date_field}__lt":cutoff})]
