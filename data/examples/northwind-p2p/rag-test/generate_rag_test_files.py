"""Build the PDF files of the Sheldon RAG test pack (see docs/05-testing/engagement-rag-test-plan.md).

    python data/examples/northwind-p2p/rag-test/generate_rag_test_files.py

Writes two versions of the same file name, so re-uploading tests that a new version replaces the old one:

    rag-test/upload-first/08_vendor_master_change_policy.pdf    approval within 4 business days, one call-back
    rag-test/upload-second/08_vendor_master_change_policy.pdf   approval within 2 business days, two call-backs
"""

from __future__ import annotations

from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table

HERE = Path(__file__).resolve().parent
NAME = "08_vendor_master_change_policy.pdf"


def _policy(version: str, approval_days: int, callbacks: str, freeze_days: int) -> list:
    styles = getSampleStyleSheet()
    h1, h2, body = styles["Title"], styles["Heading2"], styles["BodyText"]
    p = lambda text: Paragraph(text, body)  # noqa: E731
    return [
        Paragraph("Northwind Manufacturing — Vendor Master Change Policy", h1),
        p(f"Policy ID: FIN-MDG-021 | Version {version} | Owner: Daniel Park, MDG Steward | Effective 2026-03-01"),
        Spacer(1, 12),
        Paragraph("1. Purpose", h2),
        p("This policy governs how vendor master records are created and changed in SAP S/4HANA, SAP ECC and "
          "NetSuite. It protects Northwind against payment fraud and duplicate vendors."),
        Paragraph("2. Who may request a change", h2),
        p("Only buyers and category managers may request a vendor master change, through the MDG workflow in "
          "SAP. Requests by email or IT ticket are no longer accepted after 2026-03-01."),
        Paragraph("3. Approval", h2),
        p(f"The MDG steward approves or rejects every change within <b>{approval_days} business days</b> of the "
          "request. Changes to bank details also need approval by the AP manager."),
        Paragraph("4. Bank detail changes", h2),
        p(f"Bank detail changes require <b>{callbacks}</b> to the vendor, using the phone number already on file "
          "(never the number given in the change request). The call-back is recorded in the MDG workflow."),
        p(f"No bank detail change may take effect in the <b>{freeze_days} business days</b> before a scheduled "
          "payment run."),
        PageBreak(),
        Paragraph("5. Duplicate checks", h2),
        p("Before a vendor is created, MDG checks the tax ID, bank account and address against existing records. "
          "A match above 85% similarity blocks the request until the MDG steward reviews it."),
        Paragraph("6. Service levels", h2),
        Table([["Request type", "Target", "Escalation"],
               ["New vendor", "5 business days", "Procurement director"],
               ["Address change", "2 business days", "MDG steward"],
               ["Bank detail change", f"{approval_days} business days", "AP manager"]]),
        Spacer(1, 12),
        Paragraph("7. Monitoring", h2),
        p("Internal Audit reviews a sample of 30 bank detail changes every quarter."),
    ]


def main() -> None:
    versions = {
        "upload-first": ("1.0", 4, "one independent call-back", 5),
        "upload-second": ("2.0", 2, "two independent call-backs by different people", 3),
    }
    for folder, (version, approval_days, callbacks, freeze_days) in versions.items():
        out = HERE / folder
        out.mkdir(exist_ok=True)
        SimpleDocTemplate(str(out / NAME), pagesize=A4, title="Vendor Master Change Policy").build(
            _policy(version, approval_days, callbacks, freeze_days))
        print(f"wrote {out / NAME}")


if __name__ == "__main__":
    main()
