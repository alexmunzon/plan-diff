"""Polars readers for CMS public files. Every value is read as text first (so plan ids keep their
leading zeros), then typed: money becomes an exact Decimal, crosswalk labels become CrosswalkStatus.
A file that does not match its year's layout fails loudly; nothing is guessed.

CMS files are national. Each reader takes the plan ids it was asked about (the slice) and keeps only
those rows before checking or typing anything, so Part D (S) and employer (E) contracts, and junk
in plans nobody asked about, never reach the plan schema. Plan ids go through the one rule in
plan_diff.models.normalize_plan_id."""

import logging
import re
from collections.abc import Iterable
from decimal import Decimal
from enum import StrEnum
from pathlib import Path

import polars as pl

from plan_diff.cms.layouts import (
    CROSSWALK_LAYOUTS,
    LANDSCAPE_LAYOUTS,
    PBP_COMBO_COLUMNS,
    PBP_COMBO_GROUPS,
    PBP_LAYOUTS,
    PBP_PERIOD_CODES,
    CrosswalkLayout,
    LandscapeLayout,
    PbpColumn,
    PbpLayout,
)
from plan_diff.config import (
    CMS_ENCODING,
    CMS_MISSING_MARKERS,
    CMS_MONEY_PRECISION,
    CMS_MONEY_SCALE,
    CMS_NOT_COVERED_MARKERS,
)
from plan_diff.models import (
    CrosswalkStatus,
    FieldName,
    crosswalk_status_from_cms,
    normalize_plan_id,
)

log = logging.getLogger(__name__)

_THOUSANDS = re.compile(r"-?[0-9]{1,3}(,[0-9]{3})+(\.[0-9]*)?")
_PLAIN = re.compile(r"([0-9]+)(?:\.([0-9]+))?")
_MONEY = pl.Decimal(CMS_MONEY_PRECISION, CMS_MONEY_SCALE)
_CENT = Decimal(1).scaleb(-CMS_MONEY_SCALE)


class CmsFileError(ValueError):
    """A CMS file does not match what the reader expects. The message names the file."""


class AmountStatus(StrEnum):
    """What a money cell held: a number, an explicit missing marker, or a not-covered marker."""

    VALUE = "value"
    MISSING = "missing"
    NOT_COVERED = "not_covered"  # same word as plan_diff.models.NotCovered
    # PR 15 (PBP only): the min and max columns differ, so CMS gives a range, not one value.
    RANGE = "range"
    # PR 15 (PBP only): no copay, a coinsurance percent instead (in the `percent` column).
    PERCENT = "percent"
    # PR 15 (PBP only): both a copay and a coinsurance are filed; neither is picked.
    MIXED = "mixed"


def _layout[L](layouts: dict[int, L], year: int) -> L:
    if year not in layouts:
        raise CmsFileError(f"no CMS layout for year {year}; known years: {sorted(layouts)}")
    return layouts[year]


def _requested(plan_ids: Iterable[str]) -> set[str]:
    out: set[str] = set()
    for text in plan_ids:
        try:
            out.add(normalize_plan_id(text))
        except ValueError as err:
            raise CmsFileError(f"requested {err}") from err
    return out


def _read_text(path: Path, separator: str, needed: list[str]) -> pl.DataFrame:
    df = pl.read_csv(path, separator=separator, infer_schema=False, encoding=CMS_ENCODING)
    df = df.with_columns(pl.all().str.strip_chars())
    missing = [c for c in needed if c not in df.columns]
    if missing:
        raise CmsFileError(f"{path}: missing columns {missing}; check this year's layout")
    return df.with_row_index("source_row", offset=1).with_columns(
        pl.col("source_row").cast(pl.Int64)
    )


def _blank(column: str) -> pl.Expr:
    return pl.col(column).fill_null("") == ""


def _plan_ids(df: pl.DataFrame, contract: str, plan: str, segment: str | None) -> pl.Series:
    """Canonical plan id per row, or null when the row has no id or not an MA plan id (S, E).
    PR 15: a file with no segment column (the real crosswalk) is plan level: segment 000."""
    base = pl.col(contract) + "-" + pl.col(plan)
    with_segment = base if segment is None else base + "-" + pl.col(segment)
    no_segment = pl.lit(True) if segment is None else _blank(segment)
    raw = df.select(
        pl.when(_blank(contract) | _blank(plan))
        .then(None)
        .when(no_segment)
        .then(base)
        .otherwise(with_segment)
    ).to_series()
    mapping: dict[str, str | None] = {}
    for text in raw.drop_nulls().unique().to_list():
        try:
            mapping[text] = normalize_plan_id(text)
        except ValueError:
            mapping[text] = None  # not a plan we could have been asked about
    return raw.replace_strict(mapping, default=None, return_dtype=pl.String)


