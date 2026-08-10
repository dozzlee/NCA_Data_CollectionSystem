# Incident Runbooks

## Credential compromise

Disable affected accounts/keys, revoke refresh tokens, rotate secrets and provider credentials, inspect the hash-chained audit trail, preserve evidence, and re-enable access only after scope and containment are approved.

## Audit-integrity failure

Stop configuration and disposition actions, preserve database/WAL/object-storage evidence, run `/api/v1/audit/verify/`, compare daily anchors with immutable copies, investigate the first broken event, and treat repair as a controlled recovery—not an in-place audit edit.

## Malware detection

Keep the object quarantined, block review/download, preserve its SHA-256 and scanner output, notify security through an internal support ticket, and remove it only under the approved retention/incident process.

## Email delivery incident

Pause the future provider adapter, leave messages `DRAFT` or `QUEUED`, reconcile provider event IDs against the durable outbox, and never manually mark messages sent.
