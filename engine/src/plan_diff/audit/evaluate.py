"""Score audit verdicts against frozen labels. Labels never come from the code under test.

Every metric carries its denominator. A summary is always recomputed from the per-case rows, and
`problems` refuses a report whose cases differ from the manifest, whose labels or scoring fields
differ from what the labels and predictions give, or whose summary or gates were edited.
"""

import math
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

from plan_diff.audit.checks import CLAIM_ORDER
from plan_diff.audit.models import ClaimAudit, Verdict

LOCATION_TAXONOMY = frozenset({"wrong_page", "wrong_offset", "fabricated_quote", "absent_evidence"})
ABSTAIN = frozenset({Verdict.NEEDS_HUMAN_REVIEW.value})
RECALL_FLOOR = 0.8
AGREEMENT_FLOOR = 0.8
VERDICTS = frozenset(v.value for v in Verdict)


def wilson(hits: int, n: int, z: float = 1.96) -> list[float] | None:
    """95% Wilson score interval for a proportion; None when nothing was counted."""
    if n == 0:
        return None
    p = hits / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return [round(max(0.0, centre - half), 4), round(min(1.0, centre + half), 4)]


def _rate(hits: int, n: int) -> dict[str, Any]:
    return {"count": hits, "denominator": n, "rate": round(hits / n, 4) if n else None}


