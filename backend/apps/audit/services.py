import hashlib
import hmac
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from .models import AuditEvent, AuditAnchor


@transaction.atomic
def record_audit(*, user, action, entity_type, entity_id, before=None, after=None, ip_address=None):
    previous = AuditEvent.objects.select_for_update().order_by("-id").first()
    previous_hash = previous.event_hash if previous else ""
    return AuditEvent.objects.create(
        user=user, user_email=getattr(user, "email", ""), role=getattr(user, "role", ""),
        organization=getattr(getattr(user, "organization", None), "name", ""), action=action,
        entity_type=entity_type, entity_id=str(entity_id), before_value=before, after_value=after,
        ip_address=ip_address, previous_hash=previous_hash,
    )


def verify_chain():
    previous = ""
    problems = []
    for event in AuditEvent.objects.order_by("id"):
        if event.previous_hash != previous:
            problems.append(event.id)
        elif event.event_hash != event.calculate_hash():
            problems.append(event.id)
        previous = event.event_hash
    return problems


def anchor_day(day=None):
    day = day or timezone.localdate()
    events = AuditEvent.objects.filter(timestamp__date=day).order_by("id")
    first, last = events.first(), events.last()
    root_hash = last.event_hash if last else hashlib.sha256(str(day).encode()).hexdigest()
    key = getattr(settings, "AUDIT_HMAC_KEY", "")
    signature = hmac.new(key.encode(), f"{day}:{root_hash}".encode(), hashlib.sha256).hexdigest() if key else "UNSIGNED"
    return AuditAnchor.objects.update_or_create(anchor_date=day, defaults={
        "first_event_id": first.id if first else None, "last_event_id": last.id if last else None,
        "event_count": events.count(), "root_hash": root_hash, "signature": signature,
    })[0]
