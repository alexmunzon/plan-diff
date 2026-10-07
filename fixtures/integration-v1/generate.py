"""Explicit synthetic scenario only. Never derive enrollment in production adapters.

The Intake fixture is copied from Intake's real eight-client pipeline run. This deliberately
separate enrollment scenario supplies ONE claim. Other policies remain without coverage.
The plan values are synthetic demo examples re-keyed to the scenario's chosen policy.
"""

import hashlib
from pathlib import Path

from plan_diff.adapters.contract import (
    Coverage,
    CoverageFile,
    Packet,
    Provenance,
    canonical_json,
    pin,
)
from plan_diff.adapters.worklist import build_worklist, pin_plan_run
from plan_diff.diff.engine import CrosswalkRow, diff_plans
from plan_diff.models.diff import CrosswalkStatus
from plan_diff.models.plan import PlanRecord
from plan_diff.models.run import RunManifest

ROOT = Path(__file__).parent
DEMO = ROOT.parents[1] / "dashboard/public/demo-run"
PLAN_ID = "H8433-008"
COUNTY = "Example County, GA"
plan_root = ROOT / "plan-run"
(plan_root / "plans").mkdir(parents=True, exist_ok=True)
(plan_root / "diff").mkdir(exist_ok=True)
plans = []
for year in (2026, 2027):
    source = (DEMO / "plans" / f"H9999-001_{year}.json").read_text()
    source = source.replace("H9999-001", PLAN_ID)
    record = PlanRecord.model_validate_json(source)
    record = PlanRecord(**(record.model_dump() | {"counties": (COUNTY,)}))
    (plan_root / "plans" / f"{PLAN_ID}_{year}.json").write_text(canonical_json(record))
    plans.append(record)
change = diff_plans(
    plans[0],
    plans[1],
    CrosswalkRow(
        previous_plan_id=PLAN_ID,
        current_plan_id=PLAN_ID,
        status=CrosswalkStatus.CONTINUING,
        cms_status_label="Synthetic Renewal Plan",
        source_row=1,
        document_id="synthetic_crosswalk_2027.csv",
    ),
    (COUNTY,),
    (COUNTY,),
)
(plan_root / "diff" / f"{PLAN_ID}.json").write_text(canonical_json(change))
manifest = RunManifest.model_validate_json((DEMO / "manifest.json").read_text())
manifest = RunManifest(
    **(
        manifest.model_dump()
        | {
            "run_id": "plan-synthetic-v1",
            "plans": (PLAN_ID,),
            "inputs": (),
            "counts": {
                "documents": 0,
                "plan_records": 2,
                "diffs": 1,
                "review_items": len(change.review),
            },
        }
    )
)
(plan_root / "manifest.json").write_text(canonical_json(manifest))
(plan_root / "review_queue.jsonl").write_text("".join(canonical_json(r) for r in change.review))
# This is the scenario's explicit claim, not a missing-data default or an adapter inference.
row = 'synthetic-agency-a,C-00002,P-00003,H8433-008,2026,"Example County, GA"'
(ROOT / "synthetic-enrollment.csv").write_text(
    "agency_id,client_id,policy_id,plan_id,plan_year,county\n" + row + "\n"
)
source_pin = pin(ROOT, "synthetic-enrollment.csv")
coverage = CoverageFile(
    data_kind="synthetic",
    artifacts=(source_pin,),
    rows=(
        Coverage(
            agency_id="synthetic-agency-a",
            client_id="C-00002",
            policy_id="P-00003",
            plan_id=PLAN_ID,
            plan_year=2026,
            county=COUNTY,
            provenance=Provenance(
                source_file="synthetic-enrollment.csv",
                sheet=None,
                row_number=2,
                raw_hash=hashlib.sha256(row.encode()).hexdigest(),
                run_id="coverage-synthetic-v1",
                mapping_version="explicit-synthetic-scenario-v1",
                artifact=source_pin.path,
                artifact_row=1,
            ),
        ),
    ),
)
(ROOT / "coverage.json").write_text(canonical_json(coverage))
packet = Packet.model_validate_json((ROOT / "bob-packet.json").read_text())
worklist = build_worklist(
    packet,
    ROOT / "intake-run",
    coverage_root=ROOT,
    coverage_artifact=pin(ROOT, "coverage.json"),
    plan_root=plan_root,
    plan_artifacts=pin_plan_run(plan_root),
    run_id="worklist-synthetic-v1",
)
(ROOT / "worklist.json").write_text(canonical_json(worklist))
