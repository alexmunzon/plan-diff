"""PlanRecord: one plan in one year, every field cited."""

from typing import Self

from pydantic import model_validator

from plan_diff.models.citation import CitationMethod
from plan_diff.models.fields import ExtractedField, FieldName
from plan_diff.models.ids import Carrier, NonEmpty, PlanId, PlanYear, StrictModel


class PlanRecord(StrictModel):
    plan_id: PlanId
    year: PlanYear
    carrier: Carrier
    plan_name: NonEmpty
    counties: tuple[NonEmpty, ...]  # service area
    fields: dict[FieldName, ExtractedField]  # a missing key means "not extracted"
    documents: tuple[NonEmpty, ...]  # SourceDocument ids this record was read from

    @model_validator(mode="after")
    def _keys_and_citations_line_up(self) -> Self:
        for key, field in self.fields.items():
            if key != field.name:
                raise ValueError(f"fields[{key}] holds {field.name}")
            from_pdf = field.citation.method in (CitationMethod.RULE, CitationMethod.LLM)
            if from_pdf and field.citation.document_id not in self.documents:
                raise ValueError(f"{key} cites {field.citation.document_id}, not in documents")
        return self
