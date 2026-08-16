import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.audit.services import record_audit, verify_chain
from apps.compliance.models import EmailLog, TransactionalOutbox
from apps.data_requests.models import DataRequest, DataRequestArtifact, DataRequestEvent
from apps.forms_engine.models import FormFamily, FormTemplate, FormWorkbookImport
from apps.providers.models import ProviderFormAssignment, ProviderProfile
from apps.submissions.models import (
    CorrectionItem,
    ExpectedSubmission,
    PeriodFormAssignment,
    ProviderApprovalDecision,
    ProviderEditBatch,
    ProviderEditItem,
    Submission,
    SubmissionEvent,
    SubmissionNotification,
    SubmissionReceipt,
)
from apps.uploads.models import SubmissionExcelBackup, SubmissionKMZUpload
from apps.users.models import User


CONFIRMATION = "PURGE-LOCAL-MNO-AND-UNOWNED-PROVIDERS"
MNO_ONLY_CONFIRMATION = "PURGE-LOCAL-MNO-FORMS"
PROVIDER_ROLES = ("PROVIDER_DATA_ENTRY", "PROVIDER_APPROVER")


def _resolved_private_path(root, stored_path):
    if not stored_path:
        return None
    root_path = Path(root).resolve()
    candidate = Path(stored_path)
    resolved = (candidate if candidate.is_absolute() else root_path / candidate).resolve()
    if resolved == root_path or root_path not in resolved.parents:
        raise CommandError(f"Unsafe private path outside {root_path}: {stored_path}")
    return resolved


def _target_state(*, include_unowned_providers=True):
    retained_provider_ids = ProviderProfile.objects.filter(
        organization__user__role__in=PROVIDER_ROLES,
    ).values_list("id", flat=True).distinct()
    providers = (
        ProviderProfile.objects.exclude(id__in=retained_provider_ids).order_by("id")
        if include_unowned_providers else ProviderProfile.objects.none()
    )
    families = FormFamily.objects.filter(code__iexact="MNO-MONTHLY").order_by("id")
    templates = FormTemplate.objects.filter(
        Q(family__in=families) | Q(form_code__iexact="MNO-MONTHLY"),
    ).distinct().order_by("id")
    imports = FormWorkbookImport.objects.filter(form_code__iexact="MNO-MONTHLY").order_by("id")
    expected = ExpectedSubmission.objects.filter(
        Q(provider__in=providers) | Q(form_template__in=templates),
    ).distinct().order_by("id")
    submissions = Submission.objects.filter(expected__in=expected).order_by("id")
    submission_ids = set(submissions.values_list("id", flat=True))
    affected_requests = []
    for request in DataRequest.objects.exclude(approval_manifest__isnull=True).order_by("submitted_at"):
        manifest_ids = set((request.approval_manifest or {}).get("submission_ids", []))
        if manifest_ids & submission_ids and DataRequestArtifact.objects.filter(request=request).exists():
            affected_requests.append(request)
    return {
        "providers": providers,
        "families": families,
        "templates": templates,
        "imports": imports,
        "expected": expected,
        "submissions": submissions,
        "affected_requests": affected_requests,
    }


def _private_files(state):
    submission_ids = list(state["submissions"].values_list("id", flat=True))
    paths = {}

    def add(root, stored_path, sha256=""):
        resolved = _resolved_private_path(root, stored_path)
        if resolved:
            paths[str(resolved)] = sha256 or paths.get(str(resolved), "")

    for item in state["imports"]:
        add(settings.PRIVATE_UPLOAD_ROOT, item.storage_path, item.sha256)
    for item in SubmissionKMZUpload.objects.filter(submission_id__in=submission_ids):
        add(settings.PRIVATE_UPLOAD_ROOT, item.storage_path, item.sha256)
    for item in SubmissionExcelBackup.objects.filter(submission_id__in=submission_ids):
        add(settings.PRIVATE_UPLOAD_ROOT, item.storage_path, item.sha256)
    for item in SubmissionReceipt.objects.filter(submission_id__in=submission_ids):
        add(settings.PRIVATE_EXPORT_ROOT, item.private_path, item.sha256)
    for request in state["affected_requests"]:
        artifact = getattr(request, "artifact", None)
        if artifact:
            add(settings.PRIVATE_EXPORT_ROOT, artifact.private_path, artifact.sha256)
    return paths


