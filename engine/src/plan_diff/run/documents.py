"""Run step 1: find every PDF, classify it, extract it, and merge one record per plan year.

A PDF that cannot be opened (corrupt, password protected) or cannot be classified goes to review;
it never stops the run. Jev and the LLM are off, so the rules are the only reader (SPEC example 8).
"""

import hashlib
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from pdfminer.pdfdocument import PDFPasswordIncorrect
from pdfminer.pdfexceptions import PDFException
from pdfminer.psexceptions import PSException
from pdfplumber.utils.exceptions import MalformedPDFException, PdfminerException
from pypdf.errors import PdfReadError

from plan_diff import config
from plan_diff.classify import Classification, ClassifyStatus, classify_pdf, document_type_of
from plan_diff.extract import ExtractionResult, extract_document
from plan_diff.models import (
    Citation,
    CitationMethod,
    ExtractedField,
    FieldName,
    ReviewItem,
    ReviewKind,
    RunInput,
    Severity,
)


class RunRefused(Exception):
    """The run was refused before anything was written. The message says why."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run_input(kind: str, path: Path, root: Path, **extra: object) -> RunInput:
    return RunInput.model_validate(
        {
            "kind": kind,
            "path": path.relative_to(root).as_posix(),
            "sha256": sha256_file(path),
            "size_bytes": path.stat().st_size,
            **extra,
        }
    )


@dataclass
class Document:
    path: Path
    classification: Classification
    extraction: ExtractionResult


@dataclass
class DocumentsStep:
    inputs: list[RunInput] = field(default_factory=list)
    documents: list[Document] = field(default_factory=list)  # classified, in the slice
    review: list[ReviewItem] = field(default_factory=list)  # document-level problems


def find_pdfs(docs: Path) -> list[Path]:
    """Every .pdf under `docs`, sorted by relative path, so runs are deterministic."""
    found = [p for p in docs.rglob("*") if p.is_file() and p.suffix.lower() == ".pdf"]
    return sorted(found, key=lambda p: p.relative_to(docs).as_posix())


# Only the PDF libraries' own read errors (corrupt, truncated, encrypted, wrong password) send a
# document to review. Any other exception is a bug in our code and fails the run loudly.
PDF_READ_ERRORS: tuple[type[Exception], ...] = (
    PDFPasswordIncorrect,
    PDFException,
    PSException,
    PdfminerException,
    MalformedPDFException,
    PdfReadError,
)


def _unreadable(document_id: str, error: Exception) -> ReviewItem:
    return ReviewItem(
        kind=ReviewKind.UNCLASSIFIED_DOCUMENT,
        plan_id=None,
        year=None,
        field=None,
        evidence=(Citation(document_id=document_id, page=1, method=CitationMethod.RULE),),
        reason=f"could not open the PDF ({type(error).__name__}): it may be corrupt or password "
        "protected",
        severity=Severity.HIGH,
    )


def read_documents(docs: Path, plans: Sequence[str], years: Sequence[int]) -> DocumentsStep:
    step = DocumentsStep()
    paths = find_pdfs(docs)
    ids = [p.stem for p in paths]
    repeated = sorted({i for i in ids if ids.count(i) > 1})
    if repeated:
        raise RunRefused(f"two PDFs share a file name, so their citations would clash: {repeated}")
    for path in paths:
        try:
            result = classify_pdf(path, document_id=path.stem)
            extraction = None
            if result.status is ClassifyStatus.SURE:
                extraction = extract_document(path, result)
        except PDF_READ_ERRORS as error:
            step.review.append(_unreadable(path.stem, error))
            step.inputs.append(
                run_input("pdf", path, docs, status="unreadable", document_id=path.stem)
            )
            continue
        plan_id, year = result.plan_id.value, result.year.value
        status = "classified"
        if extraction is None:
            status = "unsure"
            assert result.review_item is not None
            step.review.append(result.review_item)
        elif plan_id not in plans or int(year or 0) not in years:
            status = "outside_slice"
        else:
            step.documents.append(Document(path, result, extraction))
        step.inputs.append(
            run_input(
                "pdf",
                path,
                docs,
                status=status,
                document_id=path.stem,
                plan_id=plan_id,
                year=int(year) if year else None,
                document_type=document_type_of(result),
            )
        )
    return step


def _priority(doc: Document) -> int:
    kind = document_type_of(doc.classification)
    return config.RUN_DOCUMENT_PRIORITY.index(kind.value if kind else "OTHER")


def merge_fields(
    docs: Iterable[Document],
) -> tuple[dict[FieldName, ExtractedField], list[ReviewItem]]:
    """One value per field from the highest priority document that has it (SB, then EOC, then
    ANOC). Another document with a different value is never silently dropped: it goes to review.
    A field is reported missing only when no document had it."""
    ordered = sorted(docs, key=_priority)
    fields: dict[FieldName, ExtractedField] = {}
    review: list[ReviewItem] = []
    for name in FieldName:
        found = [d.extraction.fields[name] for d in ordered if name in d.extraction.fields]
        if found:
            fields[name] = found[0]
            others = [f for f in found[1:] if (f.value, f.unit) != (found[0].value, found[0].unit)]
            if others:
                review.append(_cross_document(name, found[0], others, ordered[0].classification))
    reported_missing: set[FieldName | None] = set()
    for doc in ordered:
        for item in doc.extraction.review_items:
            if item.kind is ReviewKind.NOT_EXTRACTED:
                if item.field in fields or item.field in reported_missing:
                    continue  # another document had it, or it is already reported
                reported_missing.add(item.field)
            review.append(item)
    return fields, review


def _cross_document(
    name: FieldName, kept: ExtractedField, others: list[ExtractedField], c: Classification
) -> ReviewItem:
    pages = ", ".join(f"{f.citation.document_id} page {f.citation.page}" for f in others)
    return ReviewItem(
        kind=ReviewKind.CONFLICTING_VALUES,
        plan_id=c.plan_id.value,
        year=int(c.year.value) if c.year.value else None,
        field=name,
        evidence=(kept.citation, *(f.citation for f in others)),
        reason=f"documents disagree: kept {kept.citation.document_id} page {kept.citation.page}, "
        f"a different value is on {pages}",
        severity=Severity.MEDIUM,
    )
