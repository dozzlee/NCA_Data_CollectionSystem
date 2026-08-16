from django.db.models import Prefetch, Q

from .models import ExpectedSubmission, Submission


DATA_ENTRY_EDIT_STATES = {"NOT_STARTED", "DRAFT", "PROVIDER_CHANGES_REQUESTED"}
APPROVER_EDIT_STATES = {"PENDING_APPROVAL", "PROVIDER_RESUBMITTED", "CORRECTION_REQUESTED"}
APPROVER_QUEUE_STATES = {"PENDING_APPROVAL", "PROVIDER_RESUBMITTED", "CORRECTION_REQUESTED"}
OFFICIAL_STATES = {"SUBMITTED", "UNDER_REVIEW", "RESUBMITTED", "APPROVED", "REJECTED", "ARCHIVED"}


def provider_can_edit(user, submission):
    if not user or not user.is_authenticated or not user.is_provider:
        return False
    if user.organization_id != submission.expected.provider.organization_id:
        return False
    state = submission.expected.workflow_status
    if user.role == "PROVIDER_DATA_ENTRY":
        return state in DATA_ENTRY_EDIT_STATES
    if user.role == "PROVIDER_APPROVER":
        return state in APPROVER_EDIT_STATES
    return False


def permitted_actions(user, expected, latest=None):
    state = expected.workflow_status
    actions = ["VIEW"]
    if user.role == "PROVIDER_DATA_ENTRY":
        if latest and state in DATA_ENTRY_EDIT_STATES:
            actions.extend(["EDIT", "UPLOAD", "SUBMIT_FOR_APPROVAL"])
        if state == "NOT_STARTED":
            actions.append("START")
    elif user.role == "PROVIDER_APPROVER":
        if latest and state in APPROVER_EDIT_STATES:
            actions.extend(["EDIT", "UPLOAD", "REQUEST_CORRECTION", "OFFICIAL_SUBMIT"])
    if latest and hasattr(latest, "receipt"):
        actions.append("DOWNLOAD_RECEIPT")
    return actions


def workspace_queryset(user):
    versions = (
        Submission.objects.select_related("last_edited_by", "receipt", "provider_approval__approver")
        .prefetch_related("correction_items", "resolved_correction_items")
        .order_by("-version")
    )
    return (
        ExpectedSubmission.objects.filter(provider__organization_id=user.organization_id)
        .select_related("provider", "form_template", "period", "assigned_officer")
        .prefetch_related(
            Prefetch("versions", queryset=versions, to_attr="workspace_versions"),
            "deadline_changes",
        )
    )


def apply_workspace_queue(queryset, user, queue):
    queue = queue or "action_required"
    if queue == "action_required":
        states = (
            {"NOT_STARTED", "DRAFT", "PROVIDER_CHANGES_REQUESTED"}
            if user.role == "PROVIDER_DATA_ENTRY"
            else APPROVER_QUEUE_STATES
        )
        return queryset.filter(workflow_status__in=states)
    if queue == "drafts":
        return queryset.filter(workflow_status__in=["NOT_STARTED", "DRAFT"])
    if queue == "awaiting_data_entry":
        return queryset.filter(workflow_status__in=["NOT_STARTED", "DRAFT", "PROVIDER_CHANGES_REQUESTED"])
    if queue == "awaiting_approver":
        return queryset.filter(workflow_status__in=["PENDING_APPROVAL", "PROVIDER_RESUBMITTED"])
    if queue == "nca_corrections":
        return queryset.filter(workflow_status="CORRECTION_REQUESTED")
    if queue == "returned":
        return queryset.filter(workflow_status="PROVIDER_CHANGES_REQUESTED")
    if queue == "overdue":
        return queryset.filter(due_state="OVERDUE").exclude(workflow_status__in=OFFICIAL_STATES)
    if queue == "recent":
        return queryset.filter(workflow_status__in=OFFICIAL_STATES)
    if queue == "history":
        return queryset.filter(workflow_status__in=OFFICIAL_STATES)
    if queue == "all":
        return queryset
    return queryset.none()


def filter_workspace_queryset(queryset, params):
    search = (params.get("search") or "").strip()
    if search:
        queryset = queryset.filter(
            Q(form_template__form_code__icontains=search)
            | Q(form_template__name__icontains=search)
            | Q(period__name__icontains=search)
        )
    filters = {
        "form": "form_template_id",
        "period": "period_id",
        "status": "workflow_status",
        "deadline": "due_state",
    }
    for parameter, lookup in filters.items():
        value = params.get(parameter)
        if value:
            queryset = queryset.filter(**{lookup: value})
    correction_state = params.get("correction_state")
    if correction_state == "open":
        queryset = queryset.filter(
            Q(versions__correction_items__status="OPEN")
            | Q(versions__resolved_correction_items__status="OPEN")
        ).distinct()
    elif correction_state == "none":
        queryset = queryset.exclude(
            Q(versions__correction_items__status="OPEN")
            | Q(versions__resolved_correction_items__status="OPEN")
        )
    return queryset


def summary_for_user(user):
    queryset = ExpectedSubmission.objects.filter(provider__organization_id=user.organization_id)
    if user.role == "PROVIDER_DATA_ENTRY":
        action_states = ["NOT_STARTED", "DRAFT", "PROVIDER_CHANGES_REQUESTED"]
    else:
        action_states = list(APPROVER_QUEUE_STATES)
    return {
        "role": user.role,
        "action_required": queryset.filter(workflow_status__in=action_states).count(),
        "drafts": queryset.filter(workflow_status__in=["NOT_STARTED", "DRAFT"]).count(),
        "awaiting_data_entry": queryset.filter(
            workflow_status__in=["NOT_STARTED", "DRAFT", "PROVIDER_CHANGES_REQUESTED"],
        ).count(),
        "due_soon": queryset.filter(due_state__in=["DUE_SOON", "DUE_TODAY"]).exclude(workflow_status__in=OFFICIAL_STATES).count(),
        "overdue": queryset.filter(due_state="OVERDUE").exclude(workflow_status__in=OFFICIAL_STATES).count(),
        "awaiting_approver": queryset.filter(workflow_status__in=["PENDING_APPROVAL", "PROVIDER_RESUBMITTED"]).count(),
        "nca_corrections": queryset.filter(workflow_status="CORRECTION_REQUESTED").count(),
        "returned_to_data_entry": queryset.filter(workflow_status="PROVIDER_CHANGES_REQUESTED").count(),
        "recently_submitted": queryset.filter(workflow_status__in=OFFICIAL_STATES).count(),
    }
