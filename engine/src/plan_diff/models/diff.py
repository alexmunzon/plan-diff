"""PlanDiff: one plan from one year to the next, keyed by the CMS crosswalk."""

from enum import StrEnum
from typing import Self

from pydantic import model_validator

from plan_diff.models.citation import Citation
from plan_diff.models.fields import ExtractedField, FieldName, NotCovered
from plan_diff.models.ids import NonEmpty, PlanId, PlanYear, StrictModel
from plan_diff.models.review import ReviewItem


class CrosswalkStatus(StrEnum):
    NEW = "new"
    CONTINUING = "continuing"
    CONSOLIDATED = "consolidated"  # two or more plans merged into new_plan_id
    SERVICE_AREA_REDUCED = "service_area_reduced"
    SERVICE_AREA_EXPANDED = "service_area_expanded"
    TERMINATED = "terminated"  # terminated or non-renewed; never inferred from a missing id


# CMS Part C and D Plan Crosswalk status labels (research file section 1c, from 42 CFR 422.530
# and CMS guidance). Not yet checked against the crosswalk file's own codebook: PR 3 confirms.
CMS_CROSSWALK_LABELS: dict[str, CrosswalkStatus] = {
    "new plan": CrosswalkStatus.NEW,
    "renewal plan": CrosswalkStatus.CONTINUING,
    "consolidated renewal plan": CrosswalkStatus.CONSOLIDATED,
    "renewal plan with sar": CrosswalkStatus.SERVICE_AREA_REDUCED,
    "renewal plan with service area reduction": CrosswalkStatus.SERVICE_AREA_REDUCED,
    "renewal plan with sae": CrosswalkStatus.SERVICE_AREA_EXPANDED,
    "renewal plan with service area expansion": CrosswalkStatus.SERVICE_AREA_EXPANDED,
    "terminated/non-renewed plan": CrosswalkStatus.TERMINATED,
    "terminated/non-renewed contract": CrosswalkStatus.TERMINATED,
}


def crosswalk_status_from_cms(label: str) -> CrosswalkStatus:
    """Map a CMS crosswalk label to a status. An unknown label raises, so it is never guessed."""
    key = " ".join(label.lower().split())
    if key not in CMS_CROSSWALK_LABELS:
        raise ValueError(f"unknown CMS crosswalk status: {label!r}")
    return CMS_CROSSWALK_LABELS[key]


class ChangeCategory(StrEnum):
    PREMIUM = "premium"
    DEDUCTIBLE = "deductible"
    MOOP = "moop"
    COPAYS = "copays"
    DRUGS = "drugs"
    ALLOWANCES = "allowances"


_CATEGORY = {
    FieldName.MONTHLY_PREMIUM: ChangeCategory.PREMIUM,
    FieldName.MEDICAL_DEDUCTIBLE: ChangeCategory.DEDUCTIBLE,
    FieldName.MOOP_IN_NETWORK: ChangeCategory.MOOP,
    FieldName.DRUG_DEDUCTIBLE: ChangeCategory.DRUGS,
    FieldName.DRUG_TIER_1: ChangeCategory.DRUGS,
    FieldName.DRUG_TIER_2: ChangeCategory.DRUGS,
    FieldName.DRUG_TIER_3: ChangeCategory.DRUGS,
    FieldName.DENTAL_ALLOWANCE: ChangeCategory.ALLOWANCES,
    FieldName.OTC_ALLOWANCE: ChangeCategory.ALLOWANCES,
}


def category_for(field: FieldName) -> ChangeCategory:
    """Every field not listed above is a visit or stay cost: a copay category."""
    return _CATEGORY.get(field, ChangeCategory.COPAYS)


class Direction(StrEnum):
    UP = "up"
    DOWN = "down"
    SAME = "same"
    ADDED = "added"  # no value last year, or not covered last year
    REMOVED = "removed"  # no value this year, or now not covered
    NOT_COMPARABLE = "not_comparable"  # different kind or unit, for example copay to coinsurance


class FieldChange(StrictModel):
    field: FieldName
    old: ExtractedField | None  # carries the old value, unit, and page
    new: ExtractedField | None
    category: ChangeCategory
    direction: Direction

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if self.category != category_for(self.field):
            raise ValueError(f"{self.field} belongs in {category_for(self.field)}")
        for side in (self.old, self.new):
            if side is not None and side.name != self.field:
                raise ValueError(f"{side.name} cannot describe {self.field}")
        if self.old is None and self.new is None:
            raise ValueError("a change needs an old or a new value")
        if self.old is None and self.direction != Direction.ADDED:
            raise ValueError("no old value means added")
        if self.direction == Direction.ADDED and not (
            self.old is None or isinstance(self.old.value, NotCovered)
        ):
            raise ValueError("added means there was no old value, or it was not covered")
        if self.new is None and self.direction != Direction.REMOVED:
            raise ValueError("no new value means removed")
        return self


_NEEDS_OLD = set(CrosswalkStatus) - {CrosswalkStatus.NEW}
_NEEDS_NEW = set(CrosswalkStatus) - {CrosswalkStatus.TERMINATED}


class PlanDiff(StrictModel):
    old_plan_id: PlanId | None  # None only for a new plan
    new_plan_id: PlanId | None  # None only for a terminated plan
    old_year: PlanYear
    new_year: PlanYear
    crosswalk_status: CrosswalkStatus | None  # None only when undecided (no crosswalk row)
    changes: tuple[FieldChange, ...]
    shop_again: bool | None  # None means undecided: a person must look (see review)
    reasons: tuple[NonEmpty, ...]  # plain language, for example "premium up $25 a month"
    evidence: tuple[Citation, ...] = ()  # PR 8: the CMS crosswalk row behind the status
    review: tuple[ReviewItem, ...] = ()  # PR 8: why the flag is undecided, if it is

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if self.new_year != self.old_year + 1:
            raise ValueError("new_year must be old_year + 1")
        if self.shop_again is None:
            if not self.review or self.reasons or self.changes:
                raise ValueError("undecided needs a review item and no reasons or changes")
            if self.crosswalk_status is None and (self.old_plan_id is None or self.new_plan_id):
                raise ValueError("with no crosswalk row, only the old plan id is known")
            if self.crosswalk_status is None:
                return self
        status = self.crosswalk_status
        if status is None:
            raise ValueError("a decided flag needs a crosswalk status")
        if (self.old_plan_id is not None) != (status in _NEEDS_OLD):
            raise ValueError(f"{status} plan: old_plan_id is wrong")
        if (self.new_plan_id is not None) != (status in _NEEDS_NEW):
            raise ValueError(f"{status} plan: new_plan_id is wrong")
        if self.shop_again is not None and self.shop_again != bool(self.reasons):
            raise ValueError("shop_again is true exactly when there are reasons")
        return self
