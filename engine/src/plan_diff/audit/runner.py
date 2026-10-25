"""`plan-diff audit`: one immutable audit folder next to a run, never inside it.

The folder holds audit.json (the sidecar) and audit_manifest.json (what was read, which code and
policy, when, and whether it finished). An existing folder is refused: audits are exclusive.
"""

import hashlib
import json
import re
import subprocess
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from importlib import metadata
from pathlib import Path
from typing import Annotated, Literal

from pydantic import AwareDatetime, Field, TypeAdapter, ValidationError

from plan_diff import __version__, config
from plan_diff.audit.checks import NOTICE, Policy, audit_claim
from plan_diff.audit.evidence import (
    DEFAULT_LIMITS,
    AuditRefused,
    Corpus,
    Limits,
    build_corpus,
    cms_conflicts,
    from_manifest,
)
from plan_diff.audit.models import Adjudication, AuditSidecar, ClaimSet, EvidenceMeta, Verdict
from plan_diff.models.ids import NonEmpty, Sha256, StrictModel
from plan_diff.models.run import RunManifest
from plan_diff.models.validation import ValidationResult

AUDIT_CODE = Path(__file__).parent
# Every module whose code can change a verdict: the audit package plus what it imports to read
# rows, values, booklet pages, and documents. All of them go into the recorded code hash.
_PACKAGE = AUDIT_CODE.parent
CODE_FILES = (
    *sorted(AUDIT_CODE.glob("*.py")),
    *(
        _PACKAGE / name
        for name in (
            "config.py",
            "classify/booklet.py",
            "extract/extractor.py",
            "extract/values.py",
            "models/citation.py",
            "models/fields.py",
            "models/ids.py",
            "models/run.py",
            "models/validation.py",
            "run/documents.py",
        )
    ),
)


class AuditManifest(StrictModel):
    schema_version: Literal["citation-audit-manifest-v1"] = "citation-audit-manifest-v1"
    audit_id: NonEmpty
    status: Literal["complete"]  # a folder only exists once the audit finished
    started_at: AwareDatetime
    finished_at: AwareDatetime
    command: tuple[str, ...]
    engine_version: NonEmpty
    git_commit: NonEmpty  # "unknown" outside a git checkout
    git_dirty: bool | None
    hashes: dict[str, Sha256]  # claims, metadata, run manifest, audit code, policy
    documents: dict[str, Sha256]
    pdf_reads: Annotated[int, Field(ge=0)]
    pages_read: Annotated[int, Field(ge=0)]
    claims: Annotated[int, Field(ge=0)]
    verdicts: dict[str, int]
    model_lane: Literal["not_run"] = "not_run"
    libraries: dict[
        str, str
    ]  # installed versions of the PDF and model libraries that read evidence


# Third-party code that can change what a page reads as; its versions go into the manifest.
LIBRARIES = ("pdfplumber", "pdfminer.six", "pypdf", "pydantic")


