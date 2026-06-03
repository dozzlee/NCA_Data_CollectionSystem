from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Organization


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ["name", "org_type", "created_at"]
    list_filter = ["org_type"]
    search_fields = ["name"]


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ["email", "name", "role", "organization", "is_active", "mfa_enabled"]
    list_filter = ["role", "is_active", "mfa_enabled"]
    search_fields = ["email", "name"]
    ordering = ["name"]
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal info", {"fields": ("name", "organization")}),
        ("Role & Access", {"fields": ("role", "is_active", "is_staff", "is_superuser", "mfa_enabled")}),
        ("Security", {"fields": ("failed_login_attempts", "locked_until", "last_login_at")}),
        ("Permissions", {"fields": ("groups", "user_permissions")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "name", "organization", "role", "password1", "password2"),
        }),
    )
