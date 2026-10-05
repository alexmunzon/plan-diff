"""PR 15: extraction tuned to the real Summary of Benefits layouts.

Every string marked REAL is copied from a pinned public carrier document (sources/manifest.json)
as pdfplumber reads it, each under 200 characters. Strings marked SYNTHETIC are edits of a real
line made to prove a rule picks the right value. No PDF is committed."""

from decimal import Decimal

from plan_diff.classify import classify_pages
from plan_diff.extract import ExtractionResult, extract_pages
from plan_diff.models import Coinsurance, Copay, FieldName, Money, ReviewKind, Unit

F = FieldName
HUMANA = "2026\nSummary of Benefits\nHumana Gold Plus H0028-030 (HMO)"  # REAL, SB page 1
WELLCARE = (
    "2026\nSummary of Benefits\nTexas\nWellcare Patriot Simple (HMO)\nH5294 | 014 | 000"  # REAL
)


def run(cover: str, *pages: list[str], title: str = "Summary of Benefits") -> ExtractionResult:
    texts = [cover.replace("Summary of Benefits", title), *("\n".join(p) for p in pages)]
    classification = classify_pages(texts[:3], document_id="doc")
    assert classification.plan_id.value is not None
    return extract_pages(texts, classification)


def value(result: ExtractionResult, field: FieldName) -> tuple[object, Unit | None, float, int]:
    f = result.fields[field]
    return f.value, f.unit, f.confidence, f.citation.page


def kinds(result: ExtractionResult, field: FieldName) -> set[ReviewKind]:
    return {i.kind for i in result.review_items if i.field == field}


# REAL: Humana H0028-030 2026 SB page 4
HUMANA_PAGE_4 = [
    "Monthly Premium, Deductible and Limits",
    "Monthly plan premium $0",
    "Medical deductible This plan does not have adeductible.",
    "Pharmacy (Part D) deductible $0 deductible for Tier 1, Tier 2and Tier 3",
    "$615 deductible for Tier 4and Tier 5",
    "Medical Maximum out-of-pocket $3,400 in-network",
    "INPATIENT HOSPITAL COVERAGE",
    "This plan covers an unlimited number of days for an $95 copay per day for days 1-5",
    "inpatient stay $0 copay per day for days 6-90",
    "OUTPATIENT HOSPITAL COVERAGE",
    "Diagnostic colonoscopy $0 copay",
    "Surgery services $100 copay",
    "AMBULATORY SURGERY CENTER",
    "Surgery services $25 copay",
    "Primary Care Provider (PCP) • PCP's office: $0 copay",
    "• Telehealth: $0 copay",
    "Specialist • Specialist's office: $15 copay",
]


def test_humana_cost_rows() -> None:
    r = run(HUMANA, HUMANA_PAGE_4)
    assert value(r, F.MONTHLY_PREMIUM) == (Money(amount=Decimal(0)), Unit.PER_MONTH, 0.9, 2)
    assert value(r, F.MEDICAL_DEDUCTIBLE) == (Money(amount=Decimal(0)), Unit.PER_YEAR, 0.9, 2)
    assert value(r, F.MOOP_IN_NETWORK)[:3] == (Money(amount=Decimal(3400)), Unit.PER_YEAR, 0.9)
    assert value(r, F.INPATIENT_STAY)[:3] == (Copay(amount=Decimal(95)), Unit.PER_DAY, 0.9)
    # the outpatient hospital section's surgery row, not the surgery center's $25
    assert value(r, F.OUTPATIENT_SURGERY)[:3] == (Copay(amount=Decimal(100)), Unit.PER_VISIT, 0.9)
    assert value(r, F.PCP_COPAY)[:3] == (Copay(amount=Decimal(0)), Unit.PER_VISIT, 0.9)
    assert value(r, F.SPECIALIST_COPAY)[:3] == (Copay(amount=Decimal(15)), Unit.PER_VISIT, 0.9)
    assert not kinds(r, F.MONTHLY_PREMIUM)  # the section heading is not a second premium row