def _summary(state, paths, *, scope="MNO_AND_UNOWNED_PROVIDERS"):
    submission_ids = list(state["submissions"].values_list("id", flat=True))
    expected_ids = list(state["expected"].values_list("id", flat=True))
    template_ids = list(state["templates"].values_list("id", flat=True))
    provider_ids = list(state["providers"].values_list("id", flat=True))
    return {
        "mode": "dry-run",
        "scope": scope,
        "mno_family_ids": list(state["families"].values_list("id", flat=True)),
        "mno_template_ids": template_ids,
        "mno_workbook_import_ids": list(state["imports"].values_list("id", flat=True)),
        "provider_ids": provider_ids,
        "provider_names": list(state["providers"].values_list("registered_name", flat=True)),
        "expected_submission_ids": expected_ids,
        "submission_ids": submission_ids,
        "counts": {
            "providers": len(provider_ids),
            "form_families": state["families"].count(),
            "form_templates": len(template_ids),
            "workbook_imports": state["imports"].count(),
            "expected_submissions": len(expected_ids),
            "submissions": len(submission_ids),
            "submission_events": SubmissionEvent.objects.filter(submission_id__in=submission_ids).count(),
            "submission_notifications": SubmissionNotification.objects.filter(submission_id__in=submission_ids).count(),
            "receipts": SubmissionReceipt.objects.filter(submission_id__in=submission_ids).count(),
            "private_files": len(paths),
            "data_request_artifacts_to_expire": len(state["affected_requests"]),
        },
        "affected_data_request_ids": [str(item.id) for item in state["affected_requests"]],
        "private_files": [
            {"path": path, "sha256": digest, "exists": Path(path).is_file()}
            for path, digest in sorted(paths.items())
        ],
    }


def _target_fingerprint(state, paths):
    """Stable target identity used to fail closed if the cleanup set changes."""
    return {
        "providers": list(state["providers"].values_list("id", flat=True)),
        "families": list(state["families"].values_list("id", flat=True)),
        "templates": list(state["templates"].values_list("id", flat=True)),
        "imports": list(state["imports"].values_list("id", flat=True)),
        "expected": list(state["expected"].values_list("id", flat=True)),
        "submissions": list(state["submissions"].values_list("id", flat=True)),
        "affected_requests": [str(item.id) for item in state["affected_requests"]],
        "private_files": sorted(paths),
    }


def _delete_submission_graph(submissions):
    submission_ids = list(submissions.values_list("id", flat=True))
    if not submission_ids:
        return
    SubmissionNotification.objects.filter(submission_id__in=submission_ids).delete()
    SubmissionEvent.objects.filter(submission_id__in=submission_ids).delete()
    SubmissionReceipt.objects.filter(submission_id__in=submission_ids).delete()
    ProviderEditItem.objects.filter(batch__submission_id__in=submission_ids).delete()
    ProviderEditBatch.objects.filter(submission_id__in=submission_ids).delete()
    ProviderApprovalDecision.objects.filter(submission_id__in=submission_ids).delete()
    CorrectionItem.objects.filter(
        Q(source_submission_id__in=submission_ids) | Q(resolution_submission_id__in=submission_ids),
    ).delete()
    TransactionalOutbox.objects.filter(
        aggregate_type="Submission", aggregate_id__in=[str(value) for value in submission_ids],
    ).delete()
    for submission_id in submissions.order_by("expected_id", "-version", "-id").values_list("id", flat=True):
        Submission.objects.filter(id=submission_id).delete()


def _delete_expected(expected):
    expected_ids = list(expected.values_list("id", flat=True))
    for expected_id in expected.filter(replacement_id__isnull=False).values_list("id", flat=True):
        ExpectedSubmission.objects.filter(id=expected_id).delete()
    for expected_id in expected_ids:
        ExpectedSubmission.objects.filter(id=expected_id).delete()


