"""Compare each extracted field with its CMS value, count accuracy, and write the review queue.

The comparison rules live in plan_diff.models.disagreement, so a ValidationResult can never hold a
verdict its values do not support. A mismatch keeps both values and both citations and goes to
review with low confidence; nothing here chooses which source is right.
"""

import json
from collections.abc import Iterable, Mapping
from decimal import Decimal
from pathlib import Path

import polars as pl

from plan_diff import config
from plan_diff.cms import AmountStatus, CmsFileError
from plan_diff.extract import FAMILIES
from plan_diff.models import (
    AccuracyRow,
    AccuracyTable,
    Citation,
    CitationMethod,
    Copay,
    FieldName,
    FieldValue,
    Money,
    NotCovered,
    PlanRecord,
    ReviewItem,
    ReviewKind,
    Severity,
    StrictModel,
    Unit,
    ValidationResult,
    Verdict,
    disagreement,
    verdict_for,
)

_KIND = {p.field: p.kind for family in FAMILIES.values() for p in family}
_SEVERITY_ORDER = {Severity.HIGH: 0, Severity.MEDIUM: 1, Severity.LOW: 2}
_FIELD_ORDER = {name: index for index, name in enumerate(FieldName)}


class CmsValue(StrictModel):
    """One field's value in a CMS file, cited by file name and 1-based data row."""

    field: FieldName
    value: FieldValue
    unit: Unit | None
    citation: Citation


def _cms_unit(field: FieldName) -> Unit | None:
    unit = config.VALIDATE_CMS_UNITS[field.value]
    return Unit(unit) if unit is not None else None


def _typed(field: FieldName, amount: Decimal | None, status: str) -> FieldValue | None:
    if status == AmountStatus.NOT_COVERED:
        return NotCovered()
    if status != AmountStatus.VALUE or amount is None:
        return None  # an explicit missing marker: not in CMS
    return Copay(amount=amount) if _KIND[field] == "copay" else Money(amount=amount)


def _cms_citation(kind: str, year: int, file: str, row: int) -> Citation:
    text = f"CMS {kind} {year}, {file}, row {row}"
    return Citation(document_id=file, page=row, method=CitationMethod.CMS, text=text)


def cms_values_for(
    plan_id: str,
    *,
    pbp: pl.DataFrame,
    landscape: pl.DataFrame | None = None,
    landscape_file: str | None = None,
) -> dict[FieldName, CmsValue]:
    """CMS values for one plan from read_pbp and read_landscape output. The premium comes from the
    Landscape (docs/cms-fields.md). Counties that disagree on the premium stop the run.

    Review 2: every citation names the real CMS file and the plan year. With a Landscape frame,
    `landscape_file` (the real file name, for example "landscape_2026.csv") is required."""
    if landscape is not None and not landscape_file:
        raise ValueError("landscape_file is required with a Landscape frame: name the real file")
    out: dict[FieldName, CmsValue] = {}
    for row in pbp.filter(pl.col("plan_id") == plan_id).iter_rows(named=True):
        field = FieldName(row["field"])
        value = _typed(field, row["amount"], row["amount_status"])
        if value is not None:
            cite = _cms_citation("PBP", row["year"], row["file"], row["source_row"])
            out[field] = CmsValue(field=field, value=value, unit=_cms_unit(field), citation=cite)
    if landscape is not None and landscape_file:
        rows = landscape.filter(pl.col("plan_id") == plan_id)
        if rows.select("premium", "premium_status").unique().height > 1:
            found = rows["source_row"].to_list()
            raise CmsFileError(f"{landscape_file}: rows {found} give {plan_id} different premiums")
        if rows.height:
            first = rows.row(0, named=True)
            field = FieldName.MONTHLY_PREMIUM
            value = _typed(field, first["premium"], first["premium_status"])
            if value is not None:
                cite = _cms_citation(
                    "Landscape", first["year"], landscape_file, first["source_row"]
                )
                out[field] = CmsValue(
                    field=field, value=value, unit=_cms_unit(field), citation=cite
                )
    return out


def compare(
    extracted: PlanRecord, cms_values: Mapping[FieldName, CmsValue]
) -> list[ValidationResult]:
    """One ValidationResult per v1 field, in field order."""
    results = []
    for name in FieldName:
        pdf, cms = extracted.fields.get(name), cms_values.get(name)
        reason = None
        if pdf is None:
            verdict = Verdict.NOT_EXTRACTED
        elif cms is None:
            verdict = Verdict.NOT_IN_CMS
        else:
            reason = disagreement(name, pdf.value, pdf.unit, cms.value, cms.unit)
            verdict = verdict_for(reason)
        results.append(
            ValidationResult(
                plan_id=extracted.plan_id,
                year=extracted.year,
                field=name,
                pdf_value=pdf.value if pdf else None,
                cms_value=cms.value if cms else None,
                verdict=verdict,
                pdf_citation=pdf.citation if pdf else None,
                cms_citation=cms.citation if cms else None,
                pdf_unit=pdf.unit if pdf else None,
                cms_unit=cms.unit if cms else None,
                reason=reason,
            )
        )
    return results


