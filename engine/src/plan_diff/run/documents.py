"""Run step 1: find every PDF, classify it, extract it, and merge one record per plan year.

A PDF that cannot be opened (corrupt, password protected) or cannot be classified goes to review;
it never stops the run. Jev and the LLM are off, so the rules are the only reader (SPEC example 8).
"""

import hashlib
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

import pdfplumber
from pdfminer.pdfdocument import PDFPasswordIncorrect
from pdfminer.pdfexceptions import PDFException
from pdfminer.psexceptions import PSException
from pdfplumber.utils.exceptions import MalformedPDFException, PdfminerException
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from plan_diff import config
from plan_diff.classify import (
    Classification,
    ClassifyStatus,
    Finding,
    classify_pages,
    document_type_of,
)
from plan_diff.classify.booklet import BookletResult, mask_pages, plan_pages, plans_named
from plan_diff.extract import ExtractionResult, extract_pages
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


def run_input(
    kind: str, path: Path, root: Path, urls: Mapping[str, str] | None = None, **extra: object
) -> RunInput:
    """`urls` maps a pinned SHA-256 to its https source URL (PR 14); only PDFs look it up."""
    sha = sha256_file(path)
    url = (urls or {}).get(sha) if kind == "pdf" else None
    return RunInput.model_validate(
        {
            "kind": kind,
            "path": path.relative_to(root).as_posix(),
            "sha256": sha,
            "size_bytes": path.stat().st_size,
            "source_url": url,
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


def _booklet_problem(document_id: str, c: Classification, why: str) -> ReviewItem:
    return ReviewItem(
        kind=ReviewKind.UNCLASSIFIED_DOCUMENT,
        plan_id=c.plan_id.value,
        year=int(c.year.value) if c.year.value else None,
        field=None,
        evidence=(Citation(document_id=document_id, page=1, method=CitationMethod.RULE),),
        reason=why,
        severity=Severity.MEDIUM,
    )


def _only_plan_id_ambiguous(c: Classification) -> bool:
    others = (c.document_type, c.year, c.carrier)
    return c.plan_id.problem == "ambiguous" and all(f.problem is None for f in others)


def _for_plan(c: Classification, plan_id: str, page: int) -> Classification:
    """PR 15: a booklet's classification narrowed to one requested plan, cited to its first page."""
    cite = Citation(document_id=c.document_id, page=page, method=CitationMethod.RULE, text=plan_id)
    finding = Finding(
        value=plan_id, confidence=config.CONFIDENCE_BODY, evidence=(cite,), problem=None
    )
    return c.model_copy(
        update={"status": ClassifyStatus.SURE, "plan_id": finding, "review_item": None}
    )


def _cite_pages(extraction: ExtractionResult, booklet: BookletResult) -> ExtractionResult:
    """Every citation from a booklet says which pages were read for this plan."""
    if booklet.pages is None:
        return extraction
    prefix = f"booklet pages {booklet.pages} for {booklet.plan_id}: "
    fields = {
        name: f.model_copy(
            update={
                "citation": f.citation.model_copy(
                    update={"text": (prefix + (f.citation.text or ""))[:200]}
                )
            }
        )
        for name, f in extraction.fields.items()
    }
    return extraction.model_copy(update={"fields": fields})


def _targets(
    result: Classification, texts: Sequence[str], plans: Sequence[str]
) -> tuple[list[tuple[Classification, BookletResult]], list[str]]:
    """The (classification, pages) to extract for each requested plan in one document, and the
    problems that send it to review instead (PR 15 booklets)."""
    if result.status is ClassifyStatus.SURE and result.plan_id.value is not None:
        candidates = [result.plan_id.value]
    elif _only_plan_id_ambiguous(result):
        named = set().union(*(plans_named(t) for t in texts))
        candidates = sorted(named & set(plans))
    else:
        return [], []
    targets, problems = [], []
    for plan_id in candidates:
        booklet = plan_pages(texts, plan_id)
        if booklet.problem:
            problems.append(booklet.problem)
            continue
        first = booklet.pages.first if booklet.pages else result.plan_id.page or 1
        narrowed = result if booklet.pages is None else _for_plan(result, plan_id, first)
        targets.append((narrowed, booklet))
    return targets, problems


def read_documents(
    docs: Path, plans: Sequence[str], years: Sequence[int], urls: Mapping[str, str] | None = None
) -> DocumentsStep:
    step = DocumentsStep()
    paths = find_pdfs(docs)
    ids = [p.stem for p in paths]
    repeated = sorted({i for i in ids if ids.count(i) > 1})
    if repeated:
        raise RunRefused(f"two PDFs share a file name, so their citations would clash: {repeated}")
    for path in paths:
        try:
            with pdfplumber.open(path) as pdf:
                texts = [page.extract_text() or "" for page in pdf.pages]
            result = classify_pages(texts[: config.CLASSIFY_FIRST_PAGES], document_id=path.stem)
            page_count = len(PdfReader(path).pages)
            targets, problems = _targets(result, texts, plans)
            extracted = [
                (c, b, _cite_pages(extract_pages(mask_pages(texts, b.pages), c), b))
                for c, b in targets
            ]
        except PDF_READ_ERRORS as error:
            step.review.append(_unreadable(path.stem, error))
            step.inputs.append(
                run_input("pdf", path, docs, urls, status="unreadable", document_id=path.stem)
            )
            continue
        status = "classified"
        used = [
            (c, e)
            for c, _, e in extracted
            if c.plan_id.value in plans and int(c.year.value or 0) in years
        ]
        if problems:
            status = "unsure"
            step.review.append(_booklet_problem(path.stem, result, "; ".join(problems)))
        elif not extracted:
            status = "unsure"
            assert result.review_item is not None
            step.review.append(result.review_item)
        elif not used:
            status = "outside_slice"
        for c, e in used if not problems else []:
            step.documents.append(Document(path, c, e))
        booklets = [f"{b.plan_id}: pages {b.pages}" for _, b, _ in extracted if b.pages]
        shown = used[0][0] if len(used) == 1 else result
        plan_id, year = shown.plan_id.value, shown.year.value
        step.inputs.append(
            run_input(
                "pdf",
                path,
                docs,
                urls,
                status=status,
                page_count=page_count or None,
                document_id=path.stem,
                plan_id=plan_id,
                year=int(year) if year else None,
                document_type=document_type_of(result),
                plan_pages="; ".join(booklets) or None,
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
