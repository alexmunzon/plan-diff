"""Citation audit (PR 18): typed claims, evidence, checks, and the audit sidecar.

A claim is something a person wrote about a plan ("H9999-001 charges $25 a month in 2027, see the
Summary of Benefits page 1"). The audit asks whether the cited evidence actually supports it.
Citation existence, a matching hash, a plausible quote, or keyword overlap alone is not support.
This is a document review aid, never coverage adjudication or advice for a person's plan.
"""

from datetime import date
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import Field, StrictInt, model_validator

from plan_diff.models.fields import FieldName, FieldValue, Unit
from plan_diff.models.ids import DocumentType, NonEmpty, PlanId, PlanYear, Sha256, StrictModel
from plan_diff.models.run import DataKind

ClaimId = Annotated[str, Field(pattern=r"^[A-Za-z0-9._-]{1,64}$")]
Quote = Annotated[str, Field(min_length=1, max_length=300)]
# Free text a claimant wrote. Untrusted content: shown as text, never followed or executed.
ClaimText = Annotated[str, Field(min_length=1, max_length=500)]
Condition = Annotated[str, Field(min_length=1, max_length=80)]


class Verdict(StrEnum):
    SUPPORTED = "supported"
    CONTRADICTED = "contradicted"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    CONFLICTING_EVIDENCE = "conflicting_evidence"
    INAPPLICABLE_VERSION = "inapplicable_version"
    UNVERIFIABLE = "unverifiable"
    NEEDS_HUMAN_REVIEW = "needs_human_review"


class ClaimSource(StrictModel):
    """Where the claimant says the evidence is. Page is the 1-based physical page index."""

    document_id: NonEmpty
    page: Annotated[StrictInt, Field(ge=1)]
    quote: Quote | None = None
    sha256: Sha256 | None = None  # when given, the document must have exactly these bytes
    parts: tuple[ClaimId, ...] = ()  # the parts this source is cited for; empty means all


class ClaimPart(StrictModel):
    """One typed, checkable statement. A compound claim has several parts."""

    part_id: ClaimId
    benefit: FieldName
    value: FieldValue | None  # None: the claim names no checkable value
    unit: Unit | None
    network: Literal["in_network", "out_of_network"] | None = None
    # Words the evidence row must also carry, e.g. "days 1 to 5". Each must be found verbatim.
    conditions: tuple[Condition, ...] = ()


class Claim(StrictModel):
    claim_id: ClaimId
    text: ClaimText
    plan_id: PlanId
    year: PlanYear
    as_of: date | None = None  # the date the claim speaks about; None when unstated
    parts: Annotated[tuple[ClaimPart, ...], Field(min_length=1, max_length=8)]
    sources: Annotated[tuple[ClaimSource, ...], Field(max_length=5)]

    @model_validator(mode="after")
    def _unique_parts(self) -> Self:
        ids = [p.part_id for p in self.parts]
        if len(ids) != len(set(ids)):
            raise ValueError("part_id values must be unique within a claim")
        unknown = {i for s in self.sources for i in s.parts} - set(ids)
        if unknown:
            raise ValueError(f"sources name parts the claim does not have: {sorted(unknown)}")
        return self


