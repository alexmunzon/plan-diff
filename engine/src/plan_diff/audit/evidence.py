"""Evidence corpus for the audit: each document read once, identified by its SHA-256.

Page text comes from the same pdfplumber call the run uses (run/documents.py), so the audit never
reads a page differently from extraction. Text is untrusted: it is matched, never followed.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

import pdfplumber

from plan_diff.audit.models import DocumentMeta, EvidenceDocument, EvidenceMeta
from plan_diff.models.fields import FieldName
from plan_diff.models.run import RunManifest
from plan_diff.models.validation import ValidationResult
from plan_diff.models.validation import Verdict as ValidationVerdict
from plan_diff.run.documents import PDF_READ_ERRORS, find_pdfs, sha256_file


class AuditRefused(Exception):
    """The audit was refused before anything was written. The message says why."""


@dataclass(frozen=True)
class Limits:
    max_claims: int = 500
    max_document_bytes: int = 50 * 1024 * 1024
    max_pages: int = 2000  # across all documents
    max_input_bytes: int = 2 * 1024 * 1024  # claims and metadata files


DEFAULT_LIMITS = Limits()


@dataclass(frozen=True)
class CmsConflict:
    """A PDF/CMS mismatch the run already recorded in validation.json. Never recomputed here."""

    plan_id: str
    year: int
    field: FieldName
    file: str
    row: int
    reason: str


def cms_conflicts(results: Sequence[ValidationResult]) -> list[CmsConflict]:
    return [
        CmsConflict(
            r.plan_id,
            r.year,
            r.field,
            r.cms_citation.document_id,
            r.cms_citation.page,
            r.reason or "PDF and CMS values differ",
        )
        for r in results
        if r.verdict == ValidationVerdict.MISMATCH and r.cms_citation is not None
    ]


@dataclass
class Corpus:
    documents: dict[str, EvidenceDocument]
    pages: dict[str, tuple[str, ...]]  # sha256 -> page texts, cached by content only
    cms_conflicts: list[CmsConflict] = field(default_factory=list)
    reads: int = 0  # how many PDFs were opened, to show no per-claim rereads
    page_total: int = 0
    _by_id: dict[str, str] = field(default_factory=dict)

    def page_text(self, document_id: str, page: int) -> str | None:
        doc = self.documents.get(document_id)
        if doc is None or not doc.readable:
            return None
        texts = self.pages[doc.sha256]
        return texts[page - 1] if 1 <= page <= len(texts) else None


def _meta_for(meta: EvidenceMeta | None) -> dict[str, DocumentMeta]:
    found = {m.document_id: m for m in (meta.documents if meta else ())}
    if meta and len(found) != len(meta.documents):
        raise AuditRefused("evidence metadata lists a document_id twice")
    return found


def read_pages(path: Path, limits: Limits, pages_left: int) -> tuple[str, ...]:
    """Every page's text. Refuses before extracting any text when the document has more pages
    than the audit's remaining page budget."""
    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) > pages_left:
            raise AuditRefused(f"more than {limits.max_pages} pages across all documents")
        return tuple(page.extract_text() or "" for page in pdf.pages)


@dataclass(frozen=True)
class Declared:
    """A document's recorded identity: from a run manifest input, or a test case."""

    document_id: str
    sha256: str
    plan_id: str | None
    year: int | None
    document_type: str | None


def from_manifest(manifest: RunManifest) -> list[Declared]:
    return [
        Declared(i.document_id, i.sha256, i.plan_id, i.year, i.document_type)
        for i in manifest.inputs
        if i.kind == "pdf" and i.document_id
    ]


def build_corpus(
    declared: Sequence[Declared],
    docs: Path,
    meta: EvidenceMeta | None = None,
    limits: Limits = DEFAULT_LIMITS,
) -> Corpus:
    """Match each declared document to a PDF under `docs` by file name, check its bytes, and read
    its pages once. A missing, changed, or unreadable file stays in the corpus as unreadable."""
    known = _meta_for(meta)
    paths: Mapping[str, Path] = {p.stem: p for p in find_pdfs(docs)} if docs.is_dir() else {}
    corpus = Corpus(documents={}, pages={})
    for d in declared:
        if d.document_id in corpus.documents:
            raise AuditRefused(f"document {d.document_id} is declared twice")
        problem: str | None = None
        size, texts = 0, tuple[str, ...]()
        path = paths.get(d.document_id)
        if path is None:
            problem = "no file with this document id was supplied"
        else:
            size = path.stat().st_size
            if size > limits.max_document_bytes:  # checked before the bytes are even hashed
                raise AuditRefused(f"{path.name} is larger than {limits.max_document_bytes} bytes")
            if sha256_file(path) != d.sha256:
                problem = "the file's bytes differ from the recorded SHA-256"
            elif d.sha256 in corpus.pages:
                texts = corpus.pages[d.sha256]
            else:
                try:
                    texts = read_pages(path, limits, limits.max_pages - corpus.page_total)
                    corpus.reads += 1
                except PDF_READ_ERRORS as error:
                    problem = f"could not open the PDF ({type(error).__name__})"
        if problem is None:
            corpus.page_total += len(texts)
            if corpus.page_total > limits.max_pages:
                raise AuditRefused(f"more than {limits.max_pages} pages across all documents")
            corpus.pages[d.sha256] = texts
        corpus.documents[d.document_id] = EvidenceDocument.model_validate(
            {
                "document_id": d.document_id,
                "sha256": d.sha256,
                "size_bytes": size,
                "page_count": len(texts),
                "plan_id": d.plan_id,
                "year": d.year,
                "document_type": d.document_type,
                "readable": problem is None,
                "problem": problem,
                "meta": known.get(d.document_id, DocumentMeta(document_id=d.document_id)),
            }
        )
    stray = sorted(set(known) - set(corpus.documents))
    if stray:
        raise AuditRefused(f"evidence metadata names documents the run does not have: {stray}")
    return corpus
