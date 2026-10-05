"""Run steps 2 to 4: validate against CMS, diff by crosswalk, write the SPEC section 7 folder.

A run folder is immutable: an existing one is refused unless the caller passes overwrite. Files
are written to a hidden temp folder next to it and swapped in at the end, so a crash never leaves
half a run. With a frozen clock (--now) two runs of the same inputs write byte-identical folders.
"""

import json
import os
import re
import shutil
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from importlib.metadata import version as package_version
from pathlib import Path

import polars as pl

from plan_diff import __version__, config
from plan_diff.cms import read_crosswalk, read_landscape, read_pbp
from plan_diff.diff import crosswalk_row_for, diff_plans
from plan_diff.diff.engine import CrosswalkRow
from plan_diff.models import (
    ApiUsage,
    CrosswalkStatus,
    PlanDiff,
    PlanRecord,
    ReviewItem,
    ReviewKind,
    RunInput,
    RunManifest,
    Severity,
    StepTiming,
    ValidationResult,
)
from plan_diff.run.documents import Document, RunRefused, merge_fields, read_documents, run_input
from plan_diff.validate import (
    accuracy,
    cms_values_for,
    compare,
    review_items,
    write_accuracy,
    write_review_queue,
    write_validation,
)

_EMPTY_PBP = pl.DataFrame(
    schema={
        "plan_id": pl.String,
        "field": pl.String,
        "amount": pl.Decimal(12, 2),
        "amount_status": pl.String,
        "source_row": pl.Int64,
        "file": pl.String,
    }
)


@dataclass(frozen=True)
class RunOptions:
    docs: Path
    cms: Path
    plans: tuple[str, ...]
    years: tuple[int, ...]
    out: Path
    run_id: str
    overwrite: bool = False


@dataclass
class _Cms:
    inputs: list[RunInput]
    landscape: dict[int, pl.DataFrame]
    pbp: dict[int, pl.DataFrame]
    crosswalk: pl.DataFrame | None
    crosswalk_file: str


def _check(o: RunOptions) -> Path:
    if not re.fullmatch(config.RUN_ID_PATTERN, o.run_id):
        raise RunRefused(f"run id {o.run_id!r}: use letters, digits, dot, dash, underscore only")
    years = sorted(o.years)
    if not 1 <= len(years) <= 2 or (len(years) == 2 and years[1] != years[0] + 1):
        raise RunRefused(f"years {o.years}: give one year, or two years in a row (2026,2027)")
    if not o.docs.is_dir() or not o.cms.is_dir():
        raise RunRefused(f"--docs {o.docs} and --cms {o.cms} must both be folders")
    final = o.out / o.run_id
    if final.exists() and not o.overwrite:
        raise RunRefused(f"{final} already exists and run folders are immutable; pass --overwrite")
    return final


def _load_cms(o: RunOptions) -> _Cms:
    plans, years = list(o.plans), sorted(o.years)
    used: list[Path] = []
    landscape: dict[int, pl.DataFrame] = {}
    pbp: dict[int, pl.DataFrame] = {}
    for year in years:
        if (path := o.cms / f"landscape_{year}.csv").is_file():
            landscape[year] = read_landscape(path, year, plan_ids=plans)
            used.append(path)
        if (folder := o.cms / f"pbp_{year}").is_dir():
            pbp[year] = read_pbp(folder, year, plan_ids=plans)
            used += sorted(p for p in folder.iterdir() if p.is_file())
    crosswalk_file = f"crosswalk_{years[-1]}.csv"
    crosswalk = None
    if len(years) == 2 and (path := o.cms / crosswalk_file).is_file():
        crosswalk = read_crosswalk(path, years[-1], plan_ids=plans)
        used.append(path)
    inputs = [run_input("cms", p, o.cms) for p in sorted(used)]
    return _Cms(inputs, landscape, pbp, crosswalk, crosswalk_file)


