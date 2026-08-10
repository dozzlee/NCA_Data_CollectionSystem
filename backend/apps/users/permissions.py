from rest_framework.permissions import BasePermission

# ─── Role constants ───────────────────────────────────────────────────────────
SYSTEM_ADMIN    = "NCA_ADMIN"
NCA_OFFICER     = "NCA_OFFICER"
NCA_VIEWER      = "NCA_VIEWER"
DATA_ENTRY      = "PROVIDER_DATA_ENTRY"
APPROVER        = "PROVIDER_APPROVER"

NCA_ROLES       = {SYSTEM_ADMIN, NCA_OFFICER, NCA_VIEWER}
NCA_OPERATIONS_ROLES = {SYSTEM_ADMIN, NCA_OFFICER}
NCA_EDITOR_ROLES = {SYSTEM_ADMIN, NCA_OFFICER}
PROVIDER_ROLES  = {DATA_ENTRY, APPROVER}


class IsNCAUser(BasePermission):
    """
    NCA operational users. The legacy NCA_VIEWER role is now a governed
    data requester and must not have raw operational access.
    """
    message = "Access restricted to NCA staff."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated
                    and request.user.role in NCA_OPERATIONS_ROLES)


class IsDataRequester(BasePermission):
    """Repurposed NCA_VIEWER accounts that can use the request portal."""
    message = "Access restricted to NCA data requester accounts."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated
                    and request.user.role == NCA_VIEWER)


class IsSystemAdmin(BasePermission):
    """
    System Administrator only.
    Can: manage users, provider profiles, form templates, periods, KMZ rules,
    email templates, system configuration, audit access.
    Admin actions are audited. Does NOT grant provider submission authority.
    """
    message = "Access restricted to System Administrators."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated
                    and request.user.role == SYSTEM_ADMIN)


# Alias used in legacy code — same as IsSystemAdmin
IsNCAAdmin = IsSystemAdmin


class IsNCAEditor(BasePermission):
    """NCA administrators and officers; excludes view-only users."""
    message = "This action requires NCA editing privileges."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role in NCA_EDITOR_ROLES
        )


class IsProviderUser(BasePermission):
    """Any provider role (Data Entry or Approver)."""
    message = "Access restricted to provider users."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated
                    and request.user.role in PROVIDER_ROLES)


class IsNCAOperationsOrProvider(BasePermission):
    """Operational NCA users or provider users; excludes data requesters."""
    message = "Access restricted to operational or provider accounts."

    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated
            and request.user.role in (NCA_OPERATIONS_ROLES | PROVIDER_ROLES)
        )


class IsProviderApprover(BasePermission):
    """
    Provider Approver only.
    Can: review drafts, return to data entry, officially submit to NCA,
    download receipt/PDF, view own organisation's submission history.
    Cannot perform NCA review, compliance follow-up, or internal exports.
    """
    message = "Only Provider Approvers can perform this action."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated
                    and request.user.role == APPROVER)


class IsProviderDataEntry(BasePermission):
    """
    Provider Data Entry User only.
    Can: view assigned forms, enter values, mark field status,
    upload KMZ where required, save drafts, submit to approver.
    Cannot officially submit to NCA.
    """
    message = "Only Provider Data Entry users can perform this action."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated
                    and request.user.role == DATA_ENTRY)


class IsNCAOrReadOnly(BasePermission):
    """
    System Administrator can write; operational NCA and provider users can
    read. Data requesters use the sanitized catalog endpoint instead.
    """
    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return request.user.role in (NCA_OPERATIONS_ROLES | PROVIDER_ROLES)
        return request.user.role == SYSTEM_ADMIN