def test_tier_split_drug_deductible_is_the_highest_tier_amount() -> None:
    r = run(HUMANA, HUMANA_PAGE_4)
    assert value(r, F.DRUG_DEDUCTIBLE)[:3] == (Money(amount=Decimal(615)), Unit.PER_YEAR, 0.85)
    [item] = [i for i in r.review_items if i.field == F.DRUG_DEDUCTIBLE]
    assert "highest tier deductible" in item.reason and item.severity == "low"


def test_drug_benefit_deductible_rows_are_never_the_medical_deductible() -> None:
    page = [  # REAL, Humana 2026 SB page 11 (the medical deductible row is on page 4 only)
        "Prescription Drug Benefits",
        "Additional details below.",
        "Deductible $0 deductible for Tier 1, Tier 2and Tier 3",
        "DEDUCTIBLE",
        "$0 deductible for Tier 1, Tier 2and Tier 3. This plan has a $615 deductible for Tier 4and",
    ]
    r = run(HUMANA, page)
    assert F.MEDICAL_DEDUCTIBLE not in r.fields
    assert kinds(r, F.MEDICAL_DEDUCTIBLE) == {ReviewKind.NOT_EXTRACTED}


def test_humana_emergency_and_urgent_care() -> None:
    page = [  # REAL, Humana 2026 SB pages 5 and 6
        "EMERGENCY CARE",
        "Emergency services at emergency room $150 copay",
        "hours for the same condition, you pay $0 for the",
        "emergency care you received. We cover",
        "URGENTLY NEEDED SERVICES",
        "Urgently needed services are provided to treat a • Telehealth: $65 copay",
        "non-emergency, unforeseen medical illness, injury • Urgent care center: $65 copay",
    ]
    r = run(HUMANA, page)
    assert value(r, F.EMERGENCY_ROOM)[:3] == (Copay(amount=Decimal(150)), Unit.PER_VISIT, 0.9)
    assert not kinds(r, F.EMERGENCY_ROOM)  # "emergency care you received" is a sentence, not a row
    assert value(r, F.URGENT_CARE)[:3] == (Copay(amount=Decimal(65)), Unit.PER_VISIT, 0.9)
    # SYNTHETIC: telehealth priced differently proves the urgent care center line is the one read
    page[5] = page[5].replace("$65", "$40")
    assert value(run(HUMANA, page), F.URGENT_CARE)[0] == Copay(amount=Decimal(65))


def test_humana_dental_and_otc_allowances() -> None:
    dental = [  # REAL, Humana 2026 SB pages 7 and 8, the vision row that follows
        "DENTAL SERVICES",
        "Medicare-covered dental $15 copay",
        "• $4,000 maximum benefit coverage amount per",
        "year for all diagnostic/preventive and",
        "VISION SERVICES",
        "• $200 maximum benefit coverage amount per",
        "year for contact lenses or eyeglasses-lenses and",
    ]
    otc_2026 = [  # REAL, Humana 2026 SB page 15
        "Over-the-Counter (OTC) Allowance",
        "Humana Well Dine ® Meal Program",
        "$75 quarterly allowance on aprepaid $0 copayment for Humana Well Dine®",
    ]
    r = run(HUMANA, dental, otc_2026)
    assert value(r, F.DENTAL_ALLOWANCE)[:3] == (Money(amount=Decimal(4000)), Unit.PER_YEAR, 0.9)
    assert value(r, F.OTC_ALLOWANCE)[:3] == (Money(amount=Decimal(75)), Unit.PER_QUARTER, 0.9)
    otc_2027 = [  # REAL, Humana 2027 SB page 15: two column headings on one line
        "Over-the-Counter (OTC) Allowance Rewards and Incentives - Go365® by",
        "$60 quarterly allowance on a prepaid Humana",
    ]
    r = run(HUMANA, otc_2027)
    assert value(r, F.OTC_ALLOWANCE)[:3] == (Money(amount=Decimal(60)), Unit.PER_QUARTER, 0.9)


