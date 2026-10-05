"""Field parsers: one per field, grouped into families. Each turns a table cell into a typed value.

A parser never guesses. Text it cannot read returns None, and the caller sends the field to review.
"""

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from plan_diff import config
from plan_diff.models import Coinsurance, Copay, FieldName, FieldValue, Money, NotCovered, Unit

_MONEY = re.compile(r"\$\s?(\d{1,3}(?:,\d{3})+|\d+)(\.\d{1,2})?")
_PERCENT = re.compile(r"(\d{1,3}(?:\.\d{1,2})?)\s?%")
_NOT_COVERED = re.compile(r"\bnot covered\b", re.IGNORECASE)
_IN_NETWORK = re.compile(r"\bin[- ]network\b", re.IGNORECASE)
_SEGMENT_SPLIT = re.compile(r"[,;/]|\bor\b", re.IGNORECASE)
_DAY_RANGE = re.compile(r"\bdays?\s+\d", re.IGNORECASE)


@dataclass(frozen=True)
class FieldParser:
    field: FieldName
    kind: Literal["money", "copay"]  # what a dollar amount means for this field
    default_unit: Unit
    first_day_range: bool = False  # "$395 per day for days 1 to 5; $0 ..." keeps the first range

    @property
    def label(self) -> re.Pattern[str]:
        return re.compile(config.EXTRACT_LABELS[self.field.value], re.IGNORECASE)


@dataclass(frozen=True)
class Parsed:
    value: FieldValue
    unit: Unit | None
    multiple: bool  # the cell held two or more values; one was chosen by rule


def _tokens(text: str) -> list[tuple[int, Coinsurance | Decimal]]:
    """Every dollar amount (as Decimal) and percent (as Coinsurance), in reading order."""
    found: list[tuple[int, Coinsurance | Decimal]] = []
    for m in _MONEY.finditer(text):
        found.append((m.start(), Decimal(m.group(1).replace(",", "") + (m.group(2) or ""))))
    for m in _PERCENT.finditer(text):
        found.append((m.start(), Coinsurance(percent=Decimal(m.group(1)))))
    return sorted(found, key=lambda t: t[0])


def _unit(text: str, default: Unit) -> Unit:
    lowered = text.lower()
    hits = [(lowered.find(p), u) for p, u in config.EXTRACT_UNIT_PHRASES.items() if p in lowered]
    return Unit(min(hits)[1]) if hits else default


def parse_value(text: str, parser: FieldParser) -> Parsed | None:
    """Read one cell. Two or more values: the in-network one, else the first (lower confidence)."""
    tokens = _tokens(text)
    if not tokens:
        return Parsed(NotCovered(), None, False) if _NOT_COVERED.search(text) else None
    chosen_text = text
    day_ranges = parser.first_day_range and _DAY_RANGE.search(text) is not None
    multiple = len(tokens) > 1 and not day_ranges
    if multiple:
        marked = [s for s in _SEGMENT_SPLIT.split(text) if _IN_NETWORK.search(s) and _tokens(s)]
        chosen_text = marked[0] if marked else text
    token = _tokens(chosen_text)[0][1]
    value: FieldValue
    if isinstance(token, Coinsurance):
        value = token
    elif parser.kind == "money":
        value = Money(amount=token)
    else:
        value = Copay(amount=token)
    return Parsed(value, _unit(chosen_text, parser.default_unit), multiple)


# PR 5: the cost-sharing family. PR 6 adds a drug family and an allowance family beside it.
COST_SHARING: tuple[FieldParser, ...] = (
    FieldParser(FieldName.MONTHLY_PREMIUM, "money", Unit.PER_MONTH),
    FieldParser(FieldName.MEDICAL_DEDUCTIBLE, "money", Unit.PER_YEAR),
    FieldParser(FieldName.MOOP_IN_NETWORK, "money", Unit.PER_YEAR),
    FieldParser(FieldName.PCP_COPAY, "copay", Unit.PER_VISIT),
    FieldParser(FieldName.SPECIALIST_COPAY, "copay", Unit.PER_VISIT),
    FieldParser(FieldName.EMERGENCY_ROOM, "copay", Unit.PER_VISIT),
    FieldParser(FieldName.URGENT_CARE, "copay", Unit.PER_VISIT),
    FieldParser(FieldName.INPATIENT_STAY, "copay", Unit.PER_STAY, first_day_range=True),
    FieldParser(FieldName.OUTPATIENT_SURGERY, "copay", Unit.PER_VISIT),
)

FAMILIES: dict[str, tuple[FieldParser, ...]] = {"cost_sharing": COST_SHARING}