def _record(
    plan_id: str, year: int, docs: list[Document], cms: _Cms
) -> tuple[PlanRecord, list[ReviewItem]]:
    fields, review = merge_fields(docs)
    land = cms.landscape.get(year)
    rows = land.filter(pl.col("plan_id") == plan_id) if land is not None else None
    counties = tuple(sorted(set(rows["county"].to_list()))) if rows is not None else ()
    name = rows["plan_name"][0] if rows is not None and rows.height else plan_id
    record = PlanRecord(
        plan_id=plan_id,
        year=year,
        carrier=docs[0].classification.carrier.value or "unknown carrier",
        plan_name=name,
        counties=counties,
        fields=fields,
        documents=tuple(d.classification.document_id for d in docs),
    )
    return record, review


def _missing(plan_id: str, year: int, why: str, severity: Severity = Severity.HIGH) -> ReviewItem:
    return ReviewItem(
        kind=ReviewKind.NOT_EXTRACTED,
        plan_id=plan_id,
        year=year,
        field=None,
        evidence=(),
        reason=why,
        severity=severity,
    )


def _no_new_record(old: PlanRecord, row: CrosswalkRow) -> PlanDiff:
    why = (
        f"the CMS crosswalk maps {old.plan_id} to {row.current_plan_id}, but no {old.year + 1} "
        f"document for {row.current_plan_id} was read: shop again is undecided"
    )
    return PlanDiff(
        old_plan_id=old.plan_id,
        new_plan_id=row.current_plan_id,
        old_year=old.year,
        new_year=old.year + 1,
        crosswalk_status=row.status,
        changes=(),
        shop_again=None,
        reasons=(),
        evidence=(row.citation(),),
        review=(_missing(row.current_plan_id or old.plan_id, old.year + 1, why),),
    )


def _diff(
    old: PlanRecord,
    records: dict[tuple[str, int], PlanRecord],
    cms: _Cms,
    validation: Sequence[ValidationResult],
) -> PlanDiff:
    row = None
    if cms.crosswalk is not None:
        row = crosswalk_row_for(cms.crosswalk, old.plan_id, cms.crosswalk_file)
    new = None
    if row is not None and row.status != CrosswalkStatus.TERMINATED:
        new = records.get((row.current_plan_id or "", old.year + 1))
        if new is None:
            return _no_new_record(old, row)
    new_area = new.counties if new else ()
    # review 2: a threshold field that disagrees with CMS can never decide the flag
    return diff_plans(old, new, row, old.counties, new_area, validation=validation)


def _plans_frame(records: Sequence[PlanRecord]) -> pl.DataFrame:
    """One row per plan, year, and field. Money and percents stay Decimal, never Float64."""
    rows = []
    for r in records:
        for f in r.fields.values():
            v = f.value
            rows.append(
                {
                    "plan_id": r.plan_id,
                    "year": r.year,
                    "field": f.name.value,
                    "kind": v.kind,
                    "amount": getattr(v, "amount", None),
                    "percent": getattr(v, "percent", None),
                    "unit": f.unit.value if f.unit else None,
                    "document_id": f.citation.document_id,
                    "page": f.citation.page,
                    "method": f.citation.method.value,
                    "confidence": f.confidence,
                }
            )
    schema: dict[str, pl.DataType] = {
        "plan_id": pl.String(),
        "year": pl.Int32(),
        "field": pl.String(),
        "kind": pl.String(),
        "amount": pl.Decimal(12, 2),
        "percent": pl.Decimal(5, 2),
        "unit": pl.String(),
        "document_id": pl.String(),
        "page": pl.Int32(),
        "method": pl.String(),
        "confidence": pl.Float64(),  # a score, not money
    }
    return pl.DataFrame(rows, schema=schema)


