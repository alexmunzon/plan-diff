"""Deterministic document classifier: plan id, plan year, document type, and carrier.

Reads the first pages' text with pdfplumber. Each attribute is looked for in the title lines
first, then in body text. One value is a finding with a page citation; none or two different
values make the whole document UNSURE and produce a ReviewItem (Jev arrives in PR 10).
"""

import re
from collections.abc import Callable, Mapping, Sequence
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Literal

import pdfplumber
from pydantic import Field

from plan_diff import config
from plan_diff.models import (
    Citation,
    CitationMethod,
    DocumentType,
    ReviewItem,
    ReviewKind,
    Severity,
    StrictModel,
    normalize_plan_id,
)

# One hit on a line: (canonical value, text as it appears in the document).
Extractor = Callable[[str], list[tuple[str, str]]]


class ClassifyStatus(StrEnum):
    SURE = "sure"
    UNSURE = "unsure"


class Finding(StrictModel):
    value: str | None  # None when missing or ambiguous
    confidence: Annotated[float, Field(ge=0, le=1)]
    evidence: tuple[Citation, ...]  # first page of each distinct value seen
    problem: Literal["missing", "ambiguous"] | None

    @property
    def page(self) -> int | None:
        return self.evidence[0].page if self.value is not None else None


class Classification(StrictModel):
    document_id: str
    status: ClassifyStatus
    document_type: Finding
    plan_id: Finding
    year: Finding
    carrier: Finding
    review_item: ReviewItem | None  # set exactly when status is UNSURE


def _regex_extractor(pattern: str, canonical: Callable[[str], str] = str) -> Extractor:
    compiled = re.compile(pattern)
    return lambda line: [(canonical(m.group(1)), m.group(0)) for m in compiled.finditer(line)]


def _phrase_extractor(table: Mapping[str, str]) -> Extractor:
    compiled = [
        (re.compile(rf"\b{re.escape(phrase)}\b", re.IGNORECASE), value)
        for phrase, value in table.items()
    ]
    return lambda line: [(value, m.group(0)) for rx, value in compiled for m in rx.finditer(line)]


def _find(pages: Sequence[list[str]], extract: Extractor, document_id: str) -> Finding:
    title: list[tuple[str, int, str]] = []
    body: list[tuple[str, int, str]] = []
    for page_number, lines in enumerate(pages, start=1):
        for index, line in enumerate(lines):
            in_title = page_number == 1 and index < config.CLASSIFY_TITLE_LINES
            hits = [(value, page_number, seen) for value, seen in extract(line)]
            (title if in_title else body).extend(hits)
    hits, confidence = (title, config.CONFIDENCE_TITLE) if title else (body, config.CONFIDENCE_BODY)
    first: dict[str, Citation] = {}
    for value, page, seen in hits:
        first.setdefault(
            value,
            Citation(document_id=document_id, page=page, method=CitationMethod.RULE, text=seen),
        )
    evidence = tuple(first.values())
    if not first:
        return Finding(
            value=None, confidence=config.CONFIDENCE_MISSING, evidence=(), problem="missing"
        )
    if len(first) > 1:
        return Finding(
            value=None,
            confidence=config.CONFIDENCE_AMBIGUOUS,
            evidence=evidence,
            problem="ambiguous",
        )
    return Finding(value=next(iter(first)), confidence=confidence, evidence=evidence, problem=None)


def _reason(label: str, finding: Finding) -> str:
    if finding.problem == "missing":
        return f"{label}: not found in the first {config.CLASSIFY_FIRST_PAGES} pages"
    values = ", ".join(c.text or "" for c in finding.evidence)
    return f"{label}: two or more different values found ({values})"


def classify_pages(
    page_texts: Sequence[str],
    *,
    document_id: str,
    carrier_aliases: Mapping[str, str] | None = None,
) -> Classification:
    """Classify from already extracted page text, page 1 first."""
    pages = [[ln.strip() for ln in text.splitlines() if ln.strip()] for text in page_texts]
    aliases = config.CARRIER_ALIASES if carrier_aliases is None else carrier_aliases
    findings = {
        "document type": _find(pages, _phrase_extractor(config.DOCUMENT_TYPE_PHRASES), document_id),
        "plan id": _find(
            pages, _regex_extractor(config.PLAN_ID_PATTERN, normalize_plan_id), document_id
        ),
        "plan year": _find(pages, _regex_extractor(config.PLAN_YEAR_PATTERN), document_id),
        "carrier": _find(pages, _phrase_extractor(aliases), document_id),
    }
    doc_type, plan_id, year, carrier = findings.values()
    problems = {label: f for label, f in findings.items() if f.problem is not None}
    review_item = None
    if problems:
        evidence = tuple(c for f in findings.values() for c in f.evidence) or (
            Citation(document_id=document_id, page=1, method=CitationMethod.RULE),
        )
        review_item = ReviewItem(
            kind=ReviewKind.UNCLASSIFIED_DOCUMENT,
            plan_id=plan_id.value,
            year=int(year.value) if year.value is not None else None,
            field=None,
            evidence=evidence,
            reason="; ".join(_reason(label, f) for label, f in problems.items()),
            severity=Severity.MEDIUM,
        )
    return Classification(
        document_id=document_id,
        status=ClassifyStatus.UNSURE if problems else ClassifyStatus.SURE,
        document_type=doc_type,
        plan_id=plan_id,
        year=year,
        carrier=carrier,
        review_item=review_item,
    )


def classify_pdf(
    path: Path,
    *,
    document_id: str | None = None,
    carrier_aliases: Mapping[str, str] | None = None,
) -> Classification:
    """Classify a PDF from its first pages. A scanned PDF with no text comes back UNSURE."""
    with pdfplumber.open(path) as pdf:
        texts = [page.extract_text() or "" for page in pdf.pages[: config.CLASSIFY_FIRST_PAGES]]
    return classify_pages(
        texts, document_id=document_id or path.stem, carrier_aliases=carrier_aliases
    )


def document_type_of(result: Classification) -> DocumentType | None:
    """The document type as the schema enum, or None when it was not found."""
    value = result.document_type.value
    return DocumentType(value) if value is not None else None
