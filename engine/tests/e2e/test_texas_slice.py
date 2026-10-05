"""PR 15: the real-data path in CI, with no download. CMS rows come from fixtures/cms-real (real,
public domain). The carrier side is a few REAL lines copied from the pinned Summary of Benefits
PDFs (each under 200 characters), drawn into throwaway PDFs in a temp folder. No carrier PDF and
no page longer than these lines is ever committed."""

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import reportlab
from reportlab.lib.pagesizes import LETTER
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas

from plan_diff.cms import AmountStatus, read_crosswalk, read_landscape, read_pbp
from plan_diff.models import AccuracyTable, CrosswalkStatus, FieldName, PlanDiff
from plan_diff.run import RunOptions
from plan_diff.run import run as run_folder

REAL = Path(__file__).resolve().parents[3] / "fixtures" / "cms-real"
PLANS = ("H0028-030", "H5294-014")
F = FieldName

HUMANA_COVER = ["{year}", "Summary of Benefits", "Humana Gold Plus H0028-030 (HMO)", "San Antonio"]
WELLCARE_COVER = ["{year}", "Summary of Benefits", "Texas", "Wellcare Patriot Simple (HMO)",
                  "H5294 | 014 | 000", "H5294_{year}_TX_SB_HMAO_4626794ENG_M"]  # fmt: skip

HUMANA = {
    2026: [
        [
            "Monthly Premium, Deductible and Limits",
            "Monthly plan premium $0",
            "Medical deductible This plan does not have adeductible.",
            "Pharmacy (Part D) deductible $0 deductible for Tier 1, Tier 2and Tier 3",
            "$615 deductible for Tier 4and Tier 5",
            "Medical Maximum out-of-pocket $3,400 in-network",
            "INPATIENT HOSPITAL COVERAGE",
            "This plan covers an unlimited number of days for an $95 copay per day for days 1-5",
            "OUTPATIENT HOSPITAL COVERAGE",
            "Surgery services $100 copay",
            "Primary Care Provider (PCP) • PCP's office: $0 copay",
            "Specialist • Specialist's office: $15 copay",
        ],
        [
            "EMERGENCY CARE",
            "Emergency services at emergency room $150 copay",
            "URGENTLY NEEDED SERVICES",
            "Urgently needed services are provided to treat a • Telehealth: $65 copay",
            "non-emergency, unforeseen medical illness, injury • Urgent care center: $65 copay",
            "DENTAL SERVICES",
            "• $4,000 maximum benefit coverage amount per",
            "year for all diagnostic/preventive and",
            "VISION SERVICES",
        ],
        [
            "Tier 1: Preferred Generic $0 $0 $10 $30 $0 $0",
            "Tier 2: Generic $0 $0 $20 $60 $0 $0",
            "Tier 3: Preferred Brand $45 $135 $47 $141 $45 $90",
            "Over-the-Counter (OTC) Allowance",
            "Humana Well Dine Meal Program",
            "$75 quarterly allowance on aprepaid $0 copayment for Humana Well Dine",
        ],
    ],
    2027: [
        [
            "Monthly plan premium $0",
            "Medical deductible This plan does not have a deductible.",
            "Pharmacy (Part D) deductible $0 deductible for Tier 1, Tier 2 and Tier 3",
            "$700 deductible for Tier 4 and Tier 5",
            "Medical Maximum out-of-pocket $3,900 in-network",
            "INPATIENT HOSPITAL COVERAGE",
            "This plan covers an unlimited number of days for an $150 copay per day for days 1-5",
            "OUTPATIENT HOSPITAL COVERAGE",
            "Surgery services $300 copay",
            "Primary Care Provider (PCP) • PCP's office: $0 copay",
            "Specialist • Specialist's office: $ 20 copay",
        ],
        [
            "EMERGENCY CARE",
            "Emergency services at emergency room $150 copay",
            "URGENTLY NEEDED SERVICES",
            "Urgently needed services are provided to treat a • Telehealth: $65 copay",
            "non-emergency, unforeseen medical illness, injury • Urgent care center: $65 copay",
            "DENTAL SERVICES",
            "• $4,000 maximum benefit coverage amount per",
            "year for all diagnostic/preventive and",
            "VISION SERVICES",
        ],
        [
            "Tier 1: Preferred Generic $0 $0 $10 $30 $0 $0",
            "Tier 2: Generic $0 $0 $20 $60 $0 $0",
            "Tier 3: Preferred Brand 17% 17% 17% 17% 17% 15%",
            "Over-the-Counter (OTC) Allowance Rewards and Incentives - Go365 by",
            "$60 quarterly allowance on a prepaid Humana",
        ],
    ],
}
WELLCARE = [
    [
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
    ],
    [
        "Additional Dental Information What you should know:",
        "This plan includes coverage of routine comprehensive services",
        "up to $3,000 per plan year.",
        "Wellcare Spendables You will receive $50 monthly preloaded on your Wellcare",
    ],
]


