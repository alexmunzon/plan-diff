"""Sources manifest: which public documents exist, and the hash each must match."""

from typing import Annotated, Literal, Self

from pydantic import AwareDatetime, Field, HttpUrl, StrictInt, model_validator

from plan_diff.models.ids import (
    Carrier,
    DocumentType,
    NonEmpty,
    PlanId,
    PlanYear,
    Sha256,
    StrictModel,
)


class SourceDocument(StrictModel):
    document_id: NonEmpty
    url: HttpUrl
    sha256: Sha256 | None  # None until the file is pinned by its first fetch
    size_bytes: Annotated[StrictInt, Field(ge=1)] | None
    retrieved_at: AwareDatetime | None
    carrier: Carrier
    plan_id: PlanId
    year: PlanYear
    document_type: DocumentType

    @model_validator(mode="after")
    def _pinned_means_complete(self) -> Self:
        if self.sha256 is not None and (self.size_bytes is None or self.retrieved_at is None):
            raise ValueError("a pinned document needs size_bytes and retrieved_at")
        return self


class SourcesManifest(StrictModel):
    schema_version: Literal[1] = 1
    documents: tuple[SourceDocument, ...]

    @model_validator(mode="after")
    def _ids_unique(self) -> Self:
        ids = [d.document_id for d in self.documents]
        if len(ids) != len(set(ids)):
            raise ValueError("document_id values must be unique")
        return self
