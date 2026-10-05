"""Year-over-year diff and the shop-again flag (SPEC decision 4, section 6 step 7).

The old-to-new plan mapping comes only from the CMS crosswalk. A plan id missing from the new year
is never read as a termination: with no crosswalk row the flag stays undecided and goes to review.
"""

from collections.abc import Iterable
from decimal import Decimal

import polars as pl

from plan_diff import config
from plan_diff.models import (
    Citation,
    CitationMethod,
    CrosswalkStatus,
    Direction,
    ExtractedField,
    FieldChange,
    FieldName,
    NotCovered,
    PlanDiff,
    PlanId,
    PlanRecord,
    ReviewItem,
    ReviewKind,
    Severity,
    StrictModel,
    annualize,
    category_for,
)
from plan_diff.models.diff import ChangeCategory


class CrosswalkRow(StrictModel):
    """One row of the CMS Part C and D Plan Crosswalk, as read by cms.readers.read_crosswalk."""

    previous_plan_id: PlanId | None
    current_plan_id: PlanId | None
    status: CrosswalkStatus
    cms_status_label: str
    source_row: int  # 1-based row in the CMS file
    document_id: str  # the CMS file name

    def citation(self) -> Citation:
        return Citation(
            document_id=self.document_id,
            page=self.source_row,
            method=CitationMethod.CMS,
            text=self.cms_status_label[:200] or None,
        )


def crosswalk_row_for(
    frame: pl.DataFrame, old_plan_id: str, document_id: str
) -> CrosswalkRow | None:
    """The crosswalk row for one old plan id, or None. Two rows for one id are refused."""
    rows = frame.filter(pl.col("previous_plan_id") == old_plan_id).to_dicts()
    if len(rows) > 1:
        raise ValueError(f"{document_id}: {len(rows)} crosswalk rows for {old_plan_id}")
    return CrosswalkRow(**rows[0], document_id=document_id) if rows else None


LABELS: dict[FieldName, str] = {
    FieldName.MONTHLY_PREMIUM: "premium",
    FieldName.MEDICAL_DEDUCTIBLE: "medical deductible",
    FieldName.MOOP_IN_NETWORK: "maximum out-of-pocket",
    FieldName.PCP_COPAY: "primary care visit",
    FieldName.SPECIALIST_COPAY: "specialist visit",
    FieldName.EMERGENCY_ROOM: "emergency room",
    FieldName.URGENT_CARE: "urgent care",
    FieldName.INPATIENT_STAY: "inpatient stay",
    FieldName.OUTPATIENT_SURGERY: "outpatient surgery",
    FieldName.DRUG_DEDUCTIBLE: "drug deductible",
    FieldName.DRUG_TIER_1: "drug tier 1",
    FieldName.DRUG_TIER_2: "drug tier 2",
    FieldName.DRUG_TIER_3: "drug tier 3",
    FieldName.DENTAL_ALLOWANCE: "dental allowance",
    FieldName.OTC_ALLOWANCE: "OTC allowance",
}

# Field, threshold, and the words after the amount in the reason.
THRESHOLDS: tuple[tuple[FieldName, Decimal, str], ...] = (
    (FieldName.MONTHLY_PREMIUM, config.SHOP_AGAIN_PREMIUM_UP, " a month"),
    (FieldName.MOOP_IN_NETWORK, config.SHOP_AGAIN_MOOP_UP, ""),
    (FieldName.DRUG_DEDUCTIBLE, config.SHOP_AGAIN_DRUG_DEDUCTIBLE_UP, ""),
)


def dollars(amount: Decimal) -> str:
    """$25, $1,000, $19.99: cents only when there are some."""
    return f"${amount:,.0f}" if amount == amount.to_integral_value() else f"${amount:,.2f}"


def _number(side: ExtractedField) -> Decimal | None:
    """The comparable number for one side, or None when it has none (for example a period-less
    allowance, which annualize refuses)."""
    value = side.value
    number = value.percent if value.kind == "coinsurance" else getattr(value, "amount", None)
    if number is None or category_for(side.name) != ChangeCategory.ALLOWANCES:
        return number
    try:
        return annualize(number, side.unit)
    except ValueError:
        return None


def compare(old: ExtractedField | None, new: ExtractedField | None) -> Direction:
    was_covered = old is not None and not isinstance(old.value, NotCovered)
    is_covered = new is not None and not isinstance(new.value, NotCovered)
    if old is None or (new is not None and not was_covered):
        return Direction.ADDED if is_covered or old is None else Direction.SAME
    if new is None:
        return Direction.NOT_COMPARABLE  # absent may be an extraction miss: review, never a flag
    if not is_covered:
        return Direction.REMOVED
    allowance = category_for(old.name) == ChangeCategory.ALLOWANCES
    if old.value.kind != new.value.kind or (old.unit != new.unit and not allowance):
        return Direction.NOT_COMPARABLE
    before, after = _number(old), _number(new)
    if before is None or after is None:
        return Direction.NOT_COMPARABLE
    return Direction.UP if after > before else Direction.DOWN if after < before else Direction.SAME


