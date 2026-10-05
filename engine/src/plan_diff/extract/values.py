"""Field parsers: one per field, grouped into families. Each turns a table cell into a typed value.

A parser never guesses. Text it cannot read returns None, and the caller sends the field to review.
"""

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from plan_diff import config
from plan_diff.models import (
    Coinsurance,
    Copay,
    FieldName,
    FieldValue,
    Money,
    NotCovered,
    Unit,
)
from plan_diff.models.fields import PERIODS_PER_YEAR

_MONEY = re.compile(r"\$\s?(\d{1,3}(?:,\d{3})+|\d+)(\.\d{1,2})?")
_PERCENT = re.compile(r"(\d{1,3}(?:\.\d{1,2})?)\s?%")
_NOT_COVERED = re.compile(r"\bnot covered\b", re.IGNORECASE)
# Review 2: an ellipsis or a sentence end also splits ("40%... In-network: $295"). "$1,500" stays.
_SEGMENT_SPLIT = re.compile(
    r",(?!\d{3}\b)|[;/]|\bor\b|\.{2,}|\u2026|(?-i:\.\s+(?=[A-Z]))", re.IGNORECASE
)
_PERIOD = re.compile(config.EXTRACT_PERIOD_PATTERN, re.IGNORECASE)
_DAY_RANGE = re.compile(r"\bdays?\s+\d", re.IGNORECASE)
_FOOTNOTES = str.maketrans(dict.fromkeys(config.EXTRACT_FOOTNOTE_MARKERS, " "))
_AMBIGUOUS_DIGIT = re.compile(config.EXTRACT_AMBIGUOUS_DIGIT)
_PARENS = "()"
_TIER_DEDUCTIBLE = re.compile(config.EXTRACT_TIER_DEDUCTIBLE, re.IGNORECASE)
_ZERO = {f: re.compile(p, re.IGNORECASE) for f, p in config.EXTRACT_ZERO_PHRASES.items()}

Token = Coinsurance | Decimal | NotCovered


@dataclass(frozen=True)
class FieldParser:
    field: FieldName
    kind: Literal["money", "copay"]  # what a dollar amount means for this field
    default_unit: Unit
    first_day_range: bool = False  # "$395 per day for days 1 to 5; $0 ..." keeps the first range
    period: bool = False  # an allowance: the unit is the period it states, else none (review)
    prefer: tuple[str, ...] = ("in-network",)  # keys of config.EXTRACT_PREFER_MARKERS, in order
    units: Literal["cost", "period"] = "cost"  # which phrase table may override default_unit
    tier_split: bool = False  # PR 15: "$0 deductible for Tier 1 ...; $615 deductible for Tier 4"

    @property
    def label(self) -> re.Pattern[str]:
        return re.compile(config.EXTRACT_LABELS[self.field.value], re.IGNORECASE)


@dataclass(frozen=True)
class Parsed:
    value: FieldValue
    unit: Unit | None
    multiple: bool  # the cell held two or more values; one was chosen by rule
    picked: str = ""  # which rule chose it, for the review item: "in-network", ..., or "first"
    unknown_period: str = ""  # an allowance with no known period next to it; unit is None
    ambiguous: str = ""  # a digit right after the amount may be a footnote marker (Review 2)
    labeled: bool = False  # the pick's own words carry an explicit marker such as "in-network"
    unexpected_unit: str = ""  # a yearly field (MOOP, deductible) whose own words state another


@dataclass(frozen=True)
class _Cand:
    start: int
    end: int
    value: Token


def _candidates(text: str) -> list[_Cand]:
    """Every dollar amount, percent, and "not covered", in reading order. "Not covered (you pay
    100%)" is one value: the 100% only restates it (Review 2)."""
    found = [
        _Cand(m.start(), m.end(), Decimal(m.group(1).replace(",", "") + (m.group(2) or "")))
        for m in _MONEY.finditer(text)
    ]
    found += [
        _Cand(m.start(), m.end(), Coinsurance(percent=Decimal(m.group(1))))
        for m in _PERCENT.finditer(text)
    ]
    not_covered = [_Cand(m.start(), m.end(), NotCovered()) for m in _NOT_COVERED.finditer(text)]
    if not_covered:
        full = Coinsurance(percent=Decimal(100))
        found = [c for c in found if c.value != full]
    return sorted([*found, *not_covered], key=lambda c: c.start)


def value_count(text: str) -> int:
    """PR 15: how many values (amounts, percents, "not covered") a cell holds."""
    return len(_candidates(text.translate(_FOOTNOTES)))


