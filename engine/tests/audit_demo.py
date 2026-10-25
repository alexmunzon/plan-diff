"""`npm run audit-demo`: audit fixtures/citation-audit/demo-claims.json against the demo run.

The synthetic demo PDFs and run are rebuilt in a temp folder exactly as `npm run demo` does; the
rebuilt run must match the committed dashboard/public/demo-run byte for byte, so the audit is
bound to the run the dashboard shows. The audit folder is copied to demo-run-audit next to it.
"""

import shutil
import sys
import tempfile
from pathlib import Path

from demo_run import CMS, DEMO_OUT, NOW, PLANS, REPO, write_demo_docs

from plan_diff.audit.runner import AuditOptions, audit
from plan_diff.run import RunOptions, run

CLAIMS = REPO / "fixtures" / "citation-audit" / "demo-claims.json"
# Declared effective dates for the demo SBs: each prints its own coverage period on page 1.
META = REPO / "fixtures" / "citation-audit" / "demo-meta.json"
AUDIT_OUT = REPO / "dashboard" / "public" / "demo-run-audit"
COMMAND = ("npm", "run", "audit-demo")


def build(tmp: Path) -> Path:
    docs = tmp / "docs"
    write_demo_docs(docs)
    options = RunOptions(
        docs=docs, cms=CMS, plans=PLANS, years=(2026, 2027), out=tmp / "runs",
        run_id="demo", data_kind="synthetic",
    )  # fmt: skip
    folder = run(options, lambda: NOW)
    for name in ("manifest.json", "validation.json"):
        if (folder / name).read_bytes() != (DEMO_OUT / name).read_bytes():
            raise SystemExit(f"{name} differs from the committed demo run: run `npm run demo`")
    options_a = AuditOptions(
        claims=CLAIMS, docs=docs, out=tmp / "audits", audit_id="demo-audit", run=folder, meta=META
    )
    return audit(options_a, lambda: NOW, command=COMMAND)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="plan-diff-audit-demo-") as tmp:
        folder = build(Path(tmp))
        if AUDIT_OUT.exists():
            shutil.rmtree(AUDIT_OUT)  # generated output only; rebuilt below
        shutil.copytree(folder, AUDIT_OUT)
    print(f"wrote {AUDIT_OUT.relative_to(REPO)}")
    for line in (AUDIT_OUT / "audit_manifest.json").read_text().splitlines():
        if '"' in line and any(
            v in line
            for v in (
                "supported",
                "contradicted",
                "insufficient",
                "conflicting",
                "inapplicable",
                "unverifiable",
                "needs_human",
            )
        ):
            print(line.strip())
    return 0


if __name__ == "__main__":
    sys.exit(main())
