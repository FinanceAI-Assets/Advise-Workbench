# Vendor Master Change Control Standard (Test Practice)

## Purpose
This practice defines mandatory controls for vendor master changes, with emphasis on bank account updates, approval discipline, and cycle-time governance.

## Scope
Applies to all create and change requests for vendor master records, including name, tax, banking, payment terms, and address attributes.

## Standard workflow
1. Request initiation: Procurement raises an IT ticket with business justification.
2. Data validation: Master Data team verifies request completeness and supporting evidence.
3. Bank detail verification: Validate bank details against supplier-provided bank letter and registered supplier record.
4. Finance approval: Finance approves before release to payment processing.
5. System release: Approved change is migrated to production and logged.

## Control requirements
- Dual control is required for bank detail changes.
- Maker-checker separation is required: requester and approver cannot be the same person.
- Every change must have a traceable ticket ID and approval timestamp.
- Emergency changes require post-facto review within 1 business day.

## SLA and performance
- Target cycle time for standard vendor master changes: 5 business days.
- Escalation threshold: any request older than 7 business days.
- Legacy baseline observed in workshops: 9 days average turnaround for vendor master changes.

## Evidence pack for each change
- IT ticket reference
- Supplier bank letter or equivalent document
- Validation checklist completed by Master Data
- Finance approval evidence
- Release confirmation log

## Common failure modes and mitigations
- Missing bank evidence: reject request and return to requester.
- No finance approval: block release to payment.
- Incomplete ticket fields: auto-route back for completion.

## Alignment notes for engagement testing
This test practice intentionally includes terms that should align with discovery workshop notes:
- IT ticket
- 9 days average turnaround
- procurement raises ticket
- master data validates bank details
- finance approves before release

Use this practice to test that engagement-scoped retrieval works as expected:
- If this practice is linked to the engagement, Sheldon can use it with engagement documents.
- If no practice is linked, Sheldon should answer only from engagement documents.
