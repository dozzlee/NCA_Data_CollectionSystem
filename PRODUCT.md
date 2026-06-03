# Product

## Register

product

## Users

**NCA Officers** (internal, primary): Regulatory staff at the National Communications Authority of Ghana. Work at desktop in an office environment. Their job: monitor submission compliance across 7 form types, review provider data, trigger reminders, request corrections, and export clean data for analysis. They handle many providers and periods simultaneously; they need dense information at a glance, not hand-holding.

**Licensed Providers** (external, secondary): Telecom operators, ISPs, Pay-TV companies, tower operators, and fibre companies submitting mandatory regulatory returns. Data entry staff filling structured web forms section by section; approvers signing off before submission reaches NCA. They use the system periodically (monthly or annually) and need clear progress cues.

## Product Purpose

A secure regulatory data collection portal that replaces email-first submission with a traceable workflow. Providers fill structured manual web forms; NCA tracks completion, reviews submissions, follows up on non-compliance, and exports clean data. The system must answer: who was expected to submit, what was required, what was received, what is missing, who reviewed it, who was reminded, and what can be exported.

MVP: manual web-form entry, draft saving, KMZ upload for fibre forms only, NCA review and correction workflow, compliance dashboard, CSV and PDF exports, email draft generation, audit trail.

## Brand Personality

Authoritative. Precise. Transparent.

The interface carries the gravity of a national regulatory body. It should read as a serious institutional tool — not a startup SaaS dashboard — while being genuinely clear and usable. Data integrity and traceability are the product's core values; the design should signal both.

## Anti-references

- Generic SaaS dashboards (Mixpanel, Amplitude visual style) — too casual, metric-hero layout
- Consumer app design (rounded corners everywhere, playful motion, bright gradients) — wrong register entirely
- Government portal clichés (cluttered, dated, low contrast, table-only layouts) — functional floor, not ceiling
- Notion-style minimal white with gray text — too weightless for regulatory authority

## Design Principles

1. **Data integrity is visible.** Field statuses, submission versions, audit events, and compliance states are always explicit. Never hide or summarize away meaning.
2. **Density earns trust.** NCA Officers are experts; a dense but well-organized layout respects their fluency. Don't thin out data to look "clean."
3. **Status at a glance.** The most important information — workflow status, due state, overdue count — must be readable without interaction.
4. **Correction is a first-class flow.** The review and correction loop is the system's most critical path. It must be frictionless and precise.
5. **The sidebar is the institution.** Deep navy, NCA brand, always present. It anchors authority and orientation across every screen.

## Accessibility & Inclusion

WCAG 2.1 AA minimum. All interactive elements keyboard-navigable. Color is never the only signal for status (always paired with label or icon). All form fields have explicit labels. Reduced motion alternative for all transitions.
