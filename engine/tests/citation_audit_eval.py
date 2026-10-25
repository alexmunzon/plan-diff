"""`npm run audit-eval`: the citation audit, the citation-exists-only baseline, and the negative
controls, each scored against the frozen labels with the policy 2 expectations on top, plus the
policy 1 lane scored against the original frozen labels alone. Writes one JSON evidence file,
never over an existing one. Offline, synthetic, deterministic rules only: no model is called.

    uv run python tests/citation_audit_eval.py --out ../docs/citation-audit/evidence/NAME.json
"""

import argparse
import hashlib
import json
import resource
import sys
import tempfile
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from audit_cases import (
    CASE_SETS,
    FIXTURES,
    POLICY_1_SETS,
    POLICY_2,
    audit_cases,
    freeze_problems,
    frozen_pdfs,
    load_cases,
    load_labels,
)

from plan_diff.audit.checks import Policy
from plan_diff.audit.evaluate import gates, problems, report, summarize
from plan_diff.audit.runner import code_hash

# Each negative control turns off one safeguard. The first cases must become falsely supported;
# each of the second must become the named verdict, the one the removed check explains: with
# booklet pages ignored, Gold's $25 page now disagrees with Silver's $40 (q45); with dates
# ignored, the replacement's $30 no longer supersedes the cited $25 (d15). Under policy 2 the
# plan-year and contradiction controls use the dated v4 cases, since undated ones already go to
# a person for their unknown dates and could not show the removed safeguard.
MUTANTS: dict[str, tuple[Policy, tuple[str, ...], dict[str, str]]] = {
    "accept_any_existing_citation": (Policy(require_support=False), ("d05", "d06", "d22"), {}),
    "ignore_plan_year": (
        Policy(check_plan_year=False),
        ("q12",),
        {"q45": "conflicting_evidence"},
    ),
    "ignore_effective_dates": (
        Policy(check_effective_dates=False),
        ("d14",),
        {"d15": "conflicting_evidence"},
    ),
    "remove_contradiction_check": (Policy(check_contrary=False), ("q04", "q09"), {}),
    "treat_unknown_as_supported": (Policy(unknown_blocks=False), ("d18", "d36", "d42"), {}),
    "accept_unknown_dates": (Policy(unknown_dates_block=False), ("d01", "c12", "q03"), {}),
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def lane(
    name: str,
    policy: Policy,
    root: Path,
    drop: str | None = None,
    labels_policy: int = 2,
    sets: Sequence[Path] = CASE_SETS,
) -> dict[str, Any]:
    cases, labels = load_cases(sets), load_labels(labels_policy, sets)
    started = time.perf_counter()
    results, pdfs = {}, {}
    for case_id, audit, hashes in audit_cases(root / name, policy, drop=drop, sets=sets):
        results[case_id] = audit
        pdfs[case_id] = hashes
    inputs = {
        str(path.relative_to(FIXTURES)): sha(path)
        for folder in (*sets, POLICY_2)
        for path in sorted(folder.glob("*"))
        if path.suffix in (".json", ".md")
    } | {
        "audit_code": code_hash(),
        "labels_policy": str(labels_policy),
        "rubric-freeze.json": sha(FIXTURES / "rubric-freeze.json"),
        "evaluation_harness": sha(Path(__file__)),
        "case_builder": sha(Path(__file__).with_name("audit_cases.py")),
    }
    doc = report(name, policy.as_dict(), results, cases, labels, inputs)
    doc["wall_seconds"] = round(time.perf_counter() - started, 3)
    frozen = frozen_pdfs()
    changed = sorted(c for c, h in pdfs.items() if frozen.get(c) != h)
    doc["integrity_problems"] = (
        problems(
            json.loads(json.dumps(doc, sort_keys=True)),
            cases,
            labels,
            lane=name,
            policy=policy.as_dict(),
            hashes=inputs,
        )
        + freeze_problems()
    )
    if changed:  # the PDF generator or reportlab changed the evidence itself
        doc["integrity_problems"].append(f"generated PDFs differ from the freeze: {changed}")
    doc["pdf_sha256"] = pdfs
    return doc


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="plan-diff-audit-eval-") as tmp:
        root = Path(tmp)
        audit = lane("audit", Policy(), root)
        baseline = lane("baseline_citation_exists", Policy(require_support=False), root)
        # Policy 1 preserves agreement on these 77 original fixtures only. This does not
        # establish semantic equivalence on other inputs. Never the default.
        legacy = lane(
            "policy_1_legacy",
            Policy(unknown_dates_block=False),
            root,
            labels_policy=1,
            sets=POLICY_1_SETS,
        )
        controls = {}
        labels = load_labels()
        for name, (policy, to_supported, to_other) in MUTANTS.items():
            doc = lane(name, policy, root)
            got = {r["case_id"]: r["predicted"] for r in doc["rows"]}
            controls[name] = {
                "policy": policy.as_dict(),
                "must_become_supported": list(to_supported),
                "must_become": to_other,
                "got": {c: got[c] for c in (*to_supported, *to_other)},
                "integrity_problems": doc["integrity_problems"],
                "caught": all(got[c] == "supported" for c in to_supported)
                and all(got[c] == v != labels[c]["verdict"] for c, v in to_other.items())
                and not doc["gates"]["hard_no_false_supported"]
                and not doc["integrity_problems"],
                "false_supported": doc["summary"]["false_supported"],
            }
        dropped = lane("drop_failing_case", Policy(), root, drop="d05")
        forged = json.loads(json.dumps(audit))
        forged["summary"]["exact_agreement"]["count"] += 1
        cases = load_cases()
        controls["drop_failing_case"] = {
            "integrity_problems": dropped["integrity_problems"],
            "caught": bool(dropped["integrity_problems"])
            and not dropped["gates"]["hard_complete_inventory"],
        }
        controls["forge_summary"] = {
            "integrity_problems": problems(
                forged,
                cases,
                labels,
                lane="audit",
                policy=Policy().as_dict(),
                hashes=audit["inputs"],
            ),
            "caught": bool(
                problems(
                    forged,
                    cases,
                    labels,
                    lane="audit",
                    policy=Policy().as_dict(),
                    hashes=audit["inputs"],
                )
            ),
        }
        # Flip one prediction to supported, keep its old scoring fields, and recompute the
        # summary and gates from the edited rows: only the per-row rescoring can catch it.
        flipped = json.loads(json.dumps(audit))
        row = next(r for r in flipped["rows"] if r["case_id"] == "d05")
        row["predicted"] = "supported"
        row["predicted_parts"] = {k: "supported" for k in row["predicted_parts"]}
        flipped["summary"] = summarize(flipped["rows"])
        flipped["gates"] = gates(flipped["rows"], cases)
        scoring_problems = problems(
            flipped, cases, labels, lane="audit", policy=Policy().as_dict(), hashes=audit["inputs"]
        )
        controls["forge_scoring_fields"] = {
            "integrity_problems": scoring_problems,
            "caught": scoring_problems == ["d05: scoring fields do not follow from its verdicts"],
        }
    out = {
        "schema_version": "citation-audit-evidence-v1",
        "data_kind": "synthetic",
        "model_lane": "not_run",
        "human_adjudication": "not_run",
        "audit": audit,
        "baseline": baseline,
        "policy_1_legacy": legacy,
        "negative_controls": controls,
        "peak_rss_mb": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024 / 1024, 1),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x") as fh:  # evidence files are never overwritten
        fh.write(json.dumps(out, indent=1, sort_keys=True) + "\n")
    s, b = audit["summary"], baseline["summary"]
    print(f"wrote {args.out}")
    print(f"audit: agreement {s['exact_agreement']}, false supported {s['false_supported']}")
    print(f"baseline: agreement {b['exact_agreement']}, false supported {b['false_supported']}")
    print(f"gates: {audit['gates']}; integrity: {audit['integrity_problems'] or 'ok'}")
    g = legacy["summary"]
    print(f"policy 1 lane: agreement {g['exact_agreement']}, gates {legacy['gates']}")
    for name, c in controls.items():
        print(f"control {name}: {'caught' if c['caught'] else 'NOT CAUGHT'}")
    failed = not all(audit["gates"].values()) or audit["integrity_problems"]
    failed = failed or baseline["integrity_problems"] or legacy["integrity_problems"]
    failed = failed or not all(legacy["gates"].values())
    failed = failed or not all(c["caught"] for c in controls.values())
    if failed:
        print("FAILED: a gate failed, the report is inconsistent, or a control was not caught")
    return 1 if failed else 0  # the evidence file is written either way


if __name__ == "__main__":
    sys.exit(main())
