"""Year-over-year diff and the shop-again flag (SPEC decision 4, section 6 step 7).

The old-to-new plan mapping comes only from the CMS crosswalk. A plan id missing from the new year
is never read as a termination: with no crosswalk row the flag stays undecided and goes to review.

Review 2: the flag is never confidently wrong. A threshold field or a removed benefit whose value
is missing, not comparable, in the wrong unit, below the confidence floor, or in disagreement with
CMS cannot decide the flag: it gets a high review item, and unless another reason fires the flag is
undecided (None). An empty county list never means "lost every county".
"""

import re
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
    Unit,
    ValidationResult,
    Verdict,
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


_THRESHOLD_FIELDS = frozenset(name for name, _, _ in THRESHOLDS)
Mismatches = dict[tuple[int, FieldName], ValidationResult]


def compare(old: ExtractedField | None, new: ExtractedField | None) -> Direction:
    if old is None or new is None:
        return Direction.NOT_COMPARABLE  # absent may be an extraction miss: review, never a flag
    was_covered = not isinstance(old.value, NotCovered)
    is_covered = not isinstance(new.value, NotCovered)
    if not was_covered:
        return Direction.ADDED if is_covered else Direction.SAME
    if not is_covered:
        return Direction.REMOVED
    allowance = category_for(old.name) == ChangeCategory.ALLOWANCES
    if old.value.kind != new.value.kind or (old.unit != new.unit and not allowance):
        return Direction.NOT_COMPARABLE
    before, after = _number(old), _number(new)
    if before is None or after is None:
        return Direction.NOT_COMPARABLE
    return Direction.UP if after > before else Direction.DOWN if after < before else Direction.SAME


def _absent(name: FieldName, found: ExtractedField, missing: PlanRecord, other: int) -> ReviewItem:
    verb = "removed" if missing.year > other else "added"
    return ReviewItem(
        kind=ReviewKind.NOT_EXTRACTED,
        plan_id=missing.plan_id,
        year=missing.year,
        field=name,
        evidence=(found.citation,),
        reason=f"{LABELS[name]} is in {other} but was not found in {missing.year}: check "
        f"whether it was {verb} or missed",
        severity=Severity.MEDIUM,
    )


def _words(unit: Unit | None) -> str:
    return unit.value.replace("_", " ") if unit else "no unit"


def _doubts(
    name: FieldName,
    sides: tuple[tuple[PlanRecord, ExtractedField | None], ...],
    direction: Direction | None,
    mismatches: Mismatches,
) -> tuple[list[str], list[Citation]]:
    """Why this field cannot decide the flag (empty when it can), and the pages behind that."""
    doubts: list[str] = []
    evidence: list[Citation] = []
    floor = config.SHOP_AGAIN_CONFIDENCE_FLOOR
    wanted = config.VALIDATE_CMS_UNITS[name.value] if name in _THRESHOLD_FIELDS else None
    for record, side in sides:
        year = record.year
        if side is None:
            doubts.append(f"not found in {year}")
            continue
        evidence.append(side.citation)
        if side.confidence < floor:
            doubts.append(f"{year} value read with confidence {side.confidence:g}, below {floor:g}")
        if wanted and not isinstance(side.value, NotCovered) and side.unit != Unit(wanted):
            doubts.append(f"{year} value is {_words(side.unit)}, not {_words(Unit(wanted))}")
        if (bad := mismatches.get((year, name))) is not None:
            if bad.verdict == Verdict.NOT_COMPARABLE:
                doubts.append(f"{year} PDF value cannot be checked against CMS ({bad.reason})")
            else:
                doubts.append(f"{year} PDF value disagrees with CMS ({bad.reason})")
            evidence += [bad.cms_citation] if bad.cms_citation else []
    if direction == Direction.NOT_COMPARABLE and not doubts:
        doubts.append("the two years are different kinds of value, so they cannot be compared")
    return doubts, evidence


def _uncertain(
    record: PlanRecord, field: FieldName | None, what: str, doubts: list[str], cites: list[Citation]
) -> ReviewItem:
    return ReviewItem(
        kind=ReviewKind.SHOP_AGAIN_UNCERTAIN,
        plan_id=record.plan_id,
        year=record.year,
        field=field,
        evidence=tuple(cites),
        reason=f"{what} cannot decide shop again: {'; '.join(doubts)}",
        severity=Severity.HIGH,
    )


