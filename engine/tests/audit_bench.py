"""`npm run audit-bench`: time the audit on a declared synthetic workload and write the numbers.

Workload: the demo run's 7 synthetic PDFs, and the 8 demo claims repeated with new ids up to the
claim limit (500). Shows each PDF is read once however many claims cite it, and how wall time,
peak memory, and output size grow. Offline; no model is called.
"""

import json
import resource
import sys
import tempfile
import time
from pathlib import Path

from audit_demo import CLAIMS, build
from demo_run import NOW

from plan_diff.audit.runner import AuditOptions, audit


def main() -> int:
    out = Path(sys.argv[1])
    rows = []
    with tempfile.TemporaryDirectory(prefix="plan-diff-audit-bench-") as tmp:
        root = Path(tmp)
        demo = build(root)  # also rebuilds the demo PDFs and run
        base = json.loads(CLAIMS.read_text())
        for n in (8, 100, 500):
            claims = [
                c | {"claim_id": f"{c['claim_id']}-{i}"}
                for i in range(n // 8 + 1)
                for c in base["claims"]
            ][:n]
            path = root / f"claims-{n}.json"
            path.write_text(json.dumps(base | {"claims": claims}))
            options = AuditOptions(
                claims=path,
                docs=root / "docs",
                out=root / "bench",
                audit_id=f"n{n}",
                run=root / "runs" / "demo",
            )
            started = time.perf_counter()
            folder = audit(options, lambda: NOW)
            seconds = time.perf_counter() - started
            manifest = json.loads((folder / "audit_manifest.json").read_text())
            rows.append(
                {
                    "claims": n,
                    "claims_file_bytes": path.stat().st_size,
                    "pdfs": len(manifest["documents"]),
                    "pdf_bytes": sum(p.stat().st_size for p in (root / "docs").glob("*.pdf")),
                    "pdf_reads": manifest["pdf_reads"],
                    "pages_read": manifest["pages_read"],
                    "wall_seconds": round(seconds, 3),
                    "audit_json_bytes": (folder / "audit.json").stat().st_size,
                }
            )
        assert demo.is_dir()
    peak = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024 / 1024, 1)
    doc = {
        "workload": "demo run PDFs, demo claims repeated",
        "machine": "local macOS, single process",
        "peak_rss_mb_whole_process": peak,
        "rows": rows,
    }
    with out.open("x") as fh:
        fh.write(json.dumps(doc, indent=1) + "\n")
    print(json.dumps(doc, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
