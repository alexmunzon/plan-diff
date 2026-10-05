"""Canonical plan schema with provenance. Every other module imports models from here."""

from pydantic import BaseModel

from plan_diff.models.citation import Citation, CitationMethod
from plan_diff.models.diff import (
    CMS_CROSSWALK_LABELS,
    ChangeCategory,
    CrosswalkStatus,
    Direction,
    FieldChange,
    PlanDiff,
    category_for,
    crosswalk_status_from_cms,
)
from plan_diff.models.fields import (
    Coinsurance,
    Copay,
    ExtractedField,
    FieldName,
    FieldValue,
    Money,
    NotCovered,
    Unit,
    annualize,
)
from plan_diff.models.ids import (
    Carrier,
    DocumentType,
    NonEmpty,
    PlanId,
    PlanYear,
    Sha256,
    StrictModel,
    normalize_plan_id,
)
from plan_diff.models.plan import PlanRecord
from plan_diff.models.review import ReviewItem, ReviewKind, Severity
from plan_diff.models.run import ApiUsage, RunConfig, RunInput, RunManifest, StepTiming
from plan_diff.models.source import SourceDocument, SourcesManifest
from plan_diff.models.validation import (
    ALLOWANCE_FIELDS,
    AccuracyRow,
    AccuracyTable,
    ValidationResult,
    Verdict,
    disagreement,
    verdict_for,
)

# One per run output file (SPEC section 7). `plan-diff schema export` writes a JSON Schema for each.
TOP_LEVEL_MODELS: tuple[type[BaseModel], ...] = (
    SourcesManifest,
    PlanRecord,
    ValidationResult,
    PlanDiff,
    ReviewItem,
    AccuracyTable,
    RunManifest,  # PR 9
)

__all__ = [
    "ALLOWANCE_FIELDS",
    "AccuracyRow",
    "AccuracyTable",
    "ApiUsage",
    "CMS_CROSSWALK_LABELS",
    "TOP_LEVEL_MODELS",
    "Carrier",
    "ChangeCategory",
    "Citation",
    "CitationMethod",
    "Coinsurance",
    "Copay",
    "CrosswalkStatus",
    "Direction",
    "DocumentType",
    "ExtractedField",
    "FieldChange",
    "FieldName",
    "FieldValue",
    "Money",
    "NonEmpty",
    "NotCovered",
    "PlanDiff",
    "PlanId",
    "PlanRecord",
    "PlanYear",
    "ReviewItem",
    "ReviewKind",
    "RunConfig",
    "RunInput",
    "RunManifest",
    "Severity",
    "Sha256",
    "StepTiming",
    "SourceDocument",
    "SourcesManifest",
    "StrictModel",
    "Unit",
    "annualize",
    "ValidationResult",
    "Verdict",
    "category_for",
    "crosswalk_status_from_cms",
    "disagreement",
    "verdict_for",
    "normalize_plan_id",
]
