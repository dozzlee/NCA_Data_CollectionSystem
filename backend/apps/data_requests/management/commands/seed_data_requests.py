from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.users.models import User
from apps.submissions.models import ExpectedSubmission
from apps.providers.models import ProviderProfile
from apps.data_requests.models import DataRequest
from apps.data_requests.serializers import add_event
from apps.data_requests.services import build_manifest, eligible_submissions, generate_artifact


class Command(BaseCommand):
    help = "Create a Viewer account and simple request workflow examples"

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true")

    def handle(self, *args, **options):
        viewer, _ = User.objects.get_or_create(email="viewer@nca.org.gh", defaults={"name": "Ama Mensah", "role": "NCA_VIEWER", "is_active": True})
        viewer.set_password("testpass123"); viewer.save()
        admin, _ = User.objects.get_or_create(email="admin@nca.org.gh", defaults={"name": "NCA Administrator", "role": "NCA_ADMIN", "is_active": True, "is_staff": True})
        admin.set_password("testpass123"); admin.save()
        if options["reset"]: DataRequest.objects.filter(requester=viewer).delete()
        # Build demo scopes only from form/period pairs that genuinely contain
        # NCA-approved submissions. This keeps the Admin approval examples usable.
        approved_pairs = list(
            ExpectedSubmission.objects.filter(
                workflow_status="APPROVED",
                form_template__status="ACTIVE",
            )
            .order_by("form_template_id", "period_id")
            .values_list("form_template_id", "period_id")
            .distinct()[:4]
        )
        forms = list(dict.fromkeys(form_id for form_id, _ in approved_pairs))
        periods = list(dict.fromkeys(period_id for _, period_id in approved_pairs))
        if approved_pairs and not DataRequest.objects.filter(requester=viewer).exists():
            common = {"requester": viewer, "requester_name": viewer.name, "requester_email": viewer.email,
                "requesting_division": "Research and Innovation", "purpose": "Quarterly sector planning and policy analysis.",
                "requested_format": "XLSX", "scope": {"form_template_ids": forms, "period_ids": periods, "all_fields": True,
                    "field_ids": [], "grid_column_ids": [], "provider_scope": "ALL", "sector": "", "provider_category": "", "provider_ids": []}}
            projected = sum(submission.values.count() for submission in eligible_submissions(common["scope"]))
            # Creation order matters because the queue is newest-first. Keep an
            # approvable request at the top for immediate Admin testing.
            examples = (
                ("Coverage planning extract", "CHANGES_REQUESTED"),
                ("Historic rejected extract", "REJECTED"),
                ("Sector performance data", "SUBMITTED"),
                ("Provider trends analysis", "UNDER_REVIEW"),
            )
            for title, state in examples:
                item = DataRequest.objects.create(title=title, status=state, reviewer=admin if state != "SUBMITTED" else None,
                    projected_row_count=projected,
                    expected_delivery_at=timezone.now() + timedelta(days=5) if state == "UNDER_REVIEW" else None,
                    decision_note=("Please narrow this request to one reporting period." if state == "CHANGES_REQUESTED" else
                        "Purpose did not meet the approved disclosure policy." if state == "REJECTED" else ""), **common)
                add_event(item, viewer, "SUBMITTED", "", "SUBMITTED", "Request submitted for review.")
                if state != "SUBMITTED": add_event(item, admin, state, "SUBMITTED", state, item.decision_note or "Review started.", notify=True)
            ready = DataRequest.objects.create(title="Approved subscriber indicators", status="APPROVED", reviewer=admin,
                projected_row_count=projected, approved_at=timezone.now(), expected_delivery_at=timezone.now()+timedelta(days=2),
                requested_format="CSV", **{key:value for key,value in common.items() if key!="requested_format"})
            ready.approval_manifest=build_manifest(ready);ready.save(update_fields=["approval_manifest"])
            artifact=generate_artifact(ready,admin);ready.status="READY";ready.completed_at=timezone.now();ready.projected_row_count=artifact.row_count;ready.save(update_fields=["status","completed_at","projected_row_count"])
            add_event(ready,viewer,"SUBMITTED","","SUBMITTED","Request submitted for review.")
            add_event(ready,admin,"APPROVED","UNDER_REVIEW","APPROVED","Request approved.",notify=True)
            add_event(ready,admin,"FILE_READY","PREPARING","READY","The approved file is ready to download.",notify=True)
        self.stdout.write(self.style.SUCCESS("Viewer demo ready: viewer@nca.org.gh / testpass123"))