def _describe(value: FieldValue | None, unit: Unit | None) -> str:
    match value:
        case Money(amount=amount) | Copay(amount=amount):
            text = f"${amount:,.2f}"
        case NotCovered():
            return "not covered"
        case None:
            return "nothing"
        case _:
            text = f"{value.percent}% coinsurance"
    return f"{text} {unit.value.replace('_', ' ')}" if unit else text


def review_items(results: Iterable[ValidationResult]) -> list[ReviewItem]:
    """One low-confidence review item per mismatch, with both values and both citations.
    Release 0.1.0: a not comparable result gets its own medium item with no confidence score."""
    items = []
    for r in results:
        if r.verdict not in (Verdict.MISMATCH, Verdict.NOT_COMPARABLE):
            continue
        if r.pdf_citation is None or r.cms_citation is None:
            continue
        pdf, cms = _describe(r.pdf_value, r.pdf_unit), _describe(r.cms_value, r.cms_unit)
        if r.verdict == Verdict.MISMATCH:
            kind = ReviewKind.PDF_CMS_MISMATCH
            severity = config.VALIDATE_SEVERITY.get(r.field.value, config.VALIDATE_SEVERITY_DEFAULT)
            confidence: float | None = config.VALIDATE_MISMATCH_CONFIDENCE
        else:
            kind = ReviewKind.NOT_COMPARABLE
            severity = config.VALIDATE_NOT_COMPARABLE_SEVERITY
            confidence = None
        items.append(
            ReviewItem(
                kind=kind,
                plan_id=r.plan_id,
                year=r.year,
                field=r.field,
                evidence=(r.pdf_citation, r.cms_citation),
                reason=f"PDF says {pdf}, CMS says {cms} ({r.reason})",
                severity=Severity(severity),
                confidence=confidence,
            )
        )
    return items


def _row(
    field: FieldName | None, method: CitationMethod, rs: list[ValidationResult]
) -> AccuracyRow:
    count = {v: sum(1 for r in rs if r.verdict == v) for v in Verdict}
    compared = count[Verdict.MATCH] + count[Verdict.MISMATCH]
    return AccuracyRow(
        field=field,
        method=method,
        matched=count[Verdict.MATCH],
        mismatched=count[Verdict.MISMATCH],
        not_extracted=count[Verdict.NOT_EXTRACTED],
        not_in_cms=count[Verdict.NOT_IN_CMS],
        match_rate=count[Verdict.MATCH] / compared if compared else None,
        not_comparable=count[Verdict.NOT_COMPARABLE],
    )


def accuracy(results: Iterable[ValidationResult]) -> AccuracyTable:
    """Counts per field and method, then a total per method. A field nobody extracted counts
    under RULE, because the deterministic pass always runs first."""
    groups: dict[tuple[FieldName, CitationMethod], list[ValidationResult]] = {}
    for r in results:
        method = r.pdf_citation.method if r.pdf_citation else CitationMethod.RULE
        groups.setdefault((r.field, method), []).append(r)
    keys = sorted(groups, key=lambda k: (_FIELD_ORDER[k[0]], list(CitationMethod).index(k[1])))
    rows = [_row(field, method, groups[(field, method)]) for field, method in keys]
    for method in CitationMethod:
        mine = [r for (_, m), rs in groups.items() if m == method for r in rs]
        if mine:
            rows.append(_row(None, method, mine))
    return AccuracyTable(rows=tuple(rows))


def write_validation(results: Iterable[ValidationResult], path: Path) -> None:
    path.write_text(json.dumps([json.loads(r.model_dump_json()) for r in results], indent=2) + "\n")


def write_accuracy(table: AccuracyTable, path: Path) -> None:
    path.write_text(table.model_dump_json(indent=2) + "\n")


def write_review_queue(items: Iterable[ReviewItem], path: Path) -> None:
    """JSONL, stable sort: severity (high first), plan id, then field in v1 order. Ties keep input
    order. Document-level items (no plan or field) sort first within their severity."""
    ordered = sorted(
        items,
        key=lambda i: (
            _SEVERITY_ORDER[i.severity],
            i.plan_id or "",
            _FIELD_ORDER[i.field] if i.field else -1,
        ),
    )
    path.write_text("".join(i.model_dump_json() + "\n" for i in ordered))
