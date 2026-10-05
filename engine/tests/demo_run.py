"""`npm run demo`: synthetic PDFs into a temp folder, one run against fixtures/cms, and the run's
JSON files copied to dashboard/public/demo-run/. No PDF ever lands in the repo.

The fake plans: H9999-001 continues and its premium rises from $0 to $25 (SPEC example 1; its
specialist copay says $45 where CMS says $40, example 4); H9999-002 is consolidated into
H9999-001 (example 2); H9999-003 is terminated (example 3). One extra SB has no plan id, so the
rules cannot classify it and it goes to review (example 8).
"""

import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from pdf_factory import make_plan_pdf
from reportlab import rl_config

from plan_diff.models import DocumentType, FieldName
from plan_diff.run import RunOptions, run, summary

REPO = Path(__file__).resolve().parents[2]
CMS = REPO / "fixtures" / "cms"
DEMO_OUT = REPO / "dashboard" / "public" / "demo-run"
PLANS = ("H9999-001", "H9999-002", "H9999-003")
NOW = datetime.fromisoformat("2026-10-05T12:00:00+00:00")
F = FieldName

# H9999-001 in 2026, matching the synthetic CMS rows except the specialist copay.
GOLD = {
    F.MONTHLY_PREMIUM: "$0 per month",
    F.MOOP_IN_NETWORK: "$4,900 per year",
    F.INPATIENT_STAY: "$325 per day, days 1 to 5",
    F.OUTPATIENT_SURGERY: "$250 per visit",
    F.DRUG_TIER_2: "$8 per prescription",
    F.DENTAL_ALLOWANCE: "$2,000 per year",
}
SILVER = {
    F.MONTHLY_PREMIUM: "$25.50 per month",
    F.MEDICAL_DEDUCTIBLE: "$250 per year",
    F.MOOP_IN_NETWORK: "$6,700 per year",
    F.PCP_COPAY: "$5 per visit",
    F.EMERGENCY_ROOM: "$110 per visit",
    F.URGENT_CARE: "$35 per visit",
    F.OUTPATIENT_SURGERY: "$200 per visit",
    F.DRUG_DEDUCTIBLE: "$200 per year",
    F.DRUG_TIER_1: "$2 per prescription",
    F.DRUG_TIER_2: "$10 per prescription",
    F.DRUG_TIER_3: "$45 per prescription",
    F.OTC_ALLOWANCE: "$150 per year",
}


def write_demo_docs(docs: Path) -> None:
    """The demo's synthetic SBs. Byte-identical every time (reportlab invariant mode)."""
    rl_config.invariant = 1
    docs.mkdir(parents=True, exist_ok=True)
    sb = DocumentType.SB
    make_plan_pdf(docs, year=2026, plan_ids=("H9999-001",), values=GOLD, plan_name="Gold HMO")
    gold_2027 = GOLD | {F.MONTHLY_PREMIUM: "$25 per month"}
    make_plan_pdf(docs, year=2027, plan_ids=("H9999-001",), values=gold_2027, plan_name="Gold HMO")
    make_plan_pdf(docs, year=2026, plan_ids=("H9999-002",), values=SILVER, plan_name="Silver HMO")
    bronze = {F.MONTHLY_PREMIUM: "$12 per month"}
    make_plan_pdf(docs, year=2026, plan_ids=("H9999-003",), values=bronze, plan_name="Bronze HMO")
    make_plan_pdf(docs, year=2026, plan_ids=(), document_type=sb, name="unlabeled_2026_SB.pdf")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="plan-diff-demo-") as tmp:
        docs, runs = Path(tmp) / "docs", Path(tmp) / "runs"
        write_demo_docs(docs)
        options = RunOptions(
            docs=docs, cms=CMS, plans=PLANS, years=(2026, 2027), out=runs, run_id="demo"
        )
        folder = run(options, lambda: NOW)
        if DEMO_OUT.exists():
            shutil.rmtree(DEMO_OUT)  # generated output only; rebuilt below
        for path in sorted(folder.rglob("*")):
            if path.is_file() and path.suffix in (".json", ".jsonl"):
                target = DEMO_OUT / path.relative_to(folder)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, target)
        print(f"wrote {DEMO_OUT.relative_to(REPO)} (JSON only, no PDFs)")
        for line in summary(folder):
            print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
