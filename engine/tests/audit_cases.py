"""PR 18: citation audit cases as real PDFs, audited through the same reader as a run.

Each case's documents are drawn with reportlab (invariant mode, so bytes are repeatable) into a
folder of their own, hashed, and read back with pdfplumber by plan_diff.audit.evidence. Nothing
here decides a verdict: labels live in labels.json and are only compared afterwards.
"""

import json
import re
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from reportlab import rl_config
from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen.canvas import Canvas

from plan_diff.audit.checks import Policy, audit_claim
from plan_diff.audit.evidence import CmsConflict, Corpus, Declared, build_corpus
from plan_diff.audit.models import Claim, ClaimAudit, EvidenceMeta
from plan_diff.models import FieldName
from plan_diff.run.documents import sha256_file

REPO = Path(__file__).resolve().parents[2]
FIXTURES = REPO / "fixtures" / "citation-audit"
CASES_DIR = FIXTURES / "v1"
# Each set is frozen on its own (PROVENANCE.md in its folder); a later set adds cases, never edits.
CASE_SETS = tuple(FIXTURES / f"v{n}" for n in range(1, 10))
# The sets written before policy 2 (Alex, 2026-10-25). Their frozen labels are policy 1's
# expectations; policy-2/expectations.json lists the cases whose expected verdict changes.
POLICY_1_SETS = CASE_SETS[:3]
POLICY_2 = FIXTURES / "policy-2"
TITLES = {
    "SB": "Summary of Benefits",
    "EOC": "Evidence of Coverage",
    "ANOC": "Annual Notice of Change",
}


def load_json(name: str, folder: Path = CASES_DIR) -> Any:
    return json.loads((folder / name).read_text())