def _absent(name: FieldName, before: ExtractedField, new: PlanRecord) -> ReviewItem:
    return ReviewItem(
        kind=ReviewKind.NOT_EXTRACTED,
        plan_id=new.plan_id,
        year=new.year,
        field=name,
        evidence=(before.citation,),
        reason=f"{LABELS[name]} is in {new.year - 1} but was not found in {new.year}: check "
        "whether it was removed or missed",
        severity=Severity.MEDIUM,
    )


def _field_changes(
    old: PlanRecord, new: PlanRecord
) -> tuple[tuple[FieldChange, ...], list[str], list[ReviewItem]]:
    changes: list[FieldChange] = []
    reasons: list[str] = []
    review: list[ReviewItem] = []
    for name in FieldName:
        before, after = old.fields.get(name), new.fields.get(name)
        if before is None and after is None:
            continue
        direction = compare(before, after)
        changes.append(
            FieldChange(
                field=name, old=before, new=after, category=category_for(name), direction=direction
            )
        )
        if direction == Direction.REMOVED:
            reasons.append(f"benefit removed: {LABELS[name]} no longer covered")
        if before is not None and after is None:
            review.append(_absent(name, before, new))
    for name, threshold, tail in THRESHOLDS:
        change = next((c for c in changes if c.field == name), None)
        if change is None or change.direction != Direction.UP or not change.old or not change.new:
            continue
        rise = (_number(change.new) or Decimal(0)) - (_number(change.old) or Decimal(0))
        if rise >= threshold:
            reasons.append(f"{LABELS[name]} up {dollars(rise)}{tail}")
    return tuple(changes), reasons, review


def _check_row(old: PlanRecord, new: PlanRecord | None, row: CrosswalkRow) -> None:
    if row.previous_plan_id != old.plan_id:
        raise ValueError(f"crosswalk row is for {row.previous_plan_id}, not {old.plan_id}")
    if row.status == CrosswalkStatus.TERMINATED:
        if new is not None:
            raise ValueError(f"crosswalk says {old.plan_id} terminated, but a new record was given")
        return
    where = f"crosswalk maps {old.plan_id} to {row.current_plan_id}"
    if new is None:
        raise ValueError(f"{where}: no {old.year + 1} record")
    if new.plan_id != row.current_plan_id or new.year != old.year + 1:
        raise ValueError(f"{where}, not {new.plan_id} {new.year}")


def _undecided(old: PlanRecord) -> PlanDiff:
    item = ReviewItem(
        kind=ReviewKind.CROSSWALK_ROW_MISSING,
        plan_id=old.plan_id,
        year=old.year,
        field=None,
        evidence=(),
        reason=f"crosswalk row missing for {old.plan_id}: next year's plan is unknown, so shop "
        "again is undecided (a missing plan id is never read as a termination)",
        severity=Severity.HIGH,
    )
    return PlanDiff(
        old_plan_id=old.plan_id,
        new_plan_id=None,
        old_year=old.year,
        new_year=old.year + 1,
        crosswalk_status=None,
        changes=(),
        shop_again=None,
        reasons=(),
        review=(item,),
    )


def diff_plans(
    old: PlanRecord,
    new: PlanRecord | None,
    crosswalk_row: CrosswalkRow | None,
    service_area_old: Iterable[str],
    service_area_new: Iterable[str],
) -> PlanDiff:
    """Diff one plan into next year, following the crosswalk row, and decide shop again."""
    if crosswalk_row is None:
        return _undecided(old)
    _check_row(old, new, crosswalk_row)
    status = crosswalk_row.status
    reasons: list[str] = []
    changes: tuple[FieldChange, ...] = ()
    review: list[ReviewItem] = []
    if status == CrosswalkStatus.TERMINATED:
        reasons.append("plan terminated")
    if status == CrosswalkStatus.CONSOLIDATED:
        reasons.append(f"plan consolidated into {crosswalk_row.current_plan_id}")
    if new is not None:
        lost = sorted(set(service_area_old) - set(service_area_new))
        if lost:
            word = "county" if len(lost) == 1 else "counties"
            reasons.append(f"service area lost {len(lost)} {word}: {', '.join(lost)}")
        elif status == CrosswalkStatus.SERVICE_AREA_REDUCED:
            reasons.append("service area reduced (CMS crosswalk)")
        changes, field_reasons, review = _field_changes(old, new)
        reasons += field_reasons
    return PlanDiff(
        old_plan_id=old.plan_id,
        new_plan_id=new.plan_id if new else None,
        old_year=old.year,
        new_year=old.year + 1,
        crosswalk_status=status,
        changes=changes,
        shop_again=bool(reasons),
        reasons=tuple(reasons),
        evidence=(crosswalk_row.citation(),),
        review=tuple(review),
    )
