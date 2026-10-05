"""Synthetic benefit PDFs for tests. Generated at test time into a tmp dir, never committed.

The fake plan is H9999-001 from the fake carrier "Example Health Plan". The layout mimics a
Summary of Benefits: a title line, then a ruled cost-sharing table spread over two pages, so
page numbers matter. EOC and ANOC variants change only the title.
"""

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen.canvas import Canvas

from plan_diff.models import DocumentType, FieldName

TITLES: dict[DocumentType, str] = {
    DocumentType.SB: "Summary of Benefits",
    DocumentType.EOC: "Evidence of Coverage",
    DocumentType.ANOC: "Annual Notice of Change",
}

LABELS: dict[FieldName, str] = {
    FieldName.MONTHLY_PREMIUM: "Monthly plan premium",
    FieldName.MEDICAL_DEDUCTIBLE: "Medical deductible",
    FieldName.MOOP_IN_NETWORK: "Maximum out-of-pocket (in network)",
    FieldName.PCP_COPAY: "Primary care provider visit",
    FieldName.SPECIALIST_COPAY: "Specialist visit",
    FieldName.EMERGENCY_ROOM: "Emergency room",
    FieldName.URGENT_CARE: "Urgent care",
    FieldName.INPATIENT_STAY: "Inpatient hospital stay",
    FieldName.OUTPATIENT_SURGERY: "Outpatient surgery",
    FieldName.DRUG_DEDUCTIBLE: "Prescription drug deductible",
    FieldName.DRUG_TIER_1: "Tier 1 preferred generic drugs",
    FieldName.DRUG_TIER_2: "Tier 2 generic drugs",
    FieldName.DRUG_TIER_3: "Tier 3 preferred brand drugs",
    FieldName.DENTAL_ALLOWANCE: "Dental allowance",
    FieldName.OTC_ALLOWANCE: "Over-the-counter (OTC) allowance",
}

DEFAULT_VALUES: dict[FieldName, str] = {
    FieldName.MONTHLY_PREMIUM: "$0 per month",
    FieldName.MEDICAL_DEDUCTIBLE: "$0 per year",
    FieldName.MOOP_IN_NETWORK: "$3,400 per year",
    FieldName.PCP_COPAY: "$0 per visit",
    FieldName.SPECIALIST_COPAY: "$45 per visit",
    FieldName.EMERGENCY_ROOM: "$125 per visit",
    FieldName.URGENT_CARE: "$40 per visit",
    FieldName.INPATIENT_STAY: "$295 per day, days 1 to 5",
    FieldName.OUTPATIENT_SURGERY: "20% coinsurance",
    FieldName.DRUG_DEDUCTIBLE: "$0 per year",
    FieldName.DRUG_TIER_1: "$0 per prescription",
    FieldName.DRUG_TIER_2: "$5 per prescription",
    FieldName.DRUG_TIER_3: "$47 per prescription",
    FieldName.DENTAL_ALLOWANCE: "$1,500 per year",
    FieldName.OTC_ALLOWANCE: "$50 per quarter",
}

FIELDS_ON_PAGE_1 = 8  # the other 7 go on page 2
ROW_HEIGHT = 24
LEFT, MID, RIGHT = 54, 330, 558


@dataclass(frozen=True)
class FakePdf:
    path: Path
    page_count: int
    field_pages: dict[FieldName, int]  # 1-based page each field's row is on


def make_plan_pdf(
    out_dir: Path,
    *,
    year: int | None = 2026,
    document_type: DocumentType = DocumentType.SB,
    plan_ids: Sequence[str] = ("H9999-001",),
    carrier: str = "Example Health Plan",
    plan_name: str = "Example Gold Plus (HMO)",
    values: Mapping[FieldName, str] | None = None,
    name: str | None = None,
    omit: Collection[FieldName] = (),
    extra_rows: Sequence[tuple[int, str, str]] = (),
) -> FakePdf:
    """Write one SB, EOC, or ANOC shaped PDF and return where each field landed.

    `omit` leaves fields out (they are absent from field_pages). `extra_rows` adds
    (page, label, value) rows at the end of that page's table.
    """
    cells = {**DEFAULT_VALUES, **(values or {})}
    title = TITLES[document_type]
    year_text = f" {year}" if year is not None else ""
    path = out_dir / (name or f"{plan_ids[0] if plan_ids else 'none'}_{year}_{document_type}.pdf")
    canvas = Canvas(str(path), pagesize=LETTER)
    _, height = LETTER

    canvas.setFont("Helvetica-Bold", 14)
    canvas.drawString(LEFT, height - 60, f"{carrier}{year_text} {title}")
    canvas.setFont("Helvetica", 11)
    canvas.drawString(LEFT, height - 80, f"{plan_name} {' and '.join(plan_ids)}")
    if year is not None:
        canvas.drawString(LEFT, height - 96, f"January 1, {year} to December 31, {year}")
        if document_type is DocumentType.ANOC:
            canvas.drawString(LEFT, height - 112, f"What changes from {year - 1} to {year}")

    fields = list(FieldName)
    pages = [
        [f for f in fields[:FIELDS_ON_PAGE_1] if f not in omit],
        [f for f in fields[FIELDS_ON_PAGE_1:] if f not in omit],
    ]
    field_pages: dict[FieldName, int] = {}
    for number, page_fields in enumerate(pages, start=1):
        if number > 1:
            canvas.showPage()
        top = height - 140
        rows = [("Benefit", "What you pay")] + [(LABELS[f], cells[f]) for f in page_fields]
        rows += [(label, value) for page, label, value in extra_rows if page == number]
        for index, (label, value) in enumerate(rows):
            y = top - index * ROW_HEIGHT
            canvas.setFont("Helvetica-Bold" if index == 0 else "Helvetica", 10)
            canvas.drawString(LEFT + 6, y - 16, label)
            canvas.drawString(MID + 6, y - 16, value)
        bottom = top - len(rows) * ROW_HEIGHT
        for index in range(len(rows) + 1):
            canvas.line(LEFT, top - index * ROW_HEIGHT, RIGHT, top - index * ROW_HEIGHT)
        for x in (LEFT, MID, RIGHT):
            canvas.line(x, top, x, bottom)
        canvas.setFont("Helvetica", 8)
        canvas.drawString(LEFT, 36, f"Page {number} of {len(pages)}")
        field_pages.update(dict.fromkeys(page_fields, number))
    canvas.save()
    return FakePdf(path=path, page_count=len(pages), field_pages=field_pages)
