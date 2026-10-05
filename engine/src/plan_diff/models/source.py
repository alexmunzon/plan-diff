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
    url: HttpUrl | None  # direct file URL; None until someone finds it by hand
    sha256: Sha256 | None  # None until the file is pinned by its first fetch
    size_bytes: Annotated[StrictInt, Field(ge=1)] | None
    retrieved_at: AwareDatetime | None
    carrier: Carrier
    plan_id: PlanId | None  # None for CMS files that cover every plan
    year: PlanYear
    document_type: DocumentType
    landing_page: HttpUrl | None = None  # where a person finds the file by hand
    verified: bool = False  # True once a person has confirmed the URL serves the right file
    note: str | None = None

    @model_validator(mode="after")
    def _pinned_means_complete(self) -> Self:
        if self.sha256 is not None and (self.size_bytes is None or self.retrieved_at is None):
            raise ValueError("a pinned document needs size_bytes and retrieved_at")
        if self.url is None and (self.sha256 is not None or not self.note):
            raise ValueError("a document without a url cannot be pinned and needs a note")
        if self.plan_id is None and not self.document_type.startswith("CMS_"):
            raise ValueError("a carrier document needs a plan_id")
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