def rows_for(
    results: Mapping[str, ClaimAudit],
    cases: Sequence[Mapping[str, Any]],
    labels: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    rows = []
    for case in cases:
        cid = case["case_id"]
        if cid not in results:
            continue  # missing from the results: problems() reports it, never a silent pass
        audit, label = results[cid], labels[cid]
        row = {
            "case_id": cid,
            "split": case["split"],
            "taxonomy": case["taxonomy"],
            "author": case["author"],
            "expected": label["verdict"],
            "predicted": audit.verdict.value,
            "expected_parts": label.get("parts", {}),
            "predicted_parts": {p.part_id: p.verdict.value for p in audit.parts},
        }
        rows.append(row | scores(row))
    return rows


def scores(row: Mapping[str, Any]) -> dict[str, bool]:
    """The scoring fields, derived only from a row's expected and predicted verdicts. A part
    falsely supported counts as a hard failure even when the claim's verdict hides it."""
    want, got = row["expected_parts"], row["predicted_parts"]
    return {
        "correct": row["predicted"] == row["expected"]
        and all(got.get(k) == v for k, v in want.items()),
        "false_supported": row["predicted"] == "supported" and row["expected"] != "supported",
        "part_false_supported": any(
            got.get(k) == "supported" and v != "supported" for k, v in want.items()
        ),
    }


def summarize(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    n = len(rows)
    pos = [r for r in rows if r["expected"] == "supported"]
    neg = [r for r in rows if r["expected"] != "supported"]
    said = [r for r in rows if r["predicted"] == "supported"]
    tp = sum(r["predicted"] == "supported" for r in pos)
    fs = sum(r["false_supported"] for r in rows)
    with_parts = [r for r in rows if r["expected_parts"]]
    conflicts = [r for r in rows if r["expected"] == "conflicting_evidence"]
    located = [r for r in rows if r["taxonomy"] in LOCATION_TAXONOMY]
    abstained = sum(r["predicted"] in ABSTAIN for r in rows)
    by_split: dict[str, dict[str, int]] = {}
    for r in rows:
        s = by_split.setdefault(r["split"], {"cases": 0, "correct": 0, "false_supported": 0})
        s["cases"] += 1
        s["correct"] += r["correct"]
        s["false_supported"] += r["false_supported"]
    taxonomy: dict[str, dict[str, int]] = {}
    for r in rows:
        t = taxonomy.setdefault(r["taxonomy"], {"cases": 0, "correct": 0})
        t["cases"] += 1
        t["correct"] += r["correct"]
    confusion = Counter(f"{r['expected']} -> {r['predicted']}" for r in rows)
    return {
        "cases": n,
        "exact_agreement": _rate(sum(r["correct"] for r in rows), n),
        "supported_precision": _rate(tp, len(said)),
        "supported_recall": _rate(tp, len(pos)),
        "false_supported": _rate(fs, len(neg)) | {"wilson_95": wilson(fs, len(neg))},
        "part_false_supported": _rate(
            sum(r["part_false_supported"] for r in with_parts), len(with_parts)
        ),
        "conflict_detection": _rate(
            sum(r["predicted"] == "conflicting_evidence" for r in conflicts), len(conflicts)
        ),
        "location_correct": _rate(sum(r["correct"] for r in located), len(located)),
        "abstention": _rate(abstained, n),
        "by_split": dict(sorted(by_split.items())),
        "by_taxonomy": dict(sorted(taxonomy.items())),
        "confusion": dict(sorted(confusion.items())),
    }


def report(
    lane: str,
    policy: Mapping[str, bool],
    results: Mapping[str, ClaimAudit],
    cases: Sequence[Mapping[str, Any]],
    labels: Mapping[str, Mapping[str, Any]],
    hashes: Mapping[str, str],
) -> dict[str, Any]:
    rows = rows_for(results, cases, labels)
    summary = summarize(rows)
    return {
        "schema_version": "citation-audit-eval-v1",
        "lane": lane,
        "policy": dict(policy),
        "inputs": dict(hashes),
        "rows": rows,
        "summary": summary,
        "gates": gates(rows, cases),
    }


def gates(rows: Sequence[Mapping[str, Any]], cases: Sequence[Mapping[str, Any]]) -> dict[str, bool]:
    summary = summarize(rows)
    floor = summarize([r for r in rows if r["split"] in ("dev", "regression")])
    return {
        "hard_no_false_supported": summary["false_supported"]["count"] == 0
        and summary["part_false_supported"]["count"] == 0,
        "hard_complete_inventory": len(rows) == len(cases),
        "floor_supported_recall": (floor["supported_recall"]["rate"] or 0) >= RECALL_FLOOR,
        "floor_exact_agreement": (floor["exact_agreement"]["rate"] or 0) >= AGREEMENT_FLOOR,
    }


def problems(
    doc: Mapping[str, Any],
    cases: Sequence[Mapping[str, Any]],
    labels: Mapping[str, Mapping[str, Any]],
    *,
    lane: str,
    policy: Mapping[str, bool],
    hashes: Mapping[str, str],
) -> list[str]:
    """Why a report cannot be trusted: a case dropped or added, a label or case field changed, a
    scoring field that does not follow from the row's verdicts, or a summary or gate that does
    not recompute from the rows. Empty means consistent."""
    found: list[str] = []
    identity = {
        "schema_version": "citation-audit-eval-v1",
        "lane": lane,
        "policy": dict(policy),
        "inputs": dict(hashes),
    }
    for key, expected in identity.items():
        if doc.get(key) != expected:
            found.append(f"{key} differs from the expected evaluation identity")
    want = [c["case_id"] for c in cases]
    got = [r["case_id"] for r in doc["rows"]]
    if sorted(want) != sorted(got) or len(got) != len(set(got)):
        missing, extra = sorted(set(want) - set(got)), sorted(set(got) - set(want))
        found.append(f"case inventory differs from the manifest: missing {missing}, extra {extra}")
    if set(labels) != set(want):
        found.append("labels and cases name different case ids")
    by_id = {c["case_id"]: c for c in cases}
    for r in doc["rows"]:
        cid = r["case_id"]
        if not isinstance(r["predicted"], str) or r["predicted"] not in VERDICTS:
            found.append(f"{cid}: predicted claim has an invalid verdict")
        if cid in labels and r["expected"] != labels[cid]["verdict"]:
            found.append(f"{cid}: expected verdict differs from labels.json")
        if cid in labels and r["expected_parts"] != labels[cid].get("parts", {}):
            found.append(f"{cid}: expected part verdicts differ from labels.json")
        if cid in by_id and any(r[k] != by_id[cid][k] for k in ("split", "taxonomy", "author")):
            found.append(f"{cid}: split, taxonomy, or author differs from cases.json")
        if any(r.get(k) != v for k, v in scores(r).items()):
            found.append(f"{cid}: scoring fields do not follow from its verdicts")
        if cid in by_id:
            declared = [p["part_id"] for p in by_id[cid]["claim"]["parts"]]
            parts = r["predicted_parts"]
            valid_parts = all(isinstance(v, str) and v in VERDICTS for v in parts.values())
            if not valid_parts:
                found.append(f"{cid}: predicted parts contain an invalid verdict")
            if set(parts) != set(declared) or len(declared) != len(set(declared)):
                found.append(f"{cid}: predicted parts differ from the claim's parts")
            elif valid_parts and r["predicted"] != next(
                v.value for v in CLAIM_ORDER if v.value in parts.values()
            ):
                found.append(f"{cid}: predicted verdict does not follow from its parts")
    if summarize(doc["rows"]) != doc["summary"]:
        found.append("summary does not recompute from the per-case rows")
    if gates(doc["rows"], cases) != doc["gates"]:
        found.append("gates do not recompute from the per-case rows")
    return found