def _count_blank_ids(df: pl.DataFrame, path: Path, contract: str, plan: str) -> None:
    blank = df.filter(_blank(contract) | _blank(plan)).height
    if blank:
        log.warning("%s: ignored %d rows with a blank plan id", path, blank)


def _parse_money(text: str | None, where: str) -> tuple[Decimal | None, AmountStatus]:
    cell = (text or "").strip()
    if cell.lower() in CMS_MISSING_MARKERS:
        return None, AmountStatus.MISSING
    if cell.lower() in CMS_NOT_COVERED_MARKERS:
        return None, AmountStatus.NOT_COVERED
    number = cell.replace("$", "").replace(" ", "")
    if "," in number:
        if not _THOUSANDS.fullmatch(number):
            raise CmsFileError(f"{where}: {cell!r} has commas that are not thousands separators")
        number = number.replace(",", "")
    if number.startswith("-") or (number.startswith("(") and number.endswith(")")):
        raise CmsFileError(f"{where}: {cell!r} is negative")
    match = _PLAIN.fullmatch(number)
    if match is None:
        raise CmsFileError(f"{where}: {cell!r} is not a money amount")
    if match.group(2) is not None and len(match.group(2)) > CMS_MONEY_SCALE:
        raise CmsFileError(f"{where}: {cell!r} has more than {CMS_MONEY_SCALE} decimal places")
    if len(match.group(1).lstrip("0")) > CMS_MONEY_PRECISION - CMS_MONEY_SCALE:
        raise CmsFileError(f"{where}: {cell!r} is too large")
    return Decimal(number).quantize(_CENT), AmountStatus.VALUE


def _money(df: pl.DataFrame, column: str, path: Path, name: str) -> pl.DataFrame:
    """Adds `name` (Decimal or null) and `name_status`. Checks every cell before any cast."""
    amounts: list[Decimal | None] = []
    statuses: list[str] = []
    for row, text in zip(df["source_row"].to_list(), df[column].to_list(), strict=True):
        amount, status = _parse_money(text, f"{path}: column {column!r}, row {row}")
        amounts.append(amount)
        statuses.append(status.value)
    return df.with_columns(
        pl.Series(name, amounts, dtype=_MONEY), pl.Series(f"{name}_status", statuses, pl.String)
    )


def read_crosswalk(
    path: Path,
    year: int,
    *,
    plan_ids: Iterable[str],
    layouts: dict[int, CrosswalkLayout] = CROSSWALK_LAYOUTS,
) -> pl.DataFrame:
    """Part C and D Plan Crosswalk for `year`: previous plan id, current plan id, status.
    Keeps rows whose previous or current plan id is in `plan_ids`."""
    lay = _layout(layouts, year)
    wanted = _requested(plan_ids)
    cols = [v for k, v in vars(lay).items() if k != "separator" and v is not None]
    df = _read_text(path, lay.separator, cols)
    df = df.with_columns(
        _plan_ids(df, lay.previous_contract, lay.previous_plan, lay.previous_segment).alias(
            "previous_plan_id"
        ),
        _plan_ids(df, lay.current_contract, lay.current_plan, lay.current_segment).alias(
            "current_plan_id"
        ),
    ).filter(pl.col("previous_plan_id").is_in(wanted) | pl.col("current_plan_id").is_in(wanted))
    statuses: dict[str, str] = {}
    for label in df[lay.status].unique().to_list():
        try:
            statuses[label] = crosswalk_status_from_cms(label or "").value
        except ValueError as err:
            raise CmsFileError(f"{path}: {err}") from err
    out = df.select(
        "source_row",
        "previous_plan_id",
        "current_plan_id",
        pl.col(lay.status).replace_strict(statuses, return_dtype=pl.String).alias("status"),
        pl.col(lay.status).alias("cms_status_label"),
    )
    orphans = out.filter(
        (pl.col("status") == CrosswalkStatus.CONSOLIDATED) & pl.col("current_plan_id").is_null()
    )
    if orphans.height:
        rows = orphans["source_row"].to_list()
        raise CmsFileError(f"{path}: consolidated rows {rows} have no current plan id")
    ended = out.filter(
        (pl.col("status") == CrosswalkStatus.TERMINATED) & pl.col("current_plan_id").is_not_null()
    )
    if ended.height:
        rows = ended["source_row"].to_list()
        raise CmsFileError(f"{path}: terminated rows {rows} also name a current plan id")
    return out


