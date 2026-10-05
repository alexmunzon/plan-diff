"""PR 3: CMS file readers, run against small synthetic fixtures (fixtures/cms/SOURCE.md)."""

from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import polars as pl
import pytest

from plan_diff.cms import (
    CROSSWALK_LAYOUTS,
    LANDSCAPE_LAYOUTS,
    PBP_LAYOUTS,
    CmsFileError,
    read_crosswalk,
    read_landscape,
    read_pbp,
)
from plan_diff.models import CrosswalkStatus, FieldName

CMS = Path(__file__).resolve().parents[3] / "fixtures" / "cms"
CROSSWALK = CMS / "crosswalk_2027.csv"
ALL = ["H9999-001", "H9999-002", "H9999-003", "H9999-004", "H9999-005", "H9998-010"]


def rows_by_old_id(df: pl.DataFrame) -> dict[str | None, dict[str, object]]:
    return {r["previous_plan_id"]: r for r in df.to_dicts()}


def test_crosswalk_reads_statuses() -> None:
    df = read_crosswalk(CROSSWALK, 2027, plan_ids=ALL)
    assert df.schema["status"] == pl.String
    rows = rows_by_old_id(df)
    assert rows["H9999-001"]["status"] == CrosswalkStatus.CONTINUING
    assert rows["H9999-001"]["current_plan_id"] == "H9999-001"
    assert rows["H9998-010"]["status"] == CrosswalkStatus.SERVICE_AREA_REDUCED
    assert rows[None]["current_plan_id"] == "H9999-005"
    assert rows[None]["status"] == CrosswalkStatus.NEW


def test_crosswalk_consolidated_points_to_new_id() -> None:
    # SPEC example 2 input: the old id is gone, but the crosswalk says where it went.
    row = rows_by_old_id(read_crosswalk(CROSSWALK, 2027, plan_ids=ALL))["H9999-002"]
    assert row["status"] == CrosswalkStatus.CONSOLIDATED
    assert row["current_plan_id"] == "H9999-001"


def test_crosswalk_terminated_row() -> None:
    # SPEC example 3 input.
    row = rows_by_old_id(read_crosswalk(CROSSWALK, 2027, plan_ids=ALL))["H9999-003"]
    assert row["status"] == CrosswalkStatus.TERMINATED
    assert row["current_plan_id"] is None
    assert row["source_row"] == 3  # data row number in the CMS file, kept as evidence


def test_crosswalk_unknown_status_raises(tmp_path: Path) -> None:
    text = CROSSWALK.read_text().replace("Terminated/Non-renewed Plan", "Mystery Status")
    bad = tmp_path / "crosswalk.csv"
    bad.write_text(text)
    with pytest.raises(CmsFileError, match="unknown CMS crosswalk status: 'Mystery Status'"):
        read_crosswalk(bad, 2027, plan_ids=ALL)


def test_crosswalk_consolidated_without_new_id_raises(tmp_path: Path) -> None:
    lines = CROSSWALK.read_text().splitlines()
    lines = [
        ",".join(["H9999", "002", "000", "", "", "", "Consolidated Renewal Plan"])
        if line.startswith("H9999,002")
        else line
        for line in lines
    ]
    bad = tmp_path / "crosswalk.csv"
    bad.write_text("\n".join(lines) + "\n")
    with pytest.raises(CmsFileError, match="consolidated.*no current plan id"):
        read_crosswalk(bad, 2027, plan_ids=ALL)


def test_landscape_reads_typed_rows() -> None:
    df = read_landscape(CMS / "landscape_2026.csv", 2026, plan_ids=ALL)
    assert df.columns == [
        "plan_id",
        "year",
        "organization",
        "plan_name",
        "state",
        "county",
        "premium",
        "premium_status",
        "source_row",
    ]
    assert isinstance(df.schema["premium"], pl.Decimal)
    first = df.filter(pl.col("plan_id") == "H9999-001").to_dicts()[0]
    assert first["premium"] == Decimal("0.00")
    assert first["year"] == 2026
    assert first["organization"] == "Synthetic Health Plan of Texas"
    paid = df.filter(pl.col("plan_id") == "H9999-002").to_dicts()[0]
    assert paid["premium"] == Decimal("25.50")
    assert set(df["county"]) == {"Bexar", "Travis"}


def test_pbp_reads_fields_as_decimals() -> None:
    df = read_pbp(CMS / "pbp_2026", 2026, plan_ids=ALL)
    got = {(r["plan_id"], r["field"]): r["amount"] for r in df.to_dicts()}
    assert isinstance(df.schema["amount"], pl.Decimal)
    plan = "H9999-001"
    assert got[(plan, FieldName.MOOP_IN_NETWORK)] == Decimal("4900.00")
    assert got[(plan, FieldName.SPECIALIST_COPAY)] == Decimal("40.00")
    assert got[(plan, FieldName.DRUG_TIER_2)] == Decimal("8.00")
    assert got[(plan, FieldName.OTC_ALLOWANCE)] == Decimal("200.00")
    # Premium is not read from PBP: the Landscape holds the consolidated premium.
    assert (plan, FieldName.MONTHLY_PREMIUM) not in got
    expected = {f for f in FieldName if PBP_LAYOUTS[2026].fields[f] is not None}
    assert {f for (p, f) in got if p == plan} == expected


def test_layout_switches_by_year(tmp_path: Path) -> None:
    renamed = "Monthly Premium Renamed"
    old = LANDSCAPE_LAYOUTS[2026]
    text = (CMS / "landscape_2026.csv").read_text().replace(old.premium, renamed)
    path = tmp_path / "landscape.csv"
    path.write_text(text)
    layouts = {2026: old, 2027: replace(old, premium=renamed)}
    assert read_landscape(path, 2027, plan_ids=ALL, layouts=layouts)["year"].unique().to_list() == [
        2027
    ]
    with pytest.raises(CmsFileError, match="missing columns.*Monthly Consolidated Premium"):
        read_landscape(path, 2026, plan_ids=ALL, layouts=layouts)


def test_unknown_year_raises() -> None:
    assert 2026 in CROSSWALK_LAYOUTS and 2027 in CROSSWALK_LAYOUTS
    with pytest.raises(CmsFileError, match="no CMS layout for year 2019"):
        read_crosswalk(CROSSWALK, 2019, plan_ids=ALL)
