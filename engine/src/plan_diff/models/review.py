"""ReviewItem: something a person must look at. The pipeline never silently picks a value."""

from enum import StrEnum

from plan_diff.models.citation import Citation
from plan_diff.models.fields import FieldName
from plan_diff.models.ids import NonEmpty, PlanId, PlanYear, StrictModel


class ReviewKind(StrEnum):
    PDF_CMS_MISMATCH = "pdf_cms_mismatch"
    RULE_LLM_DISAGREE = "rule_llm_disagree"
    NOT_EXTRACTED = "not_extracted"
    UNCLASSIFIED_DOCUMENT = "unclassified_document"


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
