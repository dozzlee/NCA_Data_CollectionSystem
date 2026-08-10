from apps.users.models import User
from .models import Notification


def create_notifications(users, event_type, title, message, target_url, event_key):
    for user in users:
        Notification.objects.get_or_create(
            recipient=user,
            event_key=event_key,
            defaults={
                "event_type": event_type,
                "title": title,
                "message": message,
                "target_url": target_url,
            },
        )


def provider_users(expected, roles=None):
    roles = roles or ("PROVIDER_DATA_ENTRY", "PROVIDER_APPROVER")
    return User.objects.filter(
        organization=expected.provider.organization, role__in=roles, is_active=True
    )


def nca_users():
    return User.objects.filter(role__in=("NCA_ADMIN", "NCA_OFFICER"), is_active=True)
