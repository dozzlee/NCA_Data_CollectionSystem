import hashlib
import shutil
import uuid
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.forms_engine.models import FormTemplate
from apps.providers.models import ProviderProfile
from apps.uploads.scanner import scan_path
from apps.users.models import User
from apps.submissions.models import ProviderWorkbookBaseline
from apps.submissions.monthly_reports import baseline_readiness, suggest_exact_baseline_mappings


class Command(BaseCommand):
    help = "Register a private provider-specific monthly report workbook and exact mapping suggestions."

    def add_arguments(self, parser):
        parser.add_argument("source")
        parser.add_argument("--provider", required=True, help="Provider registered or trade name.")
        parser.add_argument("--form-code", default="MNO-MONTHLY")
        parser.add_argument("--created-by", default="admin@nca.org.gh")
        parser.add_argument("--approve", action="store_true")

    @transaction.atomic
    def handle(self, *args, **options):
        source = Path(options["source"])
        if not source.is_file() or source.suffix.lower() != ".xlsx":
            raise CommandError("The source must be an existing .xlsx workbook.")
        provider = ProviderProfile.objects.filter(registered_name__iexact=options["provider"]).first()
        if not provider:
            provider = ProviderProfile.objects.filter(trade_name__iexact=options["provider"]).first()
        if not provider:
            raise CommandError("Provider was not found.")
        template = FormTemplate.objects.filter(
            form_code=options["form_code"].upper(), status="ACTIVE", approval_status="APPROVED",
        ).order_by("-published_at", "-id").first()
        if not template:
            raise CommandError("An active approved form template was not found.")
        actor = User.objects.filter(email__iexact=options["created_by"], role__in=["NCA_ADMIN", "NCA_OFFICER"]).first()
        if not actor:
            raise CommandError("The NCA creator account was not found.")
        version = (
            ProviderWorkbookBaseline.objects.filter(provider=provider, form_template=template)
            .order_by("-version").values_list("version", flat=True).first() or 0
        ) + 1
        relative = Path("provider-report-baselines") / str(provider.provider_id) / f"{uuid.uuid4().hex}.xlsx"
        destination = Path(settings.PRIVATE_UPLOAD_ROOT) / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        digest = hashlib.sha256(destination.read_bytes()).hexdigest()
        scan = scan_path(destination)
        baseline = ProviderWorkbookBaseline.objects.create(
            provider=provider, form_template=template, version=version,
            file_name=source.name, storage_path=str(relative), file_size=destination.stat().st_size,
            sha256=digest, scan_status=scan["status"], scan_engine=scan["engine"],
            scan_details=scan["details"], created_by=actor,
        )
        if baseline.scan_status == "CLEAN":
            suggest_exact_baseline_mappings(baseline)
        baseline.refresh_from_db()
        self.stdout.write(self.style.SUCCESS(
            f"Baseline {baseline.id} registered for {provider.registered_name}; "
            f"{baseline.mapping_summary.get('total', 0)} mapped, "
            f"{baseline.mapping_summary.get('unmatched_count', 0)} unmatched."
        ))
        if options["approve"]:
            issues = [issue for issue in baseline_readiness(baseline) if "not active" not in issue]
            if baseline.mapping_summary.get("unmatched_count"):
                issues.append("Unmatched indicators remain.")
            if issues:
                raise CommandError("Approval blocked: " + " ".join(issues))
            ProviderWorkbookBaseline.objects.filter(
                provider=provider, form_template=template, status="ACTIVE",
            ).update(status="ARCHIVED")
            baseline.status = "ACTIVE"
            baseline.approved_by = actor
            baseline.approved_at = timezone.now()
            baseline.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
            self.stdout.write(self.style.SUCCESS("Baseline approved and activated."))
