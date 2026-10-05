"""Citation: where a value came from. A value without a citation is not a value."""

from enum import StrEnum
from typing import Annotated

from pydantic import Field, StrictInt

from plan_diff.models.ids import NonEmpty, StrictModel


class CitationMethod(StrEnum):
    RULE = "rule"  # deterministic parser
    LLM = "llm"  # LLM fallback, off by default
    CMS = "cms"  # CMS public use file; page is the 1-based row number in that file
    HUMAN = "human"  # set by a reviewer


class Citation(StrictModel):
    document_id: NonEmpty  # SourceDocument.document_id, or the CMS file name
    page: Annotated[StrictInt, Field(ge=1)]  # 1-based
    method: CitationMethod
    text: Annotated[str, Field(max_length=200)] | None = None  # short snippet, never a full page
