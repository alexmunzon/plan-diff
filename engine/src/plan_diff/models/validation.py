"""ValidationResult: one field checked against CMS PBP data. Flag, never pick."""

from enum import StrEnum
from typing import Self

from pydantic import model_validator

from plan_diff.models.citation import Citation
from plan_diff.models.fields import FieldName, FieldValue
from plan_diff.models.ids import PlanId, PlanYear, StrictModel


class Verdict(StrEnum):
    MATCH = "match"
    MISMATCH = "mismatch"
    NOT_IN_CMS = "not_in_cms"
    NOT_EXTRACTED = "not_extracted"


class ValidationResult(StrictModel):
    plan_id: PlanId
    year: PlanYear
    field: FieldName
    pdf_value: FieldValue | None
    cms_value: FieldValue | None
    verdict: Verdict
    pdf_citation: Citation | None  # the PDF page
    cms_citation: Citation | None  # the CMS file row

    @model_validator(mode="after")
    def _verdict_fits_values(self) -> Self:
        has_pdf, has_cms = self.pdf_value is not None, self.cms_value is not None
        ok = {
            Verdict.MATCH: has_pdf and has_cms and self.pdf_value == self.cms_value,
            Verdict.MISMATCH: has_pdf and has_cms and self.pdf_value != self.cms_value,
            Verdict.NOT_IN_CMS: has_pdf and not has_cms,
            Verdict.NOT_EXTRACTED: not has_pdf,
        }[self.verdict]
        if not ok:
            raise ValueError(f"verdict {self.verdict} does not fit the values")
        return self
