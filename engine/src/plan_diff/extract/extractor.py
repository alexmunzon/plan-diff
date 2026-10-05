"""Deterministic extraction (SPEC section 6 step 3): find each field's row, parse it, cite the page.

A field that is not found, or whose value cannot be read, is left out and becomes a NOT_EXTRACTED
review item. Two values for one field are never silently resolved: confidence drops and a
CONFLICTING_VALUES review item cites every value seen.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import pdfplumber

from plan_diff import config
from plan_diff.classify import Classification
from plan_diff.extract.values import FAMILIES, FieldParser, Parsed, parse_value
from plan_diff.models import (
    Citation,
    CitationMethod,
    ExtractedField,
    FieldName,
    ReviewItem,
    ReviewKind,
    Severity,
    StrictModel,
)


class ExtractionResult(StrictModel):
    document_id: str
    fields: dict[FieldName, ExtractedField]  # a missing key means "not extracted"
    review_items: tuple[ReviewItem, ...]


@dataclass(frozen=True)
class _Hit:
    page: int
    text: str
    parsed: Parsed | None


def _cite(document_id: str, hit: _Hit) -> Citation:
    snippet = hit.text[: config.EXTRACT_SNIPPET_CHARS] or None
    return Citation(
        document_id=document_id, page=hit.page, method=CitationMethod.RULE, text=snippet
    )


def _hits(pages: Sequence[list[str]], parser: FieldParser) -> list[_Hit]:
    hits: list[_Hit] = []
    for page_number, lines in enumerate(pages, start=1):
        for index, line in enumerate(lines):
            m = parser.label.match(line)
            if m is None:
                continue
            cell = line[m.end() :].strip(" :")
            if not cell and index + 1 < len(lines):
                cell = lines[index + 1]  # value wrapped onto the next line
            hits.append(_Hit(page_number, cell, parse_value(cell, parser)))
    return hits


def extract_pages(page_texts: Sequence[str], classification: Classification) -> ExtractionResult:
    """Extract every field that has a parser from already extracted page text, page 1 first."""
    document_id = classification.document_id
    pages = [[ln.strip() for ln in text.splitlines() if ln.strip()] for text in page_texts]
    year = classification.year.value
    fields: dict[FieldName, ExtractedField] = {}
    review: list[ReviewItem] = []

    def flag(field: FieldName, kind: ReviewKind, evidence: list[_Hit], reason: str) -> None:
        review.append(
            ReviewItem(
                kind=kind,
                plan_id=classification.plan_id.value,
                year=int(year) if year is not None else None,
                field=field,
                evidence=tuple(_cite(document_id, h) for h in evidence),
                reason=reason,
                severity=Severity.LOW if kind is ReviewKind.CONFLICTING_VALUES else Severity.MEDIUM,
            )
        )

    for parser in (p for family in FAMILIES.values() for p in family):
        name = parser.field
        all_hits = _hits(pages, parser)
        read = [h for h in all_hits if h.parsed is not None]
        if not all_hits:
            flag(name, ReviewKind.NOT_EXTRACTED, [], f"no row found on any of {len(pages)} pages")
            continue
        if not read:
            texts = ", ".join(f"'{h.text}' (page {h.page})" for h in all_hits)
            flag(
                name, ReviewKind.NOT_EXTRACTED, all_hits, f"row found but value unreadable: {texts}"
            )
            continue
        distinct: dict[tuple[object, object], _Hit] = {}
        for h in read:
            assert h.parsed is not None
            distinct.setdefault((h.parsed.value, h.parsed.unit), h)
        first = read[0]
        assert first.parsed is not None
        confidence = config.EXTRACT_CONFIDENCE_RULE
        if len(distinct) > 1:
            confidence = config.EXTRACT_CONFIDENCE_CONFLICT
            seen = ", ".join(f"'{h.text}' (page {h.page})" for h in distinct.values())
            reason = f"two or more different values: {seen}; kept page {first.page}"
            flag(name, ReviewKind.CONFLICTING_VALUES, list(distinct.values()), reason)
        elif first.parsed.multiple:
            confidence = config.EXTRACT_CONFIDENCE_MULTIPLE
            picked = first.parsed.picked
            reason = f"two or more values in one cell: '{first.text}'; took the {picked} value"
            flag(name, ReviewKind.CONFLICTING_VALUES, [first], reason)
        fields[name] = ExtractedField(
            name=name,
            value=first.parsed.value,
            unit=first.parsed.unit,
            citation=_cite(document_id, first),
            confidence=confidence,
        )
    return ExtractionResult(document_id=document_id, fields=fields, review_items=tuple(review))


def extract_document(path: Path, classification: Classification) -> ExtractionResult:
    """Extract from a PDF. Citations use the classification's document id."""
    with pdfplumber.open(path) as pdf:
        texts = [page.extract_text() or "" for page in pdf.pages]
    return extract_pages(texts, classification)
