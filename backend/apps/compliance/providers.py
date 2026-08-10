from abc import ABC, abstractmethod

from django.conf import settings


class DeliveryProvider(ABC):
    """Provider-neutral contract. Implementations must be idempotent by EmailLog key."""

    @abstractmethod
    def send(self, email_log):
        raise NotImplementedError


class DisabledDeliveryProvider(DeliveryProvider):
    def send(self, email_log):
        raise RuntimeError("Outbound email delivery is not configured.")


class MicrosoftGraphDeliveryProvider(DeliveryProvider):
    """Deliberate configuration boundary; no tenant calls are enabled by this release."""

    def send(self, email_log):
        raise RuntimeError("Microsoft Graph delivery requires approved tenant configuration.")


def get_delivery_provider():
    if not getattr(settings, "MAIL_PROVIDER_CONFIGURED", False):
        return DisabledDeliveryProvider()
    return MicrosoftGraphDeliveryProvider()