def _segments(text: str) -> list[tuple[int, int]]:
    bounds = [0]
    for m in _SEGMENT_SPLIT.finditer(text):
        bounds += [m.start(), m.end()]
    bounds.append(len(text))
    return [(bounds[i], bounds[i + 1]) for i in range(0, len(bounds), 2)]


def _own_span(text: str, cands: list[_Cand], i: int, seg: tuple[int, int]) -> str:
    """The chosen value's own words: its segment, cut at the neighbouring values and at any
    parenthesis, so "$50 ($200 a year)" gives $50 nothing about a year (Review 2)."""
    c = cands[i]
    start = max(seg[0], cands[i - 1].end if i > 0 else 0)
    end = min(seg[1], cands[i + 1].start if i + 1 < len(cands) else len(text))
    before = max((text.rfind(p, start, c.start) for p in _PARENS), default=-1)
    after = [k for p in _PARENS if (k := text.find(p, c.end, end)) != -1]
    return text[max(start, before + 1) : min([end, *after])]


_ATTACHED_PERIOD = re.compile(
    r"^\s*(?:\(\s*|,\s*)(?<![\w-])("
    + "|".join(re.escape(p) for p in sorted(config.EXTRACT_PERIOD_UNIT_PHRASES, key=len)[::-1])
    + r")\b",
    re.IGNORECASE,
)


def _attached_period(text: str, end: int) -> Unit | None:
    """A period right after the value, inside a parenthesis or after a comma: "$1,500 (per year)",
    "$50, every quarter". A parenthesis that starts with another value is not attached."""
    m = _ATTACHED_PERIOD.match(text[end:])
    return Unit(config.EXTRACT_PERIOD_UNIT_PHRASES[m.group(1).lower()]) if m else None


def _unit(text: str, phrases: dict[str, str]) -> Unit | None:
    """The earliest unit phrase in the text. "bi-annual" is not "annual"."""
    hits = [
        (m.start(), u)
        for p, u in phrases.items()
        if (m := re.search(rf"(?<![\w-]){re.escape(p)}\b", text, re.IGNORECASE))
    ]
    return Unit(min(hits)[1]) if hits else None


def parse_value(text: str, parser: FieldParser) -> Parsed | None:
    """Read one cell. Two or more values: the one the field's preferred markers pick (for example
    in-network, or a drug tier's standard pharmacy price), else the first (lower confidence).
    The unit comes only from the chosen value's own words (Review 2)."""
    clean = text.translate(_FOOTNOTES)
    cands = _candidates(clean)
    if not cands:
        zero = _ZERO.get(parser.field.value)
        if zero is not None and zero.search(
            clean
        ):  # PR 15: "This plan does not have a deductible."
            return Parsed(Money(amount=Decimal(0)), parser.default_unit, multiple=False)
        return None
    if parser.tier_split:
        tiers = [Decimal(m.group(1).replace(",", "")) for m in _TIER_DEDUCTIBLE.finditer(clean)]
        if len(tiers) >= 2:  # PR 15: the plan's deductible is the highest tier amount
            top = Money(amount=max(tiers))
            return Parsed(top, parser.default_unit, True, "highest tier deductible", labeled=True)
    segments = _segments(clean)

    def seg_of(c: _Cand) -> tuple[int, int]:
        return next(s for s in segments if s[0] <= c.start < s[1])

    index, picked = 0, ""
    rules: list[str] = []
    multiple = len(cands) > 1
    if multiple:
        segs = sorted({seg_of(c) for c in cands})
        for rule in parser.prefer:
            marker = re.compile(config.EXTRACT_PREFER_MARKERS[rule], re.IGNORECASE)
            marked = [s for s in segs if marker.search(clean[s[0] : s[1]])]
            if marked:
                segs, rules = marked, [*rules, rule]
        if rules:
            index = next(i for i, c in enumerate(cands) if seg_of(c) == segs[0])
        picked = " and ".join(rules) or "first"
    chosen = cands[index]
    seg = seg_of(chosen)
    range_text = clean[seg[0] : seg[1]] if rules else clean
    day_range = parser.first_day_range and _DAY_RANGE.search(range_text) is not None
    if day_range and not rules:
        multiple, picked = False, ""  # "$395 ... days 1 to 5; $0 ... days 6 to 90": first range
    ambiguous = ""
    if (m := _AMBIGUOUS_DIGIT.match(clean[chosen.end :])) is not None:
        ambiguous = clean[chosen.start : chosen.end + m.end()].strip()

    # Explicitly labeled: a trusted marker sits in the chosen value's own words, between its
    # neighbouring values ("$1,500 in-network / $500 ...", "$47 copay (standard) / $42 ...").
    near = clean[
        max(seg[0], cands[index - 1].end if index > 0 else 0) : min(
            seg[1], cands[index + 1].start if index + 1 < len(cands) else len(clean)
        )
    ]
    labeled = any(
        re.search(config.EXTRACT_PREFER_MARKERS[r], near, re.IGNORECASE)
        for r in rules
        if r in config.EXTRACT_LABELED_RULES
    )
    token = chosen.value
    value: FieldValue
    if isinstance(token, NotCovered | Coinsurance):
        value = token
    elif parser.kind == "money":
        value = Money(amount=token)
    else:
        value = Copay(amount=token)
    if isinstance(token, NotCovered):
        return Parsed(value, None, multiple, picked, ambiguous=ambiguous, labeled=labeled)
    span = _own_span(clean, cands, index, seg)
    stated = _unit(span, config.EXTRACT_PERIOD_UNIT_PHRASES) or _attached_period(clean, chosen.end)
    if parser.period:
        unit = stated
        if unit is None:
            m = _PERIOD.search(span)
            unknown = m.group(0) if m else "none stated next to the amount"
            return Parsed(value, None, multiple, picked, unknown, ambiguous, labeled)
        return Parsed(value, unit, multiple, picked, ambiguous=ambiguous, labeled=labeled)
    if parser.units == "period":
        unit = stated
    elif parser.default_unit in PERIODS_PER_YEAR and stated not in (None, parser.default_unit):
        # A MOOP or deductible that says "per month": keep the amount and its stated unit, but
        # never at full confidence (Review 2, unexpected_unit).
        assert stated is not None
        return Parsed(
            value,
            stated,
            multiple,
            picked,
            ambiguous=ambiguous,
            labeled=labeled,
            unexpected_unit=stated.value,
        )
    else:
        unit = _unit(span, config.EXTRACT_COST_UNIT_PHRASES)
    if day_range:
        unit = Unit.PER_DAY  # any day range means per day (Review 2)
    return Parsed(
        value, unit or parser.default_unit, multiple, picked, ambiguous=ambiguous, labeled=labeled
    )