class Command(BaseCommand):
    help = "Dry-run or permanently purge local MNO forms and providers without provider-user accounts."

    def add_arguments(self, parser):
        parser.add_argument(
            "--mno-only", action="store_true",
            help="Purge only MNO-MONTHLY records; never target provider profiles.",
        )
        parser.add_argument("--commit", action="store_true", help="Apply the permanent local purge.")
        parser.add_argument("--confirm", default="", help=f"Required with --commit: {CONFIRMATION}")
        parser.add_argument("--actor-email", default="", help="Active NCA Admin recorded in the cleanup audit event.")

    def handle(self, *args, **options):
        commit = options["commit"]
        mno_only = options["mno_only"]
        confirmation = MNO_ONLY_CONFIRMATION if mno_only else CONFIRMATION
        scope = "MNO_ONLY" if mno_only else "MNO_AND_UNOWNED_PROVIDERS"
        if commit:
            if not settings.DEBUG or settings.DATABASES["default"]["ENGINE"] != "django.db.backends.sqlite3":
                raise CommandError("Committed cleanup is restricted to the local DEBUG SQLite database.")
            if options["confirm"] != confirmation:
                raise CommandError(f"Pass --confirm {confirmation} to apply the purge.")
            actor = User.objects.filter(
                email__iexact=options["actor_email"], role="NCA_ADMIN", is_active=True,
            ).first()
            if not actor:
                raise CommandError("--actor-email must identify an active NCA Admin.")
        else:
            actor = None

        audit_problems = verify_chain()
        if audit_problems:
            raise CommandError(f"Audit chain verification failed at event IDs: {audit_problems[:10]}")
        state = _target_state(include_unowned_providers=not mno_only)
        paths = _private_files(state)
        initial_fingerprint = _target_fingerprint(state, paths)
        summary = _summary(state, paths, scope=scope)
        if not commit:
            self.stdout.write(json.dumps(summary, indent=2, default=str))
            return

        now = timezone.now()
        with transaction.atomic():
            # Re-resolve targets under the write transaction and fail closed if they changed.
            state = _target_state(include_unowned_providers=not mno_only)
            paths = _private_files(state)
            if _target_fingerprint(state, paths) != initial_fingerprint:
                raise CommandError("Cleanup targets changed after the dry-run. No records were deleted.")
            summary = _summary(state, paths, scope=scope)
            expected_ids = list(state["expected"].values_list("id", flat=True))
            submission_ids = list(state["submissions"].values_list("id", flat=True))
            provider_ids = list(state["providers"].values_list("id", flat=True))
            template_ids = list(state["templates"].values_list("id", flat=True))
            family_ids = list(state["families"].values_list("id", flat=True))

            for request in state["affected_requests"]:
                artifact = request.artifact
                if not artifact.expired_at:
                    artifact.expired_at = now
                    artifact.save(update_fields=["expired_at"])
                previous_status = request.status
                request.status = "EXPIRED"
                request.save(update_fields=["status", "updated_at"])
                DataRequestEvent.objects.create(
                    request=request, actor=actor, actor_name=actor.name, actor_email=actor.email,
                    event_type="SOURCE_DATA_PURGED", from_status=previous_status, to_status="EXPIRED",
                    message="The released artifact expired because its local source submissions were permanently purged.",
                    metadata={"purged_submission_ids": sorted(set(request.approval_manifest.get("submission_ids", [])) & set(submission_ids))},
                )

            EmailLog.objects.filter(
                Q(provider_id__in=provider_ids) | Q(expected_submission_id__in=expected_ids),
            ).delete()
            _delete_submission_graph(state["submissions"])
            _delete_expected(state["expected"])
            PeriodFormAssignment.objects.filter(
                Q(provider_id__in=provider_ids) | Q(form_template_id__in=template_ids),
            ).delete()
            ProviderFormAssignment.objects.filter(
                Q(provider_id__in=provider_ids) | Q(form_family_id__in=family_ids),
            ).delete()
            state["imports"].delete()
            state["templates"].delete()
            state["families"].delete()
            state["providers"].delete()

            summary["mode"] = "committed"
            summary["committed_at"] = now.isoformat()
            record_audit(
                user=actor,
                action="LOCAL_MNO_FORM_PURGE" if mno_only else "LOCAL_MNO_PROVIDER_PURGE",
                entity_type="LocalDataCleanup",
                entity_id=now.strftime("%Y%m%d%H%M%S"),
                after={
                    "mno_family_ids": family_ids,
                    "mno_template_ids": template_ids,
                    "provider_ids": provider_ids,
                    "expected_submission_ids": expected_ids,
                    "submission_ids": submission_ids,
                    "counts": summary["counts"],
                    "file_hashes": sorted({digest for digest in paths.values() if digest}),
                    "affected_data_request_ids": summary["affected_data_request_ids"],
                },
            )

        deleted_files = []
        missing_files = []
        for path in sorted(paths):
            item = Path(path)
            if item.is_file():
                item.unlink()
                deleted_files.append(path)
            else:
                missing_files.append(path)
        summary["deleted_files"] = deleted_files
        summary["missing_files"] = missing_files
        if verify_chain():
            raise CommandError("The audit chain failed verification after cleanup.")
        self.stdout.write(json.dumps(summary, indent=2, default=str))
