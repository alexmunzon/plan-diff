"""Polars readers for CMS public files. Every value is read as text first (so plan ids keep their
leading zeros), then typed: money becomes an exact Decimal, crosswalk labels become CrosswalkStatus.
A file that does not match its year's layout fails loudly; nothing is guessed."""

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
from plan_diff.config import CMS_ENCODING, CMS_MONEY_PRECISION, CMS_MONEY_SCALE
from plan_diff.models import CrosswalkStatus, crosswalk_status_from_cms


class CmsFileError(ValueError):
    """A CMS file does not match what the reader expects. The message names the file."""


def _layout[L](layouts: dict[int, L], year: int) -> L:
    if year not in layouts:
        raise CmsFileError(f"no CMS layout for year {year}; known years: {sorted(layouts)}")
    return layouts[year]


def _read_text(path: Path, separator: str, needed: list[str]) -> pl.DataFrame:
    df = pl.read_csv(path, separator=separator, infer_schema=False, encoding=CMS_ENCODING)
    df = df.with_columns(pl.all().str.strip_chars())
    missing = [c for c in needed if c not in df.columns]
    if missing:
        raise CmsFileError(f"{path}: missing columns {missing}; check this year's layout")
    return df


def _plan_id(contract: str, plan: str, segment: str) -> pl.Expr:
    """H1234 + 5 + 0 becomes H1234-005. A non-zero segment is kept: H1234-005-001."""
    seg = pl.col(segment).fill_null("0").str.zfill(3)
    base = pl.col(contract) + "-" + pl.col(plan).str.zfill(3)
    full = pl.when(seg == "000").then(base).otherwise(base + "-" + seg)
    return pl.when(pl.col(contract).fill_null("") == "").then(None).otherwise(full)


def _money(column: str) -> pl.Expr:
    text = pl.col(column).str.replace_all(r"[$,\s]", "")
    text = pl.when(text == "").then(None).otherwise(text)
    return text.cast(pl.Decimal(CMS_MONEY_PRECISION, CMS_MONEY_SCALE))


def read_crosswalk(
    path: Path, year: int, layouts: dict[int, CrosswalkLayout] = CROSSWALK_LAYOUTS
) -> pl.DataFrame:
    """Part C and D Plan Crosswalk for `year`: previous plan id, current plan id, status."""
    lay = _layout(layouts, year)
    cols = [v for k, v in vars(lay).items() if k != "separator"]
    df = _read_text(path, lay.separator, cols).with_row_index("source_row", offset=1)
    statuses: dict[str, str] = {}
    for label in df[lay.status].unique().to_list():
        try:
            statuses[label] = crosswalk_status_from_cms(label or "").value
        except ValueError as err:
            raise CmsFileError(f"{path}: {err}") from err
    out = df.select(
        pl.col("source_row").cast(pl.Int64),
        _plan_id(lay.previous_contract, lay.previous_plan, lay.previous_segment).alias(
            "previous_plan_id"
        ),
        _plan_id(lay.current_contract, lay.current_plan, lay.current_segment).alias(
            "current_plan_id"
        ),
        pl.col(lay.status).replace_strict(statuses).alias("status"),
        pl.col(lay.status).alias("cms_status_label"),
    )
    orphans = out.filter(
        (pl.col("status") == CrosswalkStatus.CONSOLIDATED) & pl.col("current_plan_id").is_null()
    )
    if orphans.height:
        rows = orphans["source_row"].to_list()
        raise CmsFileError(f"{path}: consolidated rows {rows} have no current plan id")
    return out


def read_landscape(
    path: Path, year: int, layouts: dict[int, LandscapeLayout] = LANDSCAPE_LAYOUTS
) -> pl.DataFrame:
    """MA Landscape for `year`: one row per plan per county, premium as Decimal."""
    lay = _layout(layouts, year)
    cols = [v for k, v in vars(lay).items() if k != "separator"]
    df = _read_text(path, lay.separator, cols)
    return df.select(
        _plan_id(lay.contract, lay.plan, lay.segment).alias("plan_id"),
        pl.lit(year, pl.Int32).alias("year"),
        pl.col(lay.organization).alias("organization"),
        pl.col(lay.plan_name).alias("plan_name"),
        pl.col(lay.state).alias("state"),
        pl.col(lay.county).alias("county"),
        _money(lay.premium).alias("premium"),
    )


def read_pbp(
    directory: Path, year: int, layouts: dict[int, PbpLayout] = PBP_LAYOUTS
) -> pl.DataFrame:
    """PBP benefits for `year` (the unzipped folder): one row per plan and field, amount as Decimal.
    Fields the layout marks None (not in PBP) are left out."""
    lay = _layout(layouts, year)
    ids = [lay.contract, lay.plan, lay.segment]
    frames: list[pl.DataFrame] = []
    tables: dict[str, pl.DataFrame] = {}
    for name, where in lay.fields.items():
        if where is None:
            continue
        needed = ids + [where.column] + ([lay.tier] if where.tier else [])
        if where.file not in tables:
            tables[where.file] = _read_text(directory / where.file, lay.separator, needed)
        table = tables[where.file]
        if where.column not in table.columns or (where.tier and lay.tier not in table.columns):
            raise CmsFileError(f"{directory / where.file}: missing columns for {name}")
        if where.tier:
            table = table.filter(pl.col(lay.tier) == where.tier)
        rows = table.select(
            _plan_id(*ids).alias("plan_id"),
            pl.lit(year, pl.Int32).alias("year"),
            pl.lit(name.value).alias("field"),
            _money(where.column).alias("amount"),
        )
        dupes = rows.filter(pl.col("plan_id").is_duplicated())["plan_id"].unique().to_list()
        if dupes:
            raise CmsFileError(f"{directory / where.file}: {name} has several rows for {dupes}")
        frames.append(rows)
    return pl.concat(frames)