# PR 5: the cost-sharing family.
COST_SHARING: tuple[FieldParser, ...] = (
    FieldParser(FieldName.MONTHLY_PREMIUM, "money", Unit.PER_MONTH, units="period"),
    FieldParser(FieldName.MEDICAL_DEDUCTIBLE, "money", Unit.PER_YEAR),
    FieldParser(FieldName.MOOP_IN_NETWORK, "money", Unit.PER_YEAR),
    FieldParser(FieldName.PCP_COPAY, "copay", Unit.PER_VISIT),
    FieldParser(FieldName.SPECIALIST_COPAY, "copay", Unit.PER_VISIT),
    FieldParser(FieldName.EMERGENCY_ROOM, "copay", Unit.PER_VISIT),
    FieldParser(FieldName.URGENT_CARE, "copay", Unit.PER_VISIT),
    FieldParser(FieldName.INPATIENT_STAY, "copay", Unit.PER_STAY, first_day_range=True),
    FieldParser(FieldName.OUTPATIENT_SURGERY, "copay", Unit.PER_VISIT),
)

# PR 6: the drug family. A tier is standard retail, 30-day supply, initial coverage stage.
_TIER_PREFER = ("in-network", "standard pharmacy", "30-day supply")
DRUGS: tuple[FieldParser, ...] = (
    FieldParser(FieldName.DRUG_DEDUCTIBLE, "money", Unit.PER_YEAR, tier_split=True),
    FieldParser(FieldName.DRUG_TIER_1, "copay", Unit.PER_PRESCRIPTION, prefer=_TIER_PREFER),
    FieldParser(FieldName.DRUG_TIER_2, "copay", Unit.PER_PRESCRIPTION, prefer=_TIER_PREFER),
    FieldParser(FieldName.DRUG_TIER_3, "copay", Unit.PER_PRESCRIPTION, prefer=_TIER_PREFER),
)

# PR 6: the allowance family. The period (month, quarter, year) is the unit; see annualize().
ALLOWANCES: tuple[FieldParser, ...] = (
    FieldParser(FieldName.DENTAL_ALLOWANCE, "money", Unit.PER_YEAR, period=True),
    FieldParser(FieldName.OTC_ALLOWANCE, "money", Unit.PER_YEAR, period=True),
)

FAMILIES: dict[str, tuple[FieldParser, ...]] = {
    "cost_sharing": COST_SHARING,
    "drugs": DRUGS,
    "allowances": ALLOWANCES,
}
