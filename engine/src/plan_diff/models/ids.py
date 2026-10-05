"""Identifiers shared by every model, plus the strict base class."""

import re
from enum import StrEnum
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StrictInt

NonEmpty = Annotated[str, Field(min_length=1)]
Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]

# Medicare contract-plan id, ASCII digits only: H0028-030, or with a segment H0028-030-001.
PlanId = Annotated[str, Field(pattern=r"^H[0-9]{4}-[0-9]{3}(-[0-9]{3})?$")]
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
