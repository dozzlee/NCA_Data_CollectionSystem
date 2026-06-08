from rest_framework.permissions import BasePermission

# ─── Role constants ───────────────────────────────────────────────────────────
SYSTEM_ADMIN    = "NCA_ADMIN"
NCA_OFFICER     = "NCA_OFFICER"
DATA_ENTRY      = "PROVIDER_DATA_ENTRY"
APPROVER        = "PROVIDER_APPROVER"

NCA_ROLES       = {SYSTEM_ADMIN, NCA_OFFICER}
PROVIDER_ROLES  = {DATA_ENTRY, APPROVER}


class IsNCAUser(BasePermission):
    """
    System Administrator or NCA Officer.
    NCA Officers can: view submissions/dashboards, review (approve/reject/correction),
    generate email drafts, add notes, export, view history.
    """
    message = "Access restricted to NCA staff."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated
                    and request.user.role in NCA_ROLES)


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


class IsProviderUser(BasePermission):
    """Any provider role (Data Entry or Approver)."""
    message = "Access restricted to provider users."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated
                    and request.user.role in PROVIDER_ROLES)


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
    System Administrator can write; any authenticated user can read.
    Used for form templates and configuration resources that providers need
    to read (to render their forms) but only System Admin should modify.
    """
    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        return request.user.role == SYSTEM_ADMIN