def _pdf(path: Path, pages: list[list[str]]) -> None:
    # Vera ships with reportlab and has the bullet the real SBs use (Helvetica here does not).
    font = Path(reportlab.__file__).parent / "fonts" / "Vera.ttf"
    pdfmetrics.registerFont(TTFont("Vera", str(font)))
    canvas = Canvas(str(path), pagesize=LETTER, invariant=True)
    for lines in pages:
        canvas.setFont("Vera", 9)
        y = 740
        for line in lines:
            canvas.drawString(40, y, line)
            y -= 16
        canvas.showPage()
    canvas.save()


def _docs(folder: Path) -> Path:
    folder.mkdir()
    for year in (2026, 2027):
        cover = [line.format(year=year) for line in HUMANA_COVER]
        _pdf(folder / f"humana-h0028-030-sb-{year}.pdf", [cover, *HUMANA[year]])
        cover = [line.format(year=year) for line in WELLCARE_COVER]
        _pdf(folder / f"wellcare-h5294-014-sb-{year}.pdf", [cover, *WELLCARE])
    return folder


def test_real_slice_readers() -> None:
    pbp = read_pbp(REAL / "pbp_2027", 2027, plan_ids=PLANS)
    got = {(r["plan_id"], r["field"]): r for r in pbp.to_dicts()}
    tier_3 = got[("H0028-030", F.DRUG_TIER_3)]
    assert (tier_3["amount_status"], tier_3["percent"]) == (AmountStatus.PERCENT, Decimal("17.00"))
    surgery = got[("H0028-030", F.OUTPATIENT_SURGERY)]
    assert (surgery["amount"], surgery["max_amount"]) == (Decimal("0.00"), Decimal("300.00"))
    assert surgery["amount_status"] == AmountStatus.RANGE
    otc = got[("H5294-014", F.OTC_ALLOWANCE)]
    assert (otc["amount"], otc["unit"]) == (Decimal("50.00"), "per_month")
    assert otc["file"] == "pbp_Section_D.txt" and "OTC DVH" in otc["note"]
    dental = got[("H0028-030", F.DENTAL_ALLOWANCE)]  # 16c "covered under 16b": the 16b maximum
    assert (dental["amount"], dental["unit"]) == (Decimal("4000.00"), "per_year")
    deductible = got[("H5294-014", F.MEDICAL_DEDUCTIBLE)]  # "no in-network deductible" is $0
    assert (deductible["amount"], deductible["amount_status"]) == (Decimal("0.00"), "value")
    assert got[("H5294-014", F.DRUG_DEDUCTIBLE)]["amount_status"] == AmountStatus.MISSING
    land = read_landscape(REAL / "landscape_2026.csv", 2026, plan_ids=PLANS)
    wellcare = land.filter(land["plan_id"] == "H5294-014")
    assert wellcare.height == 84 and set(wellcare["premium"]) == {Decimal("0.00")}  # Part C only
    cross = read_crosswalk(REAL / "crosswalk_2027.csv", 2027, plan_ids=PLANS)
    assert dict(zip(cross["previous_plan_id"], cross["status"], strict=True)) == {
        "H0028-030": CrosswalkStatus.CONTINUING,
        "H5294-014": CrosswalkStatus.SERVICE_AREA_REDUCED,
    }


def test_texas_slice_end_to_end(tmp_path: Path) -> None:
    options = RunOptions(
        docs=_docs(tmp_path / "docs"), cms=REAL, plans=PLANS, years=(2026, 2027),
        out=tmp_path / "runs", run_id="texas", data_kind="public",
    )  # fmt: skip
    folder = run_folder(options, lambda: datetime(2026, 10, 5, 12, tzinfo=UTC))
    humana = PlanDiff.model_validate_json((folder / "diff" / "H0028-030.json").read_text())
    assert humana.shop_again is True and humana.reasons == ("drug deductible up $85",)
    wellcare = PlanDiff.model_validate_json((folder / "diff" / "H5294-014.json").read_text())
    assert wellcare.shop_again is True
    assert wellcare.reasons[0].startswith("service area lost 33 counties: Bastrop, Bee")
    table = AccuracyTable.model_validate_json((folder / "accuracy.json").read_text())
    [total] = [r for r in table.rows if r.field is None]
    # The same counts as the full-file run committed in dashboard/public/texas-run/.
    assert (total.matched, total.mismatched, total.not_comparable) == (48, 0, 2)
    assert (total.not_extracted, total.not_in_cms) == (10, 0)
