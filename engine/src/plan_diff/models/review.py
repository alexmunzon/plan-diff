"""ReviewItem: something a person must look at. The pipeline never silently picks a value."""

from enum import StrEnum
from typing import Annotated

from pydantic import Field

from plan_diff.models.citation import Citation
from plan_diff.models.fields import FieldName
from plan_diff.models.ids import NonEmpty, PlanId, PlanYear, StrictModel


class ReviewKind(StrEnum):
    PDF_CMS_MISMATCH = "pdf_cms_mismatch"
    RULE_LLM_DISAGREE = "rule_llm_disagree"
    NOT_EXTRACTED = "not_extracted"
    CONFLICTING_VALUES = "conflicting_values"  # one field read as two different values
    UNCLASSIFIED_DOCUMENT = "unclassified_document"
    UNKNOWN_PERIOD = "unknown_period"  # an allowance period no Unit matches; never made yearly
    CROSSWALK_ROW_MISSING = "crosswalk_row_missing"  # PR 8: never read as a termination
    SHOP_AGAIN_UNCERTAIN = "shop_again_uncertain"  # Review 2: a field that cannot decide the flag
    UNEXPECTED_UNIT = "unexpected_unit"  # Review 2: a yearly field whose cell states another period


class Severity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ReviewItem(StrictModel):
    kind: ReviewKind
    plan_id: PlanId | None  # None when the document could not be classified
    year: PlanYear | None
    field: FieldName | None  # None for a document-level item
    evidence: tuple[Citation, ...]  # every page or CMS row behind the item
    reason: NonEmpty
    severity: Severity
    # PR 7: how far to trust the value under review, 0 to 1; None when it does not apply
    confidence: Annotated[float, Field(ge=0, le=1)] | None = None
