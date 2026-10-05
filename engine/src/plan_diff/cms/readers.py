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
    PBP_LAYOUTS,
    CrosswalkLayout,
    LandscapeLayout,
    PbpLayout,
)
from plan_diff.config import (
    CMS_ENCODING,
    CMS_MISSING_MARKERS,
    CMS_MONEY_PRECISION,
    CMS_MONEY_SCALE,
    CMS_NOT_COVERED_MARKERS,
)
from plan_diff.models import CrosswalkStatus, crosswalk_status_from_cms, normalize_plan_id

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


def _plan_ids(df: pl.DataFrame, contract: str, plan: str, segment: str) -> pl.Series:
    """Canonical plan id per row, or null when the row has no id or not an MA plan id (S, E)."""
    base = pl.col(contract) + "-" + pl.col(plan)
    raw = df.select(
        pl.when(_blank(contract) | _blank(plan))
        .then(None)
        .when(_blank(segment))
        .then(base)
        .otherwise(base + "-" + pl.col(segment))
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
    cols = [v for k, v in vars(lay).items() if k != "separator"]
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
    return df.select(
        "plan_id",
        pl.lit(year, pl.Int32).alias("year"),
        pl.col(lay.organization).alias("organization"),
        pl.col(lay.plan_name).alias("plan_name"),
        pl.col(lay.state).alias("state"),
        pl.col(lay.county).alias("county"),
        "premium",
        "premium_status",
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


def read_pbp(
    directory: Path,
    year: int,
    *,
    plan_ids: Iterable[str],
    layouts: dict[int, PbpLayout] = PBP_LAYOUTS,
) -> pl.DataFrame:
    """PBP benefits for `year` (the unzipped folder), requested plans only: one row per plan and
    field, amount as Decimal with amount_status. Fields the layout marks None are left out."""
    lay = _layout(layouts, year)
    wanted = _requested(plan_ids)
    ids = [lay.contract, lay.plan, lay.segment]
    frames: list[pl.DataFrame] = []
    tables: dict[str, pl.DataFrame] = {}
    for name, where in lay.fields.items():
        if where is None:
            continue
        path = directory / where.file
        needed = ids + [where.column] + ([lay.tier] if where.tier else [])
        if where.file not in tables:
            table = _read_text(path, lay.separator, needed)
            _count_blank_ids(table, path, lay.contract, lay.plan)
            table = table.with_columns(_plan_ids(table, *ids).alias("plan_id"))
            tables[where.file] = table.filter(pl.col("plan_id").is_in(wanted))
        table = tables[where.file]
        if where.column not in table.columns or (where.tier and lay.tier not in table.columns):
            raise CmsFileError(f"{path}: missing columns for {name}")
        if where.tier:
            table = table.filter(pl.col(lay.tier) == where.tier)
        _refuse_duplicates(table, f"{path}: {name}")
        rows = _money(table, where.column, path, "amount").select(
            "plan_id",
            pl.lit(year, pl.Int32).alias("year"),
            pl.lit(name.value).alias("field"),
            "amount",
            "amount_status",
        )
        frames.append(rows)
    return pl.concat(frames)
