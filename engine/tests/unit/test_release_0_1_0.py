"""Release 0.1.0: a not comparable verdict, version, accuracy labels, and the network guard."""

import json
import socket
import tomllib
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
from test_diff import money, plan, renewal
from test_validate import _cms, _field, _one

from plan_diff import __version__
from plan_diff.diff import diff_plans
from plan_diff.models import (
    AccuracyTable,
    Citation,
    CitationMethod,
    Copay,
    FieldName,
    Money,
    ReviewKind,
    Severity,
    Unit,
    ValidationResult,
    Verdict,
)
from plan_diff.validate import accuracy, review_items

F = FieldName
ENGINE = Path(__file__).resolve().parents[2]


def _period_not_comparable() -> ValidationResult:
    pdf = _field(F.OTC_ALLOWANCE, Money(amount=Decimal("50")), Unit.PER_QUARTER)
    return _one(pdf, _cms(F.OTC_ALLOWANCE, Money(amount=Decimal("200")), None), F.OTC_ALLOWANCE)


def _unit_not_comparable() -> ValidationResult:
    pdf = _field(F.INPATIENT_STAY, Copay(amount=Decimal("295")), Unit.PER_STAY)
    cms = _cms(F.INPATIENT_STAY, Copay(amount=Decimal("295")), Unit.PER_DAY)
    return _one(pdf, cms, F.INPATIENT_STAY)


def _as(result: ValidationResult, verdict: str) -> ValidationResult:
    data = json.loads(result.model_dump_json()) | {"verdict": verdict}
    return ValidationResult.model_validate_json(json.dumps(data))


def test_period_and_unit_not_comparable_are_their_own_verdict() -> None:
    period, unit = _period_not_comparable(), _unit_not_comparable()
    assert (period.verdict, period.reason) == (Verdict.NOT_COMPARABLE, "period not comparable")
    assert (unit.verdict, unit.reason) == (Verdict.NOT_COMPARABLE, "unit not comparable")


def test_not_comparable_cannot_pose_as_a_mismatch_or_the_reverse() -> None:
    with pytest.raises(ValueError, match="does not fit"):
        _as(_period_not_comparable(), "mismatch")
    pdf = _field(F.PCP_COPAY, Copay(amount=Decimal("10")), Unit.PER_VISIT)
    off = _one(pdf, _cms(F.PCP_COPAY, Copay(amount=Decimal("12")), Unit.PER_VISIT), F.PCP_COPAY)
    assert off.verdict == Verdict.MISMATCH
    with pytest.raises(ValueError, match="does not fit"):
        _as(off, "not_comparable")


def test_accuracy_counts_not_comparable_apart_and_outside_the_match_rate() -> None:
    pdf = _field(F.INPATIENT_STAY, Copay(amount=Decimal("295")), Unit.PER_DAY)
    same = _cms(F.INPATIENT_STAY, Copay(amount=Decimal("295")), Unit.PER_DAY)
    off = _cms(F.INPATIENT_STAY, Copay(amount=Decimal("300")), Unit.PER_DAY)
    results = [
        _one(pdf, same, F.INPATIENT_STAY),
        _one(pdf, off, F.INPATIENT_STAY),
        _unit_not_comparable(),
        _unit_not_comparable(),
    ]
    row = next(r for r in accuracy(results).rows if r.field == F.INPATIENT_STAY)
    assert (row.matched, row.mismatched, row.not_comparable) == (1, 1, 2)
    assert row.match_rate == pytest.approx(0.5)  # 1 / (1 + 1); not comparable left out
    only = next(r for r in accuracy([_period_not_comparable()]).rows if r.field is None)
    assert only.not_comparable == 1 and only.match_rate is None


def test_not_comparable_goes_to_review_as_its_own_kind() -> None:
    (item,) = review_items([_unit_not_comparable()])
    assert item.kind == ReviewKind.NOT_COMPARABLE
    assert item.severity == Severity.MEDIUM
    assert [c.method for c in item.evidence] == [CitationMethod.RULE, CitationMethod.CMS]
    assert "not comparable" in item.reason


def test_not_comparable_on_a_threshold_field_leaves_the_flag_undecided() -> None:
    old, new = plan(2026), plan(2027, moop_in_network=money("4500", Unit.PER_YEAR))
    pdf = new.fields[F.MOOP_IN_NETWORK]
    result = ValidationResult(
        plan_id=new.plan_id,
        year=new.year,
        field=F.MOOP_IN_NETWORK,
        pdf_value=pdf.value,
        cms_value=pdf.value,
        verdict=Verdict.NOT_COMPARABLE,
        pdf_citation=pdf.citation,
        cms_citation=Citation(document_id="pbp_Section_D.txt", page=2, method=CitationMethod.CMS),
        pdf_unit=Unit.PER_YEAR,
        cms_unit=Unit.PER_MONTH,
        reason="unit not comparable",
    )
    diff = diff_plans(old, new, renewal(), old.counties, new.counties, validation=[result])
    assert diff.shop_again is None and diff.reasons == ()
    item = next(i for i in diff.review if i.field == F.MOOP_IN_NETWORK)
    assert item.kind == ReviewKind.SHOP_AGAIN_UNCERTAIN and item.severity == Severity.HIGH
    assert "cannot be checked against CMS" in item.reason


def test_version_is_0_1_0_everywhere() -> None:
    project = tomllib.loads((ENGINE / "pyproject.toml").read_text())["project"]
    assert __version__ == project["version"] == "0.1.0"


def test_accuracy_table_carries_its_labels() -> None:
    table = AccuracyTable(
        rows=(), plans=("H9999-001",), years=(2026, 2027), run_id="demo", as_of="2026-10-05"
    )
    assert table.model_dump()["as_of"] == "2026-10-05"
    old = AccuracyTable.model_validate({"rows": []})  # PR 7 JSON still loads
    assert old.run_id is None and old.plans == ()


def test_network_guard_blocks_real_connections() -> None:
    with pytest.raises(RuntimeError, match="network is off in tests"):
        socket.create_connection(("127.0.0.1", 9))
    transport = httpx.MockTransport(lambda _: httpx.Response(200, content=b"ok"))
    with httpx.Client(transport=transport) as client:
        assert client.get("https://example.test/").content == b"ok"