def _field_changes(
    old: PlanRecord, new: PlanRecord, mismatches: Mismatches
) -> tuple[tuple[FieldChange, ...], list[str], list[ReviewItem]]:
    changes: list[FieldChange] = []
    reasons: list[str] = []
    review: list[ReviewItem] = []
    for name in FieldName:
        before, after = old.fields.get(name), new.fields.get(name)
        direction = None if before is None and after is None else compare(before, after)
        if direction is not None:
            category = category_for(name)
            changes.append(
                FieldChange(
                    field=name, old=before, new=after, category=category, direction=direction
                )
            )
        missing_old_benefit = before is not None and after is None
        decides = name in _THRESHOLD_FIELDS or direction == Direction.REMOVED or missing_old_benefit
        doubts, cites = _doubts(name, ((old, before), (new, after)), direction, mismatches)
        if decides and doubts:
            review.append(_uncertain(new, name, LABELS[name], doubts, cites))
            continue
        if direction == Direction.REMOVED:
            reasons.append(f"benefit removed: {LABELS[name]} no longer covered")
        if before is not None and after is None:
            review.append(_absent(name, before, new, old.year))
        if before is None and after is not None:
            review.append(_absent(name, after, old, new.year))
    for name, threshold, tail in THRESHOLDS:
        change = next((c for c in changes if c.field == name), None)
        if change is None or change.direction != Direction.UP or not change.old or not change.new:
            continue
        if any(i.field == name and i.kind == ReviewKind.SHOP_AGAIN_UNCERTAIN for i in review):
            continue
        rise = (_number(change.new) or Decimal(0)) - (_number(change.old) or Decimal(0))
        if rise >= threshold:
            reasons.append(f"{LABELS[name]} up {dollars(rise)}{tail}")
    return tuple(changes), reasons, review


def _county_key(name: str) -> str:
    words = re.sub(r"[^\w\s]", " ", name.lower()).split()
    if len(words) > 1 and words[-1] in config.COUNTY_SUFFIXES:
        words = words[:-1]
    return " ".join(words)


def same_county(a: str, b: str) -> bool:
    """Review 2: "Bexar County", "BEXAR", and "Bexar" are one county."""
    return _county_key(a) == _county_key(b)


def _service_area(
    old: PlanRecord, new: PlanRecord, area_old: Iterable[str], area_new: Iterable[str]
) -> tuple[list[str], list[ReviewItem]]:
    """Lost counties (the old spelling), or a review item when either list is empty."""
    before, after = list(area_old), list(area_new)
    empty = [r.year for r, area in ((old, before), (new, after)) if not area]
    if empty:
        years = " and ".join(str(y) for y in empty)
        why = f"the county list is empty for {years} (never read as losing every county)"
        return [], [_uncertain(new, None, "service area", [why], [])]
    kept = {_county_key(c) for c in after}
    lost: dict[str, str] = {}
    for county in before:
        if _county_key(county) not in kept:
            lost.setdefault(_county_key(county), county.strip())
    return sorted(lost.values()), []


# Release 0.1.0: a not comparable result blocks a deciding field just like a mismatch.
_BLOCKING = frozenset({Verdict.MISMATCH, Verdict.NOT_COMPARABLE})


def _mismatches(
    validation: Iterable[ValidationResult] | None, old: PlanRecord, new: PlanRecord
) -> Mismatches:
    mine = {(old.plan_id, old.year), (new.plan_id, new.year)}
    return {
        (r.year, r.field): r
        for r in validation or ()
        if r.verdict in _BLOCKING and (r.plan_id, r.year) in mine
    }


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
    *,
    validation: Iterable[ValidationResult] | None = None,
) -> PlanDiff:
    """Diff one plan into next year, following the crosswalk row, and decide shop again.

    `validation` (Review 2) is the PR 7 ValidationResult list for the old and new records; results
    for other plans or years are ignored. A MISMATCH or NOT_COMPARABLE on a threshold field or a
    removed benefit stops that field from deciding the flag. Without it, CMS disagreement is not
    checked (each field's extraction confidence still is). shop_again is True when any confident
    reason fires, None when none fires but a field could not decide, and False only when every
    deciding field is certain.
    """
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
        lost, review = _service_area(old, new, service_area_old, service_area_new)
        if lost:
            word = "county" if len(lost) == 1 else "counties"
            reasons.append(f"service area lost {len(lost)} {word}: {', '.join(lost)}")
        elif status == CrosswalkStatus.SERVICE_AREA_REDUCED:
            reasons.append("service area reduced (CMS crosswalk)")
        changes, field_reasons, field_review = _field_changes(
            old, new, _mismatches(validation, old, new)
        )
        reasons += field_reasons
        review += field_review
    uncertain = any(i.kind == ReviewKind.SHOP_AGAIN_UNCERTAIN for i in review)
    return PlanDiff(
        old_plan_id=old.plan_id,
        new_plan_id=new.plan_id if new else None,
        old_year=old.year,
        new_year=old.year + 1,
        crosswalk_status=status,
        changes=changes,
        shop_again=True if reasons else None if uncertain else False,
        reasons=tuple(reasons),
        evidence=(crosswalk_row.citation(),),
        review=tuple(review),
    )
