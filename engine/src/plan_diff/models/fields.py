"""The 15 v1 fields (SPEC decision 3) and their typed values.

Money is Decimal, never float: a float is refused outright, and amounts keep 2 decimal places.
"""

from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import AfterValidator, BeforeValidator, Field

from plan_diff.models.citation import Citation
from plan_diff.models.ids import StrictModel

CENT = Decimal("0.01")


def _refuse_float(value: Any) -> Any:
    if isinstance(value, float | bool):
        raise ValueError("money must be a Decimal, int, or string, never a float")
    return value


Amount = Annotated[
    Decimal,
    BeforeValidator(_refuse_float),
    Field(ge=0, max_digits=12, decimal_places=2),
    AfterValidator(lambda v: v.quantize(CENT)),
]
Percent = Annotated[Decimal, BeforeValidator(_refuse_float), Field(ge=0, le=100, decimal_places=2)]


class FieldName(StrEnum):
    MONTHLY_PREMIUM = "monthly_premium"
    MEDICAL_DEDUCTIBLE = "medical_deductible"
    MOOP_IN_NETWORK = "moop_in_network"  # maximum out-of-pocket, in network
    PCP_COPAY = "pcp_copay"
    SPECIALIST_COPAY = "specialist_copay"
    EMERGENCY_ROOM = "emergency_room"
    URGENT_CARE = "urgent_care"
    INPATIENT_STAY = "inpatient_stay"
    OUTPATIENT_SURGERY = "outpatient_surgery"
    DRUG_DEDUCTIBLE = "drug_deductible"
    DRUG_TIER_1 = "drug_tier_1"
    DRUG_TIER_2 = "drug_tier_2"
    DRUG_TIER_3 = "drug_tier_3"
    DENTAL_ALLOWANCE = "dental_allowance"
    OTC_ALLOWANCE = "otc_allowance"


class Unit(StrEnum):
    PER_VISIT = "per_visit"
    PER_DAY = "per_day"
    PER_STAY = "per_stay"
    PER_MONTH = "per_month"
    PER_QUARTER = "per_quarter"  # PR 6: OTC allowances are often paid every quarter
    PER_YEAR = "per_year"
    PER_PRESCRIPTION = "per_prescription"


# How many times a period repeats in a plan year. Units that are not a period are left out.
PERIODS_PER_YEAR: dict[Unit, int] = {Unit.PER_MONTH: 12, Unit.PER_QUARTER: 4, Unit.PER_YEAR: 1}


def annualize(value: Decimal | int, unit: Unit) -> Decimal:
    """A per-month, per-quarter, or per-year amount as a yearly amount: $50 a quarter is $200."""
    _refuse_float(value)
    if unit not in PERIODS_PER_YEAR:
        raise ValueError(f"{unit.value} is not a period, so it cannot be made yearly")
    return Decimal(value) * PERIODS_PER_YEAR[unit]


class Money(StrictModel):
    """A dollar amount such as a premium, deductible, MOOP, or allowance."""

    kind: Literal["money"] = "money"
    amount: Amount


class Copay(StrictModel):
    """A fixed dollar amount per unit (the unit lives on ExtractedField)."""

    kind: Literal["copay"] = "copay"
    amount: Amount


class Coinsurance(StrictModel):
    """A percent of the cost, 0 to 100."""

    kind: Literal["coinsurance"] = "coinsurance"
    percent: Percent


class NotCovered(StrictModel):
    kind: Literal["not_covered"] = "not_covered"


FieldValue = Annotated[Money | Copay | Coinsurance | NotCovered, Field(discriminator="kind")]


class ExtractedField(StrictModel):
    name: FieldName
    value: FieldValue
    unit: Unit | None  # None when the value has no unit, for example "not covered"
    citation: Citation
    confidence: Annotated[float, Field(ge=0, le=1)]  # a score, not money
