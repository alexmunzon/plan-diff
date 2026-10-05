"""Review 1 fixes: one plan id rule, money checks, duplicate rows, and messy CMS fixtures."""

import logging
from decimal import Decimal
from pathlib import Path

import pytest

from plan_diff.classify import classify_pages
from plan_diff.cms import AmountStatus, CmsFileError, read_crosswalk, read_landscape, read_pbp
from plan_diff.models import FieldName, normalize_plan_id

MESSY = Path(__file__).resolve().parents[3] / "fixtures" / "cms" / "messy"
LANDSCAPE = MESSY / "landscape_2026.csv"
CROSSWALK = MESSY / "crosswalk_2027.csv"
PBP = MESSY / "pbp_2026"


@pytest.mark.parametrize(
    ("text", "canonical"),
    [
        ("H0028-030-000", "H0028-030"),
        ("H0028-030", "H0028-030"),
        ("H5294-014-001", "H5294-014-001"),
        ("H9999-1-0", "H9999-001"),
        ("R9999-001", "R9999-001"),
    ],
)
def test_normalize_plan_id(text: str, canonical: str) -> None:
    assert normalize_plan_id(text) == canonical


@pytest.mark.parametrize("bad", ["S9999-001", "E9999-001", "H0028030", "h0028-030", ""])
def test_normalize_plan_id_refuses_non_ma_ids(bad: str) -> None:
    with pytest.raises(ValueError, match="not a Medicare Advantage plan id"):
        normalize_plan_id(bad)


def test_segment_round_trips_through_classifier_and_reader() -> None:
    pages = ["Humana 2026 Summary of Benefits\nH5294-014-001"]
    from_pdf = classify_pages(pages, document_id="d").plan_id.value
    assert from_pdf == "H5294-014-001"
    df = read_landscape(LANDSCAPE, 2026, plan_ids=[from_pdf])
    assert df["plan_id"].to_list() == [from_pdf]


def test_zero_segment_is_dropped_by_classifier_and_reader() -> None:
    pages = ["Humana 2026 Summary of Benefits\nH0028-030-000"]
    assert classify_pages(pages, document_id="d").plan_id.value == "H0028-030"
    df = read_landscape(LANDSCAPE, 2026, plan_ids=["H0028-030-000"])
    assert df["plan_id"].to_list() == ["H0028-030"]


def test_r_contract_is_accepted() -> None:
    assert (
        classify_pages(
            ["Humana 2026 Evidence of Coverage\nR9999-001"], document_id="d"
        ).plan_id.value
        == "R9999-001"
    )
    row = read_landscape(LANDSCAPE, 2026, plan_ids=["R9999-001"]).to_dicts()[0]
    assert row["premium"] == Decimal("40.00")
    assert read_crosswalk(CROSSWALK, 2027, plan_ids=["R9999-001"])["current_plan_id"].to_list() == [
        "R9999-001"
    ]


def test_s_and_e_rows_are_filtered_not_errors() -> None:
    # The S and E rows hold junk money ("abc", "-1") and a label the crosswalk does not know.
    # They are outside the slice, so none of it is checked.
    wanted = ["H9999-001", "R9999-001"]
    assert set(read_landscape(LANDSCAPE, 2026, plan_ids=wanted)["plan_id"]) == set(wanted)
    assert set(read_crosswalk(CROSSWALK, 2027, plan_ids=wanted)["previous_plan_id"]) == set(wanted)
    assert set(read_pbp(PBP, 2026, plan_ids=["R9999-001"])["plan_id"]) == {"R9999-001"}


def test_requested_id_that_is_not_ma_is_refused() -> None:
    with pytest.raises(CmsFileError, match="S9999-001"):
        read_landscape(LANDSCAPE, 2026, plan_ids=["S9999-001"])