def test_drug_tier_grid_and_the_insulin_table() -> None:
    page = [  # REAL, Humana 2026 SB pages 11 and 12
        "Day supply 30-day 100-day* 30-day 100-day* 30-day 100-day*",
        "Tier 3: Preferred Brand $45 $135 $47 $141 $45 $90",
        "Insulin Cost-Sharing",
        "Tier 3: Preferred Brand 25% up to 25% up to 25% up to 25% up to 25% up to 25% up to",
        "CATASTROPHIC COVERAGE",
    ]
    r = run(HUMANA, page)
    # first column is retail 30-day; a grid pick stays below the 0.7 floor
    assert value(r, F.DRUG_TIER_3)[:3] == (Copay(amount=Decimal(45)), Unit.PER_PRESCRIPTION, 0.6)
    assert "different values" not in " ".join(
        i.reason for i in r.review_items if i.field == F.DRUG_TIER_3
    )
    coins = ["Tier 3: Preferred Brand 17% 17% 17% 17% 17% 15%"]  # REAL, Humana 2027 SB page 11
    assert value(run(HUMANA, coins), F.DRUG_TIER_3)[0] == Coinsurance(percent=Decimal(17))


def test_wellcare_rows() -> None:
    page_4 = [  # REAL, Wellcare H5294-014 2026 SB pages 4 and 5
        "Monthly Plan Premium $0",
        "Plan does not cover Part D.",
        "Deductible No deductible",
        "Maximum Out-of-Pocket (MOOP) $3,400 annually",
        "Inpatient Hospital Coverage For each admission, you pay:",
        "• $275 copay per day for days 1 through 5",
        "• $0 copay per day for days 6 through 90",
        "Primary Care Providers $0 copay",
        "Specialists $10 copay",
        "Emergency Care $150 copay",
        "Urgently Needed Services $25 copay",
    ]
    r = run(WELLCARE, page_4)
    assert value(r, F.MONTHLY_PREMIUM)[0] == Money(amount=Decimal(0))
    assert value(r, F.MEDICAL_DEDUCTIBLE)[:2] == (Money(amount=Decimal(0)), Unit.PER_YEAR)
    assert value(r, F.MOOP_IN_NETWORK)[:3] == (Money(amount=Decimal(3400)), Unit.PER_YEAR, 0.9)
    assert value(r, F.INPATIENT_STAY)[:3] == (Copay(amount=Decimal(275)), Unit.PER_DAY, 0.9)
    assert value(r, F.PCP_COPAY)[0] == Copay(amount=Decimal(0))
    assert value(r, F.SPECIALIST_COPAY)[0] == Copay(amount=Decimal(10))
    assert value(r, F.EMERGENCY_ROOM)[0] == Copay(amount=Decimal(150))
    assert value(r, F.URGENT_CARE)[0] == Copay(amount=Decimal(25))
    assert F.DRUG_DEDUCTIBLE not in r.fields  # "does not cover Part D" is never read as $0


def test_wellcare_dental_and_spendables() -> None:
    page = [  # REAL, Wellcare 2026 SB pages 8, 9, and 15
        "Additional Dental Information What you should know:",
        "This plan includes coverage of routine comprehensive services",
        "up to $3,000 per plan year.",
        "Wellcare Spendables® You will receive $50 monthly preloaded on your Wellcare",
    ]
    r = run(WELLCARE, page)
    assert value(r, F.DENTAL_ALLOWANCE)[:3] == (Money(amount=Decimal(3000)), Unit.PER_YEAR, 0.9)
    assert value(r, F.OTC_ALLOWANCE)[:3] == (Money(amount=Decimal(50)), Unit.PER_MONTH, 0.9)


def test_anoc_rows_with_last_year_and_this_year_are_not_read() -> None:
    page = [  # REAL, Humana 2026 ANOC page 5: 2025 then 2026 side by side
        "Maximum out-of-pocket amount $3,600 $3,400",
        # the real line has an en dash after each "days 1"; written as an escape, never typed
        "Inpatient hospital stays $75 copayment per day for days 1 \u2013 $95 copayment per day"
        " for days 1 \u2013",
    ]
    r = run(HUMANA, page, title="Annual Notice of Changes")
    assert F.MOOP_IN_NETWORK not in r.fields and F.INPATIENT_STAY not in r.fields
    assert kinds(r, F.MOOP_IN_NETWORK) == {ReviewKind.NOT_EXTRACTED}
