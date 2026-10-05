"""RunManifest (PR 9): what a run read, with what versions and modes, and what it cost."""

from typing import Annotated, Literal

from pydantic import AwareDatetime, Field, StrictInt

from plan_diff.models.fields import Amount
from plan_diff.models.ids import DocumentType, NonEmpty, PlanId, PlanYear, Sha256, StrictModel

Mode = Literal["off", "replay", "record", "live"]
# PR 13: what the run read. Set by `run --data-kind` (required), never guessed from plan ids.
DataKind = Literal["synthetic", "public"]


class RunInput(StrictModel):
    """One input file. `path` is relative to --docs or --cms, so the manifest has no local paths."""

    kind: Literal["pdf", "cms"]
    path: NonEmpty
    sha256: Sha256
    size_bytes: Annotated[StrictInt, Field(ge=0)]
    # PDFs only: classified (used), unsure, unreadable, or outside the requested plans and years
    status: Literal["classified", "unsure", "unreadable", "outside_slice"] | None = None
    document_id: str | None = None
    plan_id: PlanId | None = None
    year: PlanYear | None = None
    document_type: DocumentType | None = None
    # PR 14: PDFs only. The carrier's own https URL when sources/manifest.json pins this exact file
    # (same SHA-256), else None (synthetic demo PDFs). Page count when the PDF could be opened.
    source_url: Annotated[str, Field(pattern=r"^https://[^\s]+$")] | None = None
    page_count: Annotated[StrictInt, Field(ge=1)] | None = None
    # PR 15: PDFs only. For a multi-plan booklet, the pages read for each requested plan,
    # for example "H5294-014: pages 9 to 16". None when every page was read.
    plan_pages: str | None = None


class RunConfig(StrictModel):
    """PR 14: the decision values this run used, so the dashboard never keeps its own copy."""

    confidence_floor: Annotated[float, Field(ge=0, le=1)]  # a score, not money
    premium_up: Amount
    moop_up: Amount
    drug_deductible_up: Amount


class ApiUsage(StrictModel):
    mode: Mode
    calls: Annotated[StrictInt, Field(ge=0)]
    cost_usd: Amount  # Decimal, like all money


class StepTiming(StrictModel):
    step: NonEmpty
    seconds: Annotated[float, Field(ge=0)]  # a duration, not money; 0 when --now froze the clock


class RunManifest(StrictModel):
    schema_version: Literal[1] = 1
    run_id: NonEmpty
    data_kind: DataKind  # required: a run must say whether its documents are synthetic or public
    started_at: AwareDatetime
    finished_at: AwareDatetime
    versions: dict[str, str]  # plan-diff and the libraries that read the inputs
    plans: tuple[PlanId, ...]
    years: tuple[PlanYear, ...]
    inputs: tuple[RunInput, ...]
    modes: dict[str, str]  # per tier: rules "on"; Jev and LLM off, replay, record, or live
    jev: ApiUsage
    llm: ApiUsage
    timings: tuple[StepTiming, ...]
    counts: dict[str, int]  # documents, plan records, diffs, review items
    config: RunConfig  # PR 14
