# NCA Recovery Runbook

## Launch prerequisites

1. NCA approves RPO and RTO; set `TARGET_RPO_MINUTES` and `TARGET_RTO_MINUTES`.
2. Configure pgBackRest with encrypted full/differential backups and continuous WAL archiving to versioned, immutable S3-compatible storage.
3. Configure a separate encrypted backup of `PRIVATE_UPLOAD_ROOT` and `PRIVATE_EXPORT_ROOT`; retain manifest SHA-256 hashes.
4. Keep `RECOVERY_STORAGE_CONFIGURED=False` until backup, WAL and object-lock evidence has been reviewed.

## Database loss

1. Isolate the failed database and preserve logs; do not initialize a replacement over it.
2. Select a recovery target consistent with the approved RPO.
3. Restore the latest full/differential backup into an isolated network, then replay WAL to the selected target.
4. Run migrations in check mode, relationship checks, row-count reconciliation and audit-chain verification.
5. Record a `BackupRun` and `RestoreDrill` with manifest, recovery point, elapsed time and evidence; an Admin signs off the passed drill.

## Private-file loss

Restore files into a new private root, verify manifest hashes, scan representative files, test authenticated downloads and then atomically change the mounted root. Never restore uploads into the public media tree.

## Complete environment recovery

Restore database, private files, application secrets and ingress configuration into an isolated environment with outbound communications disabled. Validate migrations, counts, foreign keys, audit chains, receipt/artifact hashes and role isolation before approving traffic cutover.

Monthly automated verification and quarterly full exercises must write evidence through `/api/v1/governance/restore-drills/`; absence or failed RPO/RTO remains a launch blocker.