def run(o: RunOptions, clock: Callable[[], datetime]) -> Path:
    """Run every step and write the run folder. Returns its path."""
    final = _check(o)
    started = clock()
    timings: list[StepTiming] = []

    def lap(step: str, since: datetime) -> datetime:
        now = clock()
        timings.append(StepTiming(step=step, seconds=round((now - since).total_seconds(), 3)))
        return now

    plans, years = tuple(o.plans), tuple(sorted(o.years))
    docs = read_documents(o.docs, plans, years)
    t = lap("classify_and_extract", started)
    cms = _load_cms(o)
    t = lap("read_cms", t)
    review: list[ReviewItem] = list(docs.review)
    records: dict[tuple[str, int], PlanRecord] = {}
    for plan_id in plans:
        for year in years:
            mine = [
                d
                for d in docs.documents
                if (d.classification.plan_id.value, int(d.classification.year.value or 0))
                == (plan_id, year)
            ]
            if mine:
                records[(plan_id, year)], items = _record(plan_id, year, mine, cms)
                review += items
    validation: list[ValidationResult] = []
    for (plan_id, year), record in records.items():
        found = cms_values_for(
            plan_id,
            pbp=cms.pbp.get(year, _EMPTY_PBP),
            landscape=cms.landscape.get(year),
            landscape_file=f"landscape_{year}.csv",
        )
        results = compare(record, found)
        validation += results
        review += review_items(results)
    t = lap("validate", t)
    diffs: dict[str, PlanDiff] = {}
    if len(years) == 2:
        for plan_id in plans:
            old = records.get((plan_id, years[0]))
            if old is None:
                why = f"no {years[0]} document for {plan_id} was read, so it was not diffed"
                review.append(_missing(plan_id, years[0], why))
                continue
            diffs[plan_id] = _diff(old, records, cms, validation)
            review += diffs[plan_id].review
    lap("diff", t)
    finished = clock()
    manifest = RunManifest(
        run_id=o.run_id,
        started_at=started,
        finished_at=finished,
        versions={"plan-diff": __version__}
        | {name: package_version(name) for name in ("pdfplumber", "pypdf", "polars", "pydantic")},
        plans=plans,
        years=years,
        inputs=(*docs.inputs, *cms.inputs),
        modes={
            "classify_rules": "on",
            "extract_rules": "on",
            "classify_jev": config.RUN_JEV_MODE,
            "agreement_jev": config.RUN_JEV_MODE,
            "extract_llm": config.RUN_LLM_MODE,
        },
        jev=ApiUsage(mode=config.RUN_JEV_MODE, calls=0, cost_usd=Decimal("0")),
        llm=ApiUsage(mode=config.RUN_LLM_MODE, calls=0, cost_usd=Decimal("0")),
        timings=tuple(timings),
        counts={
            "pdfs": len(docs.inputs),
            "plan_records": len(records),
            "diffs": len(diffs),
            "review_items": len(review),
        },
    )
    o.out.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(dir=o.out, prefix=f".{o.run_id}.", suffix=".part"))
    try:
        (tmp / "plans").mkdir()
        (tmp / "diff").mkdir()
        (tmp / "manifest.json").write_text(manifest.model_dump_json(indent=2) + "\n")
        for (plan_id, year), record in records.items():
            path = tmp / "plans" / f"{plan_id}_{year}.json"
            path.write_text(record.model_dump_json(indent=2) + "\n")
        _plans_frame(list(records.values())).write_parquet(tmp / "plans.parquet")
        write_validation(validation, tmp / "validation.json")
        labels = {"plans": plans, "years": years, "run_id": o.run_id}
        labels["as_of"] = started.date().isoformat()  # Release 0.1.0: numbers carry their slice
        write_accuracy(accuracy(validation).model_copy(update=labels), tmp / "accuracy.json")
        for plan_id, d in diffs.items():
            (tmp / "diff" / f"{plan_id}.json").write_text(d.model_dump_json(indent=2) + "\n")
        write_review_queue(review, tmp / "review_queue.jsonl")
        if final.exists():
            shutil.rmtree(final)  # only with --overwrite (checked above), only this run id
        os.replace(tmp, final)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return final


def summary(folder: Path) -> list[str]:
    """One plain line per diffed plan, for the terminal. Undecided is never shown as no."""
    lines = []
    for path in sorted((folder / "diff").glob("*.json")):
        d = json.loads(path.read_text())
        flag = {True: "yes", False: "no", None: "undecided, needs review"}[d["shop_again"]]
        why = "; ".join(d["reasons"]) or "; ".join(i["reason"] for i in d["review"]) or "no change"
        lines.append(f"{d['old_plan_id']}: shop again {flag} ({why})")
    return lines
