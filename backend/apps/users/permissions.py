from rest_framework.permissions import BasePermission


class RolePermission(BasePermission):
    roles = ()

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role in self.roles)


class IsNCAAdmin(RolePermission):
    roles = ("NCA_ADMIN",)


class IsNCAUser(RolePermission):
    roles = ("NCA_ADMIN", "NCA_OFFICER")


class IsProviderUser(RolePermission):
    roles = ("PROVIDER_DATA_ENTRY", "PROVIDER_APPROVER")


class IsProviderDataEntry(RolePermission):
    roles = ("PROVIDER_DATA_ENTRY",)


class IsProviderApprover(RolePermission):
    roles = ("PROVIDER_APPROVER",)


def provider_organization_id(user):
    if not user.is_provider or not user.organization_id:
        return None
    return user.organization_id