class ClaimSet(StrictModel):
    schema_version: Literal["citation-claims-v1"] = "citation-claims-v1"
    data_kind: DataKind
    claims: Annotated[tuple[Claim, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def _unique_claims(self) -> Self:
        ids = [c.claim_id for c in self.claims]
        if len(ids) != len(set(ids)):
            raise ValueError("claim_id values must be unique")
        return self


class DocumentMeta(StrictModel):
    """What is explicitly known about a document's authority. Unknown stays None, never guessed."""

    document_id: NonEmpty
    effective_from: date | None = None
    effective_to: date | None = None
    supersedes: tuple[NonEmpty, ...] = ()  # document ids this one explicitly replaces
    printed_page_labels: dict[str, str] = {}  # "3" -> "ii" when the printed label differs
    note: Annotated[str, Field(max_length=200)] | None = None

    @model_validator(mode="after")
    def _window(self) -> Self:
        if self.effective_from and self.effective_to and self.effective_to < self.effective_from:
            raise ValueError("effective_to is before effective_from")
        return self


class EvidenceMeta(StrictModel):
    schema_version: Literal["evidence-meta-v1"] = "evidence-meta-v1"
    documents: tuple[DocumentMeta, ...] = ()


class EvidenceDocument(StrictModel):
    """One document the audit may read, with identity from the run manifest (or a case file)."""

    document_id: NonEmpty
    sha256: Sha256
    size_bytes: Annotated[StrictInt, Field(ge=0)]
    page_count: Annotated[StrictInt, Field(ge=0)]
    page_index: Literal["1-based physical page"] = "1-based physical page"
    plan_id: PlanId | None  # None: unknown, so applicability cannot be shown
    year: PlanYear | None
    document_type: DocumentType | None
    readable: bool  # False: missing, unreadable, or bytes differ from the recorded hash
    problem: str | None = None
    meta: DocumentMeta


class Location(StrictModel):
    kind: Literal["pdf_page", "cms_row"] = "pdf_page"
    document_id: NonEmpty  # for a CMS row, the CMS file name
    page: Annotated[StrictInt, Field(ge=1)]  # 1-based physical page, or 1-based CMS row
    printed_page: str | None = None  # only when declared in evidence metadata
    row: Quote | None = None  # the evidence row as read, at most 300 characters


Lane = Literal["deterministic", "model"]
Outcome = Literal["pass", "fail", "unknown", "not_run"]
CheckName = Literal[
    "text_matches_parts",
    "source_resolves",
    "hash_matches",
    "page_in_range",
    "quote_on_page",
    "plan_year_matches",
    "plan_pages",
    "effective_date_applies",
    "not_superseded",
    "row_found",
    "quote_covers_row",
    "row_in_grammar",
    "network_matches",
    "page_has_no_qualifiers",
    "conditions_present",
    "value_matches",
    "no_contrary_evidence",
    "model_judgment",
]


class Check(StrictModel):
    name: CheckName
    lane: Lane = "deterministic"
    outcome: Outcome
    reason: NonEmpty
    location: Location | None = None


class SourceResult(StrictModel):
    source_index: Annotated[StrictInt, Field(ge=0)]
    verdict: Verdict
    checks: tuple[Check, ...]


class Contrary(StrictModel):
    location: Location
    reason: NonEmpty
    dismissed: str | None = None  # why it does not count, from explicit metadata only


class PartResult(StrictModel):
    part_id: ClaimId
    checks: tuple[Check, ...]  # part-level checks, such as the claim text matching the part
    verdict: Verdict
    reasons: tuple[NonEmpty, ...]
    sources: tuple[SourceResult, ...]
    contrary: tuple[Contrary, ...]
    unknowns: tuple[NonEmpty, ...]


class ClaimAudit(StrictModel):
    claim: Claim  # verbatim, never rewritten
    verdict: Verdict
    reasons: tuple[NonEmpty, ...]
    parts: tuple[PartResult, ...]
    origin: Literal["deterministic_rules_v1"] = "deterministic_rules_v1"
    model_lane: Literal["not_run"] = "not_run"
    uncertainty: NonEmpty


class AuditSidecar(StrictModel):
    schema_version: Literal["citation-audit-v1"] = "citation-audit-v1"
    audit_id: NonEmpty
    data_kind: DataKind
    run_id: NonEmpty | None
    policy: dict[str, bool]
    documents: tuple[EvidenceDocument, ...]
    claims: tuple[ClaimAudit, ...]
    counts: dict[str, int]
    notice: NonEmpty


class Adjudication(StrictModel):
    """A reviewer decision, stored as its own numbered file. audit.json is never rewritten.

    Each revision names the audit it judges (by hash) and the revision before it (by hash), so a
    chain of corrections can be checked and no revision before the latest can be silently
    replaced. The latest revision has nothing after it to anchor it.
    """

    schema_version: Literal["citation-adjudication-v1"] = "citation-adjudication-v1"
    revision: Annotated[StrictInt, Field(ge=1)]
    audit_sha256: Sha256
    parent_sha256: Sha256 | None  # the previous revision file; None for revision 1
    claim_id: ClaimId
    computed_verdict: Verdict  # copied from audit.json, unchanged
    verdict: Verdict
    origin: Literal["human_reviewer"] = "human_reviewer"
    reviewer: Annotated[str, Field(min_length=1, max_length=80)]
    note: Annotated[str, Field(min_length=1, max_length=1000)]
    at: date
