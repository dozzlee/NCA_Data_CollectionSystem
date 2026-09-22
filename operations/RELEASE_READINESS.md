# Publication Readiness Gates

The codebase can be tested locally, but production publication is not approved until the NCA supplies and signs off the external controls below.

## Mandatory external gates

- Production domain, strong secrets, HTTPS origins and trusted managed-ingress CIDRs.
- Confirmed official provider/form assignment register.
- NCA confirmation or replacement of provisional `TOWER-MAIN-ANNUAL` code.
- Immutable backup/private-file destination, credentials and a successful isolated restore meeting approved RPO/RTO.
- Approved retention schedule; automated disposition remains disabled meanwhile.
- Approved penalty wording if it is to appear in correspondence.
- Named NCA, provider, browser, accessibility and spreadsheet/PDF UAT sign-offs.

## Deferred/advisory integrations

- MFA is deferred and is not presented as enforced.
- Microsoft Graph/shared mailbox is provider-neutral architecture only; no messages are marked sent without real delivery evidence.

## Release evidence

Attach migration plan, backend test output, frontend lint/type/build, dependency audits, Compose configuration/build, production security check, smoke test, audit-chain verification, backup/restore report, UAT matrix and the rendered updated PRD.
