"""Deterministic extraction (SPEC section 6 step 3): find each field's row, parse it, cite the page.

A field that is not found, or whose value cannot be read, is left out and becomes a NOT_EXTRACTED
review item. Two values for one field are never silently resolved: confidence drops and a
CONFLICTING_VALUES review item cites every value seen.
"""

import re
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


_ANY_LABEL = [re.compile(p, re.IGNORECASE) for p in config.EXTRACT_LABELS.values()]
_DRUG_HEADING = re.compile(config.EXTRACT_DRUG_SECTION_HEADING, re.IGNORECASE)
_MEDICAL_HEADING = re.compile(config.EXTRACT_MEDICAL_SECTION_HEADING, re.IGNORECASE)
_AMOUNT = re.compile(r"[$%\d]")


def _is_label(line: str) -> bool:
    return any(label.match(line) for label in _ANY_LABEL)


def _drug_section_flags(pages: Sequence[list[str]]) -> list[list[bool]]:
    """For each line, whether it sits inside a drug section (Review 2). A heading is a whole line
    with no amount that is not a field label; the section runs across pages until a medical one."""
    in_drug, flags = False, []
    for lines in pages:
        page_flags = []
        for line in lines:
            if not _AMOUNT.search(line) and not _is_label(line):
                if _DRUG_HEADING.match(line):
                    in_drug = True
                elif _MEDICAL_HEADING.match(line):
                    in_drug = False
            page_flags.append(in_drug)
        flags.append(page_flags)
    return flags


def _hits(
    pages: Sequence[list[str]], parser: FieldParser, drug_flags: list[list[bool]]
) -> list[_Hit]:
    scoped = config.EXTRACT_DRUG_SECTION_LABELS.get(parser.field.value)
    drug_label = re.compile(scoped, re.IGNORECASE) if scoped else parser.label
    hits: list[_Hit] = []
    for page_number, lines in enumerate(pages, start=1):
        for index, line in enumerate(lines):
            label = drug_label if drug_flags[page_number - 1][index] else parser.label
            m = label.match(line)
            if m is None:
                continue
            cell = line[m.end() :].strip(" :")
            # A value wrapped onto the next line, unless that line is another field's row.
            if not cell and index + 1 < len(lines) and not _is_label(lines[index + 1]):
                cell = lines[index + 1]
            hits.append(_Hit(page_number, cell, parse_value(cell, parser) if cell else None))
    return hits


def extract_pages(page_texts: Sequence[str], classification: Classification) -> ExtractionResult:
    """Extract every field that has a parser from already extracted page text, page 1 first."""
    document_id = classification.document_id
    pages = [[ln.strip() for ln in text.splitlines() if ln.strip()] for text in page_texts]
    drug_flags = _drug_section_flags(pages)
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
        all_hits = _hits(pages, parser, drug_flags)
        read = [h for h in all_hits if h.parsed is not None]
        unread = [h for h in all_hits if h.parsed is None]
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
        if len(distinct) > 1 or unread:
            # An unreadable row beside a readable one is a conflict too, never a silent pick.
            confidence = config.EXTRACT_CONFIDENCE_CONFLICT
            evidence = [*distinct.values(), *unread]
            seen = ", ".join(f"'{h.text}' (page {h.page})" for h in evidence)
            reason = f"two or more different values: {seen}; kept page {first.page}"
            if unread:
                reason += "; a row with no readable value may hold a different one"
            flag(name, ReviewKind.CONFLICTING_VALUES, evidence, reason)
        elif first.parsed.multiple:
            confidence = config.EXTRACT_CONFIDENCE_MULTIPLE
            picked = first.parsed.picked
            reason = f"two or more values in one cell: '{first.text}'; took the {picked} value"
            flag(name, ReviewKind.CONFLICTING_VALUES, [first], reason)
        if first.parsed.unknown_period:
            confidence = min(confidence, config.EXTRACT_CONFIDENCE_UNKNOWN_PERIOD)
            reason = (
                f"period '{first.parsed.unknown_period}' not recognized in '{first.text}'; "
                "amount kept with no unit, so it cannot be made yearly"
            )
            flag(name, ReviewKind.UNKNOWN_PERIOD, [first], reason)
        if first.parsed.ambiguous:
            confidence = min(confidence, config.EXTRACT_CONFIDENCE_AMBIGUOUS_DIGIT)
            reason = (
                f"'{first.parsed.ambiguous}' in '{first.text}': a digit after the amount may be a "
                "footnote marker or part of the number; kept the amount without it"
            )
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