def read_landscape(
    path: Path,
    year: int,
    *,
    plan_ids: Iterable[str],
    layouts: dict[int, LandscapeLayout] = LANDSCAPE_LAYOUTS,
) -> pl.DataFrame:
    """MA Landscape for `year`, requested plans only: one row per plan per county, premium as
    Decimal with premium_status saying when it is missing or not covered."""
    lay = _layout(layouts, year)
    wanted = _requested(plan_ids)
    cols = [v for k, v in vars(lay).items() if k != "separator"]
    df = _read_text(path, lay.separator, cols)
    _count_blank_ids(df, path, lay.contract, lay.plan)
    df = df.with_columns(_plan_ids(df, lay.contract, lay.plan, lay.segment).alias("plan_id"))
    df = _money(df.filter(pl.col("plan_id").is_in(wanted)), lay.premium, path, "premium")
    df = _part_c_only(df, lay, path)
    return df.select(
        "plan_id",
        pl.lit(year, pl.Int32).alias("year"),
        pl.col(lay.organization).alias("organization"),
        pl.col(lay.plan_name).alias("plan_name"),
        pl.col(lay.state).alias("state"),
        pl.col(lay.county).alias("county"),
        "premium",
        "premium_status",
        "source_row",  # PR 7: the CMS citation for the premium
    )


def _part_c_only(df: pl.DataFrame, lay: LandscapeLayout, path: Path) -> pl.DataFrame:
    """PR 15: a plan with no Part D files "Not Applicable" as its consolidated premium; its whole
    premium is the Part C premium. Only rows whose Part D indicator says No take it."""
    no_d = (pl.col("premium_status") == AmountStatus.MISSING) & (
        pl.col(lay.part_d_indicator).str.to_lowercase() == "no"
    )
    if not df.filter(no_d).height:
        return df
    part_c = _money(df, lay.part_c_premium, path, "part_c")
    return part_c.with_columns(
        pl.when(no_d).then(pl.col("part_c")).otherwise(pl.col("premium")).alias("premium"),
        pl.when(no_d)
        .then(pl.col("part_c_status"))
        .otherwise(pl.col("premium_status"))
        .alias("premium_status"),
    )


def _refuse_duplicates(rows: pl.DataFrame, where: str) -> None:
    dupes = (
        rows.group_by("plan_id", maintain_order=True)
        .agg(pl.col("source_row"))
        .filter(pl.col("source_row").list.len() > 1)
    )
    if dupes.height:
        found = "; ".join(f"{r['plan_id']} (rows {r['source_row']})" for r in dupes.to_dicts())
        raise CmsFileError(f"{where} has several rows for {found}")


def _cell(row: dict[str, object], column: str, where: str) -> str:
    if column not in row:
        raise CmsFileError(f"{where}: missing column {column!r}; check this year's layout")
    return str(row[column] or "")


def _period(row: dict[str, object], column: str | None, where: str) -> str | None:
    if column is None:
        return None
    return PBP_PERIOD_CODES.get(_cell(row, column, where).strip())


_PbpOut = dict[str, object]
_NOTE_CHARS = 120  # the CMS citation text, note included, stays under the schema's 200 characters


def _combo(row: dict[str, object], spec: PbpColumn, where: str) -> _PbpOut:
    """PR 15: the Section D combined benefit group that lists `spec.combo_category`."""
    found = []
    for n in range(1, PBP_COMBO_GROUPS + 1):
        col = {k: v.format(n=n) for k, v in PBP_COMBO_COLUMNS.items()}
        if col["categories"] not in row:
            break
        cats = [c.strip() for c in _cell(row, col["categories"], where).split(";")]
        if spec.combo_category in cats:
            found.append(col)
    if not found:
        return {"amount_status": AmountStatus.MISSING.value}
    if len(found) > 1:
        raise CmsFileError(f"{where}: {spec.combo_category} is in {len(found)} combined groups")
    col = found[0]
    amount, status = _parse_money(_cell(row, col["amount"], where), f"{where}, {col['amount']}")
    listed = _cell(row, col["categories"], where).rstrip(";")
    note = f"combined group {_cell(row, col['name'], where)!r} ({listed})"
    return {
        "amount": amount,
        "amount_status": status.value,
        "unit": _period(row, col["period"], where),
        "note": note[:_NOTE_CHARS],
    }


