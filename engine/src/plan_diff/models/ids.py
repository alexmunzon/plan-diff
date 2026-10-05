"""Identifiers shared by every model, plus the strict base class."""

import re
from enum import StrEnum
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StrictInt

NonEmpty = Annotated[str, Field(min_length=1)]
Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]

# Medicare Advantage contract-plan id, ASCII digits only, in canonical form: H0028-030, or with a
# non-zero segment H0028-030-001. H is a local MA contract, R a regional PPO. Segment 000 is never
# written out (normalize_plan_id drops it), so one plan has exactly one spelling.
_SEGMENT = r"(00[1-9]|0[1-9][0-9]|[1-9][0-9]{2})"
PLAN_ID_REGEX = rf"^[HR][0-9]{{4}}-[0-9]{{3}}(-{_SEGMENT})?$"
PlanId = Annotated[str, Field(pattern=PLAN_ID_REGEX)]

# PR 15: carriers also write the id as "H5294_014", "H5294 | 014 | 000", or "H5294, Plan 014, 000"
# (all seen in the real Wellcare documents). Each is the same contract, plan, and segment.
_LOOSE_PLAN_ID = re.compile(
    r"([HR][0-9]{4})(?:-|_|\s*\|\s*|,\s*Plan\s+)([0-9]{1,3})(?:(?:-|_|\s*\|\s*|,\s*)([0-9]{1,3}))?"
)


def normalize_plan_id(text: str) -> str:
    """The one plan id rule: contract-plan plus segment, segment 000 (or none) dropped.

    H0028-030-000 becomes H0028-030; H5294-014-001 stays H5294-014-001 (segments can carry
    different benefits). Short plan or segment numbers are zero padded (H0028-30 is H0028-030).
    PR 15: "H5294_014", "H5294 | 014 | 000", and "H5294, Plan 014, 000" are H5294-014.
    Anything else, including S (Part D) and E (employer) contracts, raises ValueError.
    """
    match = _LOOSE_PLAN_ID.fullmatch(text.strip())
    if match is None:
        raise ValueError(f"not a Medicare Advantage plan id: {text!r}")
    contract, plan, segment = match.groups()
    base = f"{contract}-{plan.zfill(3)}"
    segment = (segment or "0").zfill(3)
    return base if segment == "000" else f"{base}-{segment}"


PlanYear = Annotated[StrictInt, Field(ge=2006, le=2100)]


def _normalize_carrier(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


# Open list on purpose: carriers come and go. Whitespace is collapsed, case is kept.
Carrier = Annotated[str, AfterValidator(_normalize_carrier), Field(min_length=1)]


class StrictModel(BaseModel):
    """Base for every schema model: unknown fields are refused and values never change."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class DocumentType(StrEnum):
    SB = "SB"  # Summary of Benefits
    EOC = "EOC"  # Evidence of Coverage
    ANOC = "ANOC"  # Annual Notice of Change
    OTHER = "OTHER"
    CMS_PBP = "CMS_PBP"  # CMS Plan Benefit Package benefits data (ZIP)
    CMS_LANDSCAPE = "CMS_LANDSCAPE"  # CMS Medicare Advantage Landscape file (ZIP)
    CMS_CROSSWALK = "CMS_CROSSWALK"  # CMS Part C and D Plan Crosswalk (ZIP)
