from datetime import timedelta
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.users.models import User, NCADivision
from apps.submissions.models import ExpectedSubmission, ReportingPeriod, Submission, SubmissionValue
from apps.forms_engine.models import FormTemplate
from apps.providers.models import ProviderProfile
from apps.data_requests.models import DataRequest
from apps.data_requests.serializers import add_event
from apps.data_requests.services import build_manifest, eligible_submissions, generate_artifact
from apps.uploads.models import SubmissionKMZUpload


class Command(BaseCommand):
    help = "Create a Viewer account and simple request workflow examples"

    demo_password = "testpass123"

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true")

    def handle(self, *args, **options):
        division, _ = NCADivision.objects.get_or_create(code="research-and-innovation", defaults={"name": "Research and Innovation"})
        viewer, _ = User.objects.get_or_create(email="viewer@nca.org.gh", defaults={"name": "Ama Mensah", "role": "NCA_VIEWER", "is_active": True})
        viewer.division=division; viewer.grade="Principal Manager"; self._restore_demo_login(viewer)
        admin, _ = User.objects.get_or_create(email="admin@nca.org.gh", defaults={"name": "NCA Administrator", "role": "NCA_ADMIN", "is_active": True, "is_staff": True})
        self._restore_demo_login(admin)
        # Keep every documented local/UAT login stable when this command is
        # rerun independently. Provider and Officer accounts are created by
        # seed_data; only reset them here when they already exist.
        for email in (
            "officer.asante@nca.org.gh",
            "dataentry@vodafone.com.gh",
            "admin@vodafone.com.gh",
        ):
            existing = User.objects.filter(email=email).first()
            if existing:
                self._restore_demo_login(existing)
        if options["reset"]: DataRequest.objects.filter(requester=viewer).delete()
        self._seed_form_review_examples(admin)
        # Local/UAT fixtures only: mirror observed historical provider/form pairs
        # onto the newly published PRD versions so request approval and artifact
        # generation can be exercised. These are deliberately not official
        # ProviderFormAssignment records.
        for old_expected in ExpectedSubmission.objects.exclude(form_template__status="ACTIVE").select_related("form_template", "provider", "period"):
            active_form = FormTemplate.objects.filter(family=old_expected.form_template.family, status="ACTIVE", approval_status="APPROVED").first()
            if not active_form:
                continue
            expected, _ = ExpectedSubmission.objects.get_or_create(
                provider=old_expected.provider, form_template=active_form, period=old_expected.period,
                defaults={"workflow_status": "APPROVED", "due_state": "CLOSED"},
            )
            expected.workflow_status="APPROVED"; expected.due_state="CLOSED"; expected.save(update_fields=["workflow_status", "due_state"])
            submission, _ = Submission.objects.get_or_create(expected=expected, version=1, defaults={"completion_pct": 100, "submitted_by": admin, "submitted_at": timezone.now()})
            for index, field in enumerate(active_form.sections.values_list("fields__id", flat=True).exclude(fields__id=None)[:12], start=1):
                SubmissionValue.objects.get_or_create(submission=submission, field_id=field, defaults={"value": str(index * 100), "value_status": "PROVIDED", "updated_by": admin})
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
                "requesting_division": division.name, "requester_grade_snapshot": viewer.grade, "purpose": "Quarterly sector planning and policy analysis.",
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
        self.stdout.write(self.style.SUCCESS("Local demo logins restored with password: testpass123"))

    def _restore_demo_login(self, user):
        user.set_password(self.demo_password)
        user.failed_login_attempts = 0
        user.locked_until = None
        user.must_change_password = False
        user.save()

    @staticmethod
    def _demo_value(field_type, index=1):
        if field_type == "date": return timezone.localdate().isoformat()
        if field_type in {"boolean", "declaration"}: return "true"
        if field_type in {"number", "currency", "percentage", "formula"}: return str(index)
        if field_type == "multiselect": return "SATELLITE"
        return f"Demo value {index}"

    def _fill_complete_submission(self, submission):
        form = submission.expected.form_template
        for index, field in enumerate(form.sections.values_list("fields__id", flat=True).exclude(fields__id=None), start=1):
            target = form.sections.filter(fields__id=field).values_list("fields__field_type", flat=True).first()
            SubmissionValue.objects.update_or_create(submission=submission, field_id=field, defaults={"value": self._demo_value(target, index), "value_status": "PROVIDED", "updated_by": submission.submitted_by})
        for grid in form.sections.values_list("grids__id", flat=True).exclude(grids__id=None):
            model = form.sections.filter(grids__id=grid).values_list("grids__row_mode", flat=True).first()
            grid_model = form.sections.filter(grids__id=grid).first().grids.get(pk=grid)
            row_ids = [str(row.id) for row in grid_model.fixed_rows.all()] if model == "FIXED" else [f"demo-row-{grid}"]
            for row_number, row_id in enumerate(row_ids, start=1):
                for column in grid_model.columns.all():
                    value = self._demo_value(column.field_type, row_number)
                    if column.column_code == "latitude": value = "5.6037"
                    if column.column_code == "longitude": value = "-0.1870"
                    SubmissionValue.objects.update_or_create(submission=submission, grid=grid_model, grid_row_id=row_id, grid_column=column,
                        defaults={"value": value, "value_status": "PROVIDED", "updated_by": submission.submitted_by})
        # Reconcile declared scalar totals used by grid-total validation rules.
        for rule in form.validation_rules.filter(rule_type="GRID_TOTAL"):
            total = sum(Decimal(item.value) for item in submission.values.filter(grid=rule.grid, grid_column_id=rule.parameters["column_id"]))
            SubmissionValue.objects.update_or_create(submission=submission, field_id=rule.parameters["equals_field"],
                defaults={"value": str(total), "value_status": "PROVIDED", "updated_by": submission.submitted_by})
        for rule in form.validation_rules.filter(rule_type="COMPARISON"):
            SubmissionValue.objects.update_or_create(submission=submission, field_id=rule.parameters["left_field"],
                defaults={"value": "100", "value_status": "PROVIDED", "updated_by": submission.submitted_by})
            SubmissionValue.objects.update_or_create(submission=submission, field_id=rule.parameters["right_field"],
                defaults={"value": "1000", "value_status": "PROVIDED", "updated_by": submission.submitted_by})
        for requirement in form.kmz_requirements.filter(is_required=True):
            SubmissionKMZUpload.objects.get_or_create(submission=submission, requirement=requirement, file_name="demo-topology.kmz",
                defaults={"file_size": 128, "storage_path": f"demo/{submission.id}/topology.kmz", "uploaded_by": submission.submitted_by,
                    "sha256": "0" * 64, "scan_status": "CLEAN", "scan_engine": "demo-fixture", "review_status": "ACCEPTED"})

    def _seed_form_review_examples(self, admin):
        """Local/UAT-only complete and intentionally incomplete examples for every verified PRD form."""
        for form in FormTemplate.objects.filter(mapping_basis="PRD_SECTION_11"):
            period, _ = ReportingPeriod.objects.get_or_create(
                name=f"Demo review period — {form.form_code}",
                defaults={"frequency": form.frequency, "year": timezone.localdate().year,
                    "month": timezone.localdate().month if form.frequency == "MONTHLY" else None,
                    "opens_at": timezone.now() - timedelta(days=1), "due_at": timezone.now() + timedelta(days=30),
                    "status": "ACTIVE", "created_by": admin},
            )
            for state, suffix in (("SUBMITTED", "Complete"), ("UNDER_REVIEW", "Needs correction")):
                provider, _ = ProviderProfile.objects.get_or_create(
                    registered_name=f"Demo {form.form_code} {suffix}",
                    defaults={"sector": form.sector, "category": form.provider_category, "licence_type": form.provider_category,
                        "licence_number": f"DEMO-{form.form_code}-{suffix[:1]}", "primary_email": f"demo-{form.form_code.lower()}-{suffix[:1].lower()}@example.test", "primary_phone": "0000000000"},
                )
                expected, _ = ExpectedSubmission.objects.get_or_create(provider=provider, form_template=form, period=period,
                    defaults={"workflow_status": state, "due_state": "OPEN"})
                expected.workflow_status = state; expected.save(update_fields=["workflow_status"])
                submission, _ = Submission.objects.get_or_create(expected=expected, version=1,
                    defaults={"completion_pct": 100 if state == "SUBMITTED" else 1, "submitted_by": admin, "submitted_at": timezone.now()})
                if state == "SUBMITTED":
                    self._fill_complete_submission(submission)
                elif not submission.values.exists():
                    first = form.sections.values_list("fields__id", flat=True).exclude(fields__id=None).first()
                    if first:
                        SubmissionValue.objects.create(submission=submission, field_id=first, value="Incomplete demo", value_status="PROVIDED", updated_by=admin)
