"""ValidationResult: one field checked against CMS PBP data. Flag, never pick."""

from enum import StrEnum
from typing import Self

from pydantic import model_validator

from plan_diff.models.citation import Citation, CitationMethod
from plan_diff.models.fields import PERIODS_PER_YEAR, FieldName, FieldValue, Money, Unit, annualize
from plan_diff.models.ids import PlanId, PlanYear, StrictModel

# PR 7: allowances may state different periods ($50 a quarter, $200 a year); they compare yearly.
ALLOWANCE_FIELDS = frozenset({FieldName.DENTAL_ALLOWANCE, FieldName.OTC_ALLOWANCE})


class Verdict(StrEnum):
    MATCH = "match"
    MISMATCH = "mismatch"
    NOT_IN_CMS = "not_in_cms"
    NOT_EXTRACTED = "not_extracted"


def disagreement(
    field: FieldName,
    pdf: FieldValue,
    pdf_unit: Unit | None,
    cms: FieldValue,
    cms_unit: Unit | None,
) -> str | None:
    """Why a PDF value and a CMS value disagree, or None when they agree (PR 7 rules).

    Money is exact to the cent. A copay never equals a coinsurance. Not covered equals not covered.
    Allowances compare after annualize() when both name a period. Other fields: when both name a
    unit, the units must be the same.
    """
    if pdf.kind != cms.kind:
        return f"PDF has a {pdf.kind} value, CMS has a {cms.kind} value"
    if field in ALLOWANCE_FIELDS and isinstance(pdf, Money) and isinstance(cms, Money):
        if pdf_unit is None or cms_unit is None:
            return "period not comparable"
        if pdf_unit not in PERIODS_PER_YEAR or cms_unit not in PERIODS_PER_YEAR:
            return "period not comparable"
        if annualize(pdf.amount, pdf_unit) != annualize(cms.amount, cms_unit):
            return "yearly amounts differ"
        return None
    if pdf != cms:
        return "values differ"
    if pdf_unit is not None and cms_unit is not None and pdf_unit != cms_unit:
        return "units differ"
    return None


class ValidationResult(StrictModel):
    plan_id: PlanId
    year: PlanYear
    field: FieldName
    pdf_value: FieldValue | None
    cms_value: FieldValue | None
    verdict: Verdict
    pdf_citation: Citation | None  # the PDF page
    cms_citation: Citation | None  # the CMS file row
    pdf_unit: Unit | None = None  # PR 7
    cms_unit: Unit | None = None  # PR 7
    reason: str | None = None  # PR 7: why a mismatch is a mismatch

    @model_validator(mode="after")
    def _verdict_fits_values(self) -> Self:
        pdf, cms = self.pdf_value, self.cms_value
        why = None
        if pdf is not None and cms is not None:
            why = disagreement(self.field, pdf, self.pdf_unit, cms, self.cms_unit)
        ok = {
            Verdict.MATCH: pdf is not None and cms is not None and why is None,
            Verdict.MISMATCH: why is not None,
            Verdict.NOT_IN_CMS: pdf is not None and cms is None,
            Verdict.NOT_EXTRACTED: pdf is None,
        }[self.verdict]
        if not ok:
            raise ValueError(f"verdict {self.verdict} does not fit the values")
        return self


class AccuracyRow(StrictModel):
    """PR 7: one field and one extraction method. match_rate is over comparable fields only."""

    field: FieldName | None  # None for the all-fields total of a method
    method: CitationMethod
    matched: int
    mismatched: int
    not_extracted: int
    not_in_cms: int
    match_rate: float | None  # matched / (matched + mismatched); None when nothing compared


class AccuracyTable(StrictModel):
    """PR 7: accuracy.json. One row per field and method, then one total row per method."""

    rows: tuple[AccuracyRow, ...]
