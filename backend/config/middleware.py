from ipaddress import ip_address, ip_network

from django.conf import settings


class TrustedProxyHeaderMiddleware:
    """Ignore forwarded HTTPS claims unless the direct peer is an approved proxy."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.networks = [ip_network(value, strict=False) for value in settings.TRUSTED_PROXY_CIDRS]

    def __call__(self, request):
        forwarded_header = settings.SECURE_PROXY_SSL_HEADER[0] if settings.SECURE_PROXY_SSL_HEADER else None
        if forwarded_header and forwarded_header in request.META:
            try:
                peer = ip_address(request.META.get("REMOTE_ADDR", ""))
                trusted = any(peer in network for network in self.networks)
            except ValueError:
                trusted = False
            if not trusted:
                request.META.pop(forwarded_header, None)
        return self.get_response(request)