def test_messy_landscape_money_and_padding() -> None:
    df = read_landscape(LANDSCAPE, 2026, plan_ids=["H9999-001", "H9999-002", "H9999-004"])
    rows = {r["plan_id"]: r for r in df.to_dicts()}
    assert rows["H9999-001"]["premium"] == Decimal("1234.00")  # plan "1", "$1,234"
    assert rows["H9999-001"]["premium_status"] == AmountStatus.VALUE
    assert "�" in rows["H9999-001"]["organization"]  # non-UTF-8 byte replaced, not fatal
    assert rows["H9999-002"]["premium"] is None
    assert rows["H9999-002"]["premium_status"] == AmountStatus.MISSING  # "N/A"
    assert rows["H9999-004"]["premium"] is None
    assert rows["H9999-004"]["premium_status"] == AmountStatus.NOT_COVERED  # "Not covered"


def test_money_with_three_decimals_is_refused() -> None:
    with pytest.raises(
        CmsFileError, match=r"landscape_2026.csv: column 'Monthly.*', row 3: '12.345' has more"
    ):
        read_landscape(LANDSCAPE, 2026, plan_ids=["H9999-003"])


def test_negative_money_is_refused() -> None:
    with pytest.raises(CmsFileError, match=r"row 5: '-5.00' is negative"):
        read_landscape(LANDSCAPE, 2026, plan_ids=["H9999-005"])


def test_landscape_blank_ids_are_counted(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING):
        read_landscape(LANDSCAPE, 2026, plan_ids=["H9999-001"])
    assert "ignored 1 rows with a blank plan id" in caplog.text


def test_messy_crosswalk_padding_and_segments() -> None:
    wanted = ["H9999-001", "H5294-014-001", "H0028-030"]
    df = read_crosswalk(CROSSWALK, 2027, plan_ids=wanted)
    assert df["previous_plan_id"].to_list() == wanted
    assert df["current_plan_id"].to_list() == wanted


def test_terminated_row_with_current_id_is_refused() -> None:
    with pytest.raises(CmsFileError, match=r"terminated rows \[2\] also name a current plan id"):
        read_crosswalk(CROSSWALK, 2027, plan_ids=["H9999-003"])


def test_messy_pbp_reads_requested_plans() -> None:
    df = read_pbp(PBP, 2026, plan_ids=["H9999-001", "H5294-014-001"])
    got = {(r["plan_id"], r["field"]): r for r in df.to_dicts()}
    deductible = got[("H9999-001", FieldName.MEDICAL_DEDUCTIBLE)]
    assert deductible["amount"] == Decimal("1234.00")
    moop = got[("H9999-001", FieldName.MOOP_IN_NETWORK)]
    assert (moop["amount"], moop["amount_status"]) == (None, AmountStatus.MISSING)
    seg = got[("H5294-014-001", FieldName.MOOP_IN_NETWORK)]
    assert seg["amount_status"] == AmountStatus.NOT_COVERED


def test_pbp_three_decimals_is_refused() -> None:
    with pytest.raises(
        CmsFileError, match=r"pbp_Section_D.txt: column 'pbp_d_ann_deduct_amt', row 2: '250.555'"
    ):
        read_pbp(PBP, 2026, plan_ids=["H9999-002"])


def test_pbp_duplicates_name_plan_and_rows() -> None:
    with pytest.raises(
        CmsFileError, match=r"pcp_copay has several rows for H9999-003 \(rows \[3, 4\]\)"
    ):
        read_pbp(PBP, 2026, plan_ids=["H9999-003"])


def test_pbp_duplicates_outside_the_slice_and_blank_ids_are_ignored(
    caplog: pytest.LogCaptureFixture,
) -> None:
    # S9999-001 has two rows and two rows have a blank id; neither is a duplicate of ours.
    with caplog.at_level(logging.WARNING):
        df = read_pbp(PBP, 2026, plan_ids=["H9999-001"])
    assert set(df["plan_id"]) == {"H9999-001"}
    assert "pbp_Section_D.txt: ignored 2 rows with a blank plan id" in caplog.text
