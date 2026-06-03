from django.contrib import admin
from .models import ProviderProfile, ProviderContact


class ProviderContactInline(admin.TabularInline):
    model = ProviderContact
    extra = 1
    fields = ["name", "designation", "email", "phone", "is_active"]


@admin.register(ProviderProfile)
class ProviderProfileAdmin(admin.ModelAdmin):
    list_display = ["registered_name", "trade_name", "category", "licence_number", "status", "primary_email"]
    list_filter = ["category", "status"]
    search_fields = ["registered_name", "trade_name", "licence_number", "primary_email"]
    inlines = [ProviderContactInline]