def library_versions() -> dict[str, str]:
    found = {}
    for name in LIBRARIES:
        try:
            found[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            found[name] = "not installed"
    return found


@dataclass(frozen=True)
class AuditOptions:
    claims: Path
    docs: Path
    out: Path
    audit_id: str
    run: Path | None = None  # a run folder; its manifest names each document and its hash
    meta: Path | None = None
    policy: Policy = Policy()
    limits: Limits = DEFAULT_LIMITS


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def code_hash() -> str:
    digest = hashlib.sha256()
    for path in CODE_FILES:
        name = path.relative_to(_PACKAGE).as_posix()
        digest.update(name.encode() + b"\0" + path.read_bytes())
    return digest.hexdigest()


def _git() -> tuple[str, bool | None]:
    try:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True, cwd=AUDIT_CODE
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=True,
            cwd=AUDIT_CODE,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown", None
    return head, bool(dirty)


def _read(path: Path, limits: Limits, what: str) -> bytes:
    if not path.is_file():
        raise AuditRefused(f"{what} {path} is not a file")
    if path.stat().st_size > limits.max_input_bytes:
        raise AuditRefused(f"{what} {path} is larger than {limits.max_input_bytes} bytes")
    return path.read_bytes()


def _check_out(o: AuditOptions) -> Path:
    if not re.fullmatch(config.RUN_ID_PATTERN, o.audit_id):
        raise AuditRefused(f"audit id {o.audit_id!r}: use letters, digits, dot, dash, underscore")
    final = o.out / o.audit_id
    if final.exists():
        raise AuditRefused(f"{final} already exists and audit folders are immutable")
    if o.run is not None and (
        final.resolve() == o.run.resolve() or o.run.resolve() in final.resolve().parents
    ):
        raise AuditRefused("write the audit next to the run folder, never inside it")
    return final


def audit(
    o: AuditOptions,
    clock: Callable[[], datetime],
    command: Sequence[str] = (),
    corpus: Corpus | None = None,
    run_manifest: RunManifest | None = None,
) -> Path:
    """Validate every input first, audit each claim, then install the folder in one swap."""
    final = _check_out(o)
    started = clock()
    raw_claims = _read(o.claims, o.limits, "claims file")
    raw_meta = _read(o.meta, o.limits, "evidence metadata") if o.meta else b""
    try:
        claims = ClaimSet.model_validate_json(raw_claims)
        meta = EvidenceMeta.model_validate_json(raw_meta) if o.meta else None
    except ValidationError as error:
        raise AuditRefused(f"invalid input, nothing audited: {error}") from error
    if len(claims.claims) > o.limits.max_claims:
        raise AuditRefused(f"{len(claims.claims)} claims; the limit is {o.limits.max_claims}")
    hashes = {"claims": sha256_bytes(raw_claims), "audit_code": code_hash()}
    hashes["policy"] = sha256_bytes(json.dumps(o.policy.as_dict(), sort_keys=True).encode())
    if o.meta:
        hashes["evidence_meta"] = sha256_bytes(raw_meta)
    if corpus is None:
        if o.run is None:
            raise AuditRefused("give --run so each document's identity comes from a run")
        raw_run = _read(o.run / "manifest.json", DEFAULT_LIMITS, "run manifest")
        run_manifest = RunManifest.model_validate_json(raw_run)
        hashes["run_manifest"] = sha256_bytes(raw_run)
        corpus = build_corpus(from_manifest(run_manifest), o.docs, meta, o.limits)
        raw_validation = _read(o.run / "validation.json", DEFAULT_LIMITS, "run validation")
        hashes["run_validation"] = sha256_bytes(raw_validation)
        validation = TypeAdapter(list[ValidationResult]).validate_json(raw_validation)
        corpus.cms_conflicts = cms_conflicts(validation)
    if run_manifest is not None and run_manifest.data_kind != claims.data_kind:
        raise AuditRefused(
            f"claims are {claims.data_kind} but the run is {run_manifest.data_kind}; never mixed"
        )
    results = tuple(audit_claim(c, corpus, o.policy) for c in claims.claims)
    counts = Counter(r.verdict.value for r in results)
    verdicts = {v.value: counts.get(v.value, 0) for v in Verdict}
    sidecar = AuditSidecar(
        audit_id=o.audit_id,
        data_kind=claims.data_kind,
        run_id=run_manifest.run_id if run_manifest else None,
        policy=o.policy.as_dict(),
        documents=tuple(corpus.documents.values()),
        claims=results,
        counts=verdicts | {"claims": len(results)},
        notice=NOTICE,
    )
    commit, dirty = _git()
    manifest = AuditManifest(
        audit_id=o.audit_id,
        status="complete",
        started_at=started,
        finished_at=clock(),
        command=tuple(command),
        engine_version=__version__,
        git_commit=commit,
        git_dirty=dirty,
        hashes=hashes,
        documents={d.document_id: d.sha256 for d in corpus.documents.values()},
        pdf_reads=corpus.reads,
        pages_read=corpus.page_total,
        claims=len(results),
        verdicts=verdicts,
        libraries=library_versions(),
    )
    o.out.mkdir(parents=True, exist_ok=True)
    try:
        final.mkdir()  # exclusive: a second writer with the same id fails here, replacing nothing
    except FileExistsError:
        raise AuditRefused(f"{final} already exists and audit folders are immutable") from None
    try:
        (final / "audit.json").write_text(sidecar.model_dump_json(indent=2) + "\n")
        # Written last: a folder without it never finished, and readers refuse it.
        (final / "audit_manifest.json").write_text(manifest.model_dump_json(indent=2) + "\n")
    except Exception as error:
        (final / "audit_failed.txt").write_text(f"{type(error).__name__}: {error}\n")
        raise
    return final


def _check_chain(
    earlier: Sequence[Path], audit_sha: str, computed: Mapping[str, Verdict]
) -> str | None:
    """Refuse to extend a revision chain that is not exactly 0001.json, 0002.json, ... each a
    valid revision of this audit, for one of its claims with that claim's computed verdict, whose
    parent is the hash of the one before. Returns the hash of the last revision (None when there
    is none). The last revision has no later hash pointing at it, so an edit to it alone cannot
    be detected here; every earlier one can."""
    parent: str | None = None
    for number, path in enumerate(earlier, start=1):
        if path.name != f"{number:04d}.json":
            raise AuditRefused(f"unexpected file {path.name} in the adjudication history")
        raw = path.read_bytes()
        try:
            record = Adjudication.model_validate_json(raw)
        except ValidationError:
            raise AuditRefused(f"adjudication {path.name} is not a valid revision") from None
        if (record.revision, record.parent_sha256, record.audit_sha256) != (
            number,
            parent,
            audit_sha,
        ):
            raise AuditRefused(f"adjudication {path.name} does not continue this audit's chain")
        if computed.get(record.claim_id) != record.computed_verdict:
            raise AuditRefused(
                f"adjudication {path.name} misstates a claim or its computed verdict"
            )
        parent = sha256_bytes(raw)
    return parent


def adjudicate(folder: Path, adjudication: dict[str, object]) -> Path:
    """Add one reviewer revision as adjudications/NNNN.json. audit.json is never touched."""
    if not (folder / "audit_manifest.json").is_file():
        raise AuditRefused(f"{folder} is not a finished audit")
    audit_bytes = (folder / "audit.json").read_bytes()
    sidecar = AuditSidecar.model_validate_json(audit_bytes)
    claim_id = adjudication.get("claim_id")
    computed = {c.claim.claim_id: c.verdict for c in sidecar.claims}
    if claim_id not in computed:
        raise AuditRefused(f"claim {claim_id!r} is not in this audit")
    store = folder / "adjudications"
    store.mkdir(exist_ok=True)
    audit_sha = sha256_bytes(audit_bytes)
    earlier = sorted(store.iterdir())
    parent = _check_chain(earlier, audit_sha, computed)
    record = Adjudication.model_validate(
        adjudication
        | {
            "revision": len(earlier) + 1,
            "audit_sha256": audit_sha,
            "parent_sha256": parent,
            "computed_verdict": computed[str(claim_id)],
        }
    )
    path = store / f"{record.revision:04d}.json"
    with path.open("x") as fh:  # never overwrites an existing revision
        fh.write(record.model_dump_json(indent=2) + "\n")
    return path