def _pbp_value(row: dict[str, object], spec: PbpColumn, path: Path) -> _PbpOut:
    """One field's value for one PBP row (PR 15 rules in PbpColumn's docstring)."""
    n = row["source_row"]

    def money(column: str) -> tuple[Decimal | None, AmountStatus]:
        where = f"{path}: column {column!r}, row {n}"
        return _parse_money(_cell(row, column, where), where)

    if spec.only_when is not None:
        column, code = spec.only_when
        if _cell(row, column, str(path)).strip() != code:
            return {"amount_status": AmountStatus.MISSING.value}
    if spec.combo_category:
        return _combo(row, spec, f"{path}: row {n}")
    amount, status = money(spec.column)
    out: _PbpOut = {"amount": amount, "amount_status": status.value}
    if status is AmountStatus.MISSING and spec.zero_when is not None:
        column, code = spec.zero_when
        if _cell(row, column, str(path)).strip() == code:
            out = {"amount": Decimal(0).quantize(_CENT), "amount_status": AmountStatus.VALUE.value}
            out["note"] = f"{column} = {code}"
    if status is AmountStatus.VALUE and spec.max_column is not None:
        top, top_status = money(spec.max_column)
        if top_status is AmountStatus.VALUE and top != amount:
            out = {**out, "amount_status": AmountStatus.RANGE.value, "max_amount": top}
    if spec.coins_column is not None:
        pct, pct_status = money(spec.coins_column)
        if pct_status is AmountStatus.VALUE:
            if status is AmountStatus.VALUE:
                out = {"amount_status": AmountStatus.MIXED.value}
            elif status is AmountStatus.MISSING:
                out = {"amount_status": AmountStatus.PERCENT.value, "percent": pct}
                if spec.coins_max_column is not None and spec.coins_max_column in row:
                    top, top_status = money(spec.coins_max_column)
                    if top_status is AmountStatus.VALUE:
                        out["max_amount"] = top
    out["unit"] = _period(row, spec.period_column, str(path))
    return out


def read_pbp(
    directory: Path,
    year: int,
    *,
    plan_ids: Iterable[str],
    layouts: dict[int, PbpLayout] = PBP_LAYOUTS,
) -> pl.DataFrame:
    """PBP benefits for `year` (the unzipped folder), requested plans only: one row per plan and
    field, amount as Decimal with amount_status. Fields the layout marks None are left out.

    PR 15 columns: `percent` (a coinsurance), `max_amount` (the top of a range), `unit` (the CMS
    period of an allowance, else null), `note` (what else the citation should say)."""
    lay = _layout(layouts, year)
    wanted = _requested(plan_ids)
    ids = [lay.contract, lay.plan, lay.segment]
    tables: dict[str, pl.DataFrame] = {}

    def table(file: str) -> pl.DataFrame:
        if file not in tables:
            path = directory / file
            raw = _read_text(path, lay.separator, ids)
            _count_blank_ids(raw, path, lay.contract, lay.plan)
            raw = raw.with_columns(_plan_ids(raw, *ids).alias("plan_id"))
            tables[file] = raw.filter(pl.col("plan_id").is_in(wanted))
        return tables[file]

    row_maps: dict[tuple[str, str | None], dict[str, dict[str, object]]] = {}

    def rows_for(spec: PbpColumn, name: FieldName) -> dict[str, dict[str, object]]:
        key = (spec.file, spec.tier)
        if key in row_maps:
            return row_maps[key]
        rows = table(spec.file)
        path = directory / spec.file
        if spec.tier:
            if lay.tier not in rows.columns:
                raise CmsFileError(f"{path}: missing columns for {name}")
            rows = rows.filter(pl.col(lay.tier) == spec.tier)
        _refuse_duplicates(rows, f"{path}: {name}")
        row_maps[key] = {str(r["plan_id"]): r for r in rows.to_dicts()}
        return row_maps[key]

    out: list[dict[str, object]] = []
    for name, first in lay.fields.items():
        if first is None:
            continue
        for plan_id, row in sorted(rows_for(first, name).items()):
            spec: PbpColumn | None = first
            hit: tuple[PbpColumn, dict[str, object], _PbpOut] | None = None
            while spec is not None:
                source = row if spec.file == first.file else rows_for(spec, name).get(plan_id)
                if source is not None:
                    value = _pbp_value(source, spec, directory / spec.file)
                    hit = (spec, source, value)
                    if value["amount_status"] != AmountStatus.MISSING:
                        break
                spec = spec.fallback
            assert hit is not None  # the first spec always has this plan's row
            spec_used, source, value = hit
            out.append(
                {
                    "plan_id": plan_id,
                    "year": year,
                    "field": name.value,
                    "amount": value.get("amount"),
                    "amount_status": value["amount_status"],
                    "source_row": source["source_row"],
                    "file": spec_used.file,
                    "percent": value.get("percent"),
                    "max_amount": value.get("max_amount"),
                    "unit": value.get("unit"),
                    "note": value.get("note"),
                }
            )
    return pl.DataFrame(out, schema=PBP_SCHEMA)


PBP_SCHEMA: dict[str, pl.DataType | type[pl.DataType]] = {
    "plan_id": pl.String,
    "year": pl.Int32,
    "field": pl.String,
    "amount": _MONEY,
    "amount_status": pl.String,
    "source_row": pl.Int64,
    "file": pl.String,
    "percent": _MONEY,
    "max_amount": _MONEY,
    "unit": pl.String,
    "note": pl.String,
}