def load_cases(sets: Sequence[Path] = CASE_SETS) -> list[dict[str, Any]]:
    cases = [c for folder in sets for c in load_json("cases.json", folder)["cases"]]
    ids = [c["case_id"] for c in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("a case id appears in two case sets")
    return cases


def load_labels(policy: int = 2, sets: Sequence[Path] = CASE_SETS) -> dict[str, Any]:
    """Expected verdicts. Policy 2 (the default) applies policy-2/expectations.json on top of
    the frozen labels; policy 1 is the frozen labels alone, for the sets written under it."""
    if policy not in (1, 2):
        raise ValueError(f"unsupported label policy: {policy}")
    labels = {
        k: v for folder in sets for k, v in load_json("labels.json", folder)["labels"].items()
    }
    if policy == 1:
        if any(folder not in POLICY_1_SETS for folder in sets):
            raise ValueError("only v1 to v3 have policy 1 labels")
        return labels
    scoped_ids = {c["case_id"] for c in load_cases(POLICY_1_SETS)}
    for name in ("expectations.json", "expectations-r2.json"):
        overlay = load_json(name, POLICY_2)
        if overlay.get("schema_version") != "citation-audit-expectations-v1":
            raise ValueError(f"unsupported expectations schema: {name}")
        if overlay.get("applies_to") != [p.name for p in POLICY_1_SETS]:
            raise ValueError(f"expectations scope must be v1 to v3: {name}")
        if name == "expectations-r2.json" and overlay.get("extends_sha256") != sha256_file(
            POLICY_2 / "expectations.json"
        ):
            raise ValueError("expectations revision does not extend the frozen original")
        overrides = overlay["overrides"]
        if not set(overrides) <= scoped_ids:
            raise ValueError(f"expectations override outside declared scope: {name}")
        labels |= {k: v for k, v in overrides.items() if k in labels}
    return labels


def freeze_problems() -> list[str]:
    """Each set's PROVENANCE.md (and policy-2's README.md) lists the SHA-256 of its frozen files;
    any difference from the files on disk is a problem, never a silent new version."""
    found = []
    frozen_files = [
        (folder, "PROVENANCE.md", {"cases.json", "labels.json"}) for folder in CASE_SETS
    ]
    for folder, doc, want in [
        *frozen_files,
        (POLICY_2, "README.md", {"expectations.json"}),
        (POLICY_2, "REVISION-2.md", {"expectations-r2.json"}),
    ]:
        frozen = re.findall(r"^([0-9a-f]{64})  (\S+)$", (folder / doc).read_text(), re.M)
        if {name for _, name in frozen} != want:
            found.append(f"{folder.name}/{doc} does not freeze exactly {sorted(want)}")
        for digest, name in frozen:
            if sha256_file(folder / name) != digest:
                found.append(f"{folder.name}/{name} differs from its frozen SHA-256")
    rubric = load_json("rubric-freeze.json", FIXTURES)
    if set(rubric) != {"v1/rubric.md", "policy-2/README.md"}:
        found.append("rubric freeze must name the original rubric and policy 2 addendum")
    else:
        for name, digest in rubric.items():
            if sha256_file(FIXTURES / name) != digest:
                found.append(f"{name} differs from its frozen SHA-256")
    return found


def frozen_pdfs() -> dict[str, dict[str, str]]:
    return {k: v for folder in CASE_SETS for k, v in load_json("pdf-sha256.json", folder).items()}


def draw_pdf(path: Path, doc: Mapping[str, Any]) -> None:
    """Header lines like the demo SBs (unless bare), the case's body lines, then a page footer."""
    rl_config.invariant = 1
    canvas = Canvas(str(path), pagesize=LETTER)
    _, height = LETTER
    pages = doc["pages"]
    for number, body in enumerate(pages, start=1):
        if number > 1:
            canvas.showPage()
        lines: list[str] = []
        if not doc.get("bare"):
            year = doc.get("year")
            title = TITLES.get(doc.get("document_type") or "", "Plan document")
            lines.append(f"Example Health Plan {year} {title}")
            lines.append(f"Gold HMO {doc['plan_id']}" if doc.get("plan_id") else "Gold HMO")
            lines.append(f"January 1, {year} to December 31, {year}")
            lines.append(doc.get("table_header", "Benefit What you pay"))
        lines += body
        canvas.setFont("Helvetica", 10)
        for index, line in enumerate(lines):
            canvas.drawString(54, height - 60 - index * 20, line)
        canvas.setFont("Helvetica", 8)
        canvas.drawString(54, 36, f"Page {number} of {len(pages)}")
    canvas.save()


@dataclass
class Built:
    corpus: Corpus
    claim: Claim
    pdf_sha256: dict[str, str]


def build_case(case: Mapping[str, Any], root: Path) -> Built:
    """Write the case's PDFs into `root` (a folder of its own) and build its evidence corpus."""
    root.mkdir(parents=True, exist_ok=True)
    declared, hashes = [], {}
    for doc in case["documents"]:
        path = root / f"{doc['document_id']}.pdf"
        draw_pdf(path, doc)
        sha = sha256_file(path)
        hashes[doc["document_id"]] = sha
        state = doc.get("state", "ok")
        if state == "missing":
            path.unlink()
        elif state == "truncated":
            path.write_bytes(path.read_bytes()[: path.stat().st_size // 2])
        elif state == "corrupt":
            path.write_bytes(b"%PDF-1.4\nthis is not a real PDF body\n")
            sha = sha256_file(path)  # the run recorded these exact (broken) bytes
            hashes[doc["document_id"]] = sha
        declared.append(
            Declared(doc["document_id"], sha, doc["plan_id"], doc["year"], doc["document_type"])
        )
    meta = EvidenceMeta.model_validate({"documents": case["meta"]})
    corpus = build_corpus(declared, root, meta)
    corpus.cms_conflicts = [
        CmsConflict(
            c["plan_id"], c["year"], FieldName(c["field"]), c["file"], c["row"], c["reason"]
        )
        for c in case["cms_conflicts"]
    ]
    return Built(corpus, Claim.model_validate(case["claim"]), hashes)


def audit_cases(
    root: Path,
    policy: Policy | None = None,
    drop: str | None = None,
    sets: Sequence[Path] = CASE_SETS,
) -> Iterator[tuple[str, ClaimAudit, dict[str, str]]]:
    """Audit every case under `policy`. `drop` skips one case: a negative control only."""
    for case in load_cases(sets):
        if case["case_id"] == drop:
            continue
        built = build_case(case, root / case["case_id"])
        result = audit_claim(built.claim, built.corpus, policy or Policy())
        yield case["case_id"], result, built.pdf_sha256
