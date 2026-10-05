import json
from decimal import Decimal
from pathlib import Path

import pytest
from pdf_factory import make_plan_pdf

from plan_diff.classify import classify_pdf
from plan_diff.cms import read_landscape, read_pbp
from plan_diff.extract import extract_document
from plan_diff.models import (
    Citation,
    CitationMethod,
    Coinsurance,
    Copay,
    ExtractedField,
    FieldName,
    FieldValue,
    Money,
    NotCovered,
    PlanRecord,
    ReviewItem,
    ReviewKind,
    Severity,
    Unit,
    ValidationResult,
    Verdict,
)
from plan_diff.validate import (
    CmsValue,
    accuracy,
    cms_values_for,
    compare,
    review_items,
    write_accuracy,
    write_review_queue,
)

CMS = Path(__file__).resolve().parents[3] / "fixtures" / "cms"
F = FieldName


def _field(name: FieldName, value: FieldValue, unit: Unit | None) -> ExtractedField:
    cite = Citation(document_id="doc", page=2, method=CitationMethod.RULE)
    return ExtractedField(name=name, value=value, unit=unit, citation=cite, confidence=0.9)


def _record(*fields: ExtractedField, plan_id: str = "H9999-001") -> PlanRecord:
    return PlanRecord(
        plan_id=plan_id,
        year=2026,
        carrier="Example Health Plan",
        plan_name="Example Gold Plus (HMO)",
        counties=("Bexar",),
        fields={f.name: f for f in fields},
        documents=("doc",),
    )


def _cms(name: FieldName, value: FieldValue, unit: Unit | None, row: int = 2) -> CmsValue:
    cite = Citation(document_id="pbp.txt", page=row, method=CitationMethod.CMS)
    return CmsValue(field=name, value=value, unit=unit, citation=cite)


def _one(pdf: ExtractedField | None, cms: CmsValue | None, name: FieldName) -> ValidationResult:
    record = _record(*([pdf] if pdf else []))
    results = compare(record, {name: cms} if cms else {})
    return next(r for r in results if r.field == name)


def test_spec_example_4_flag_not_pick(tmp_path: Path) -> None:
    fake = make_plan_pdf(tmp_path)  # specialist $45 per visit; the CMS fixture says $40
    extracted = extract_document(fake.path, classify_pdf(fake.path, document_id="doc"))
    record = _record(*extracted.fields.values())
    pbp = read_pbp(CMS / "pbp_2026", 2026, plan_ids=["H9999-001"])
    land = read_landscape(CMS / "landscape_2026.csv", 2026, plan_ids=["H9999-001"])
    cms = cms_values_for("H9999-001", pbp=pbp, landscape=land, landscape_file="landscape_2026.csv")
    results = compare(record, cms)
    assert len(results) == len(FieldName)
    spec = next(r for r in results if r.field == F.SPECIALIST_COPAY)
    assert spec.verdict == Verdict.MISMATCH
    assert spec.pdf_value == Copay(amount=Decimal("45"))
    assert spec.cms_value == Copay(amount=Decimal("40"))
    assert spec.cms_citation is not None and spec.cms_citation.method == CitationMethod.CMS
    assert spec.cms_citation.document_id == "pbp_b7_health_prof.txt"
    assert spec.cms_citation.page == 1  # first data row of the file
    pcp = next(r for r in results if r.field == F.PCP_COPAY)
    assert pcp.verdict == Verdict.MATCH
    items = [i for i in review_items(results) if i.field == F.SPECIALIST_COPAY]
    assert len(items) == 1
    item = items[0]
    assert item.kind == ReviewKind.PDF_CMS_MISMATCH
    assert item.confidence is not None and item.confidence <= 0.3
    assert "$45.00" in item.reason and "$40.00" in item.reason
    assert [c.method for c in item.evidence] == [CitationMethod.RULE, CitationMethod.CMS]
    assert item.evidence[0].page == fake.field_pages[F.SPECIALIST_COPAY]
    row = next(r for r in accuracy(results).rows if r.field == F.SPECIALIST_COPAY)
    assert (row.mismatched, row.matched, row.method) == (1, 0, CitationMethod.RULE)
    premium = next(r for r in results if r.field == F.MONTHLY_PREMIUM)
    assert premium.verdict == Verdict.MATCH  # Landscape premium $0.00 vs PDF $0 per month
    out = tmp_path / "validation.json"
    out.write_text(json.dumps([json.loads(r.model_dump_json()) for r in results]))
    assert '"45.00"' in out.read_text() and '"40.00"' in out.read_text()


def test_every_verdict() -> None:
    pdf = _field(F.PCP_COPAY, Copay(amount=Decimal("10")), Unit.PER_VISIT)
    same = _cms(F.PCP_COPAY, Copay(amount=Decimal("10.00")), Unit.PER_VISIT)
    off = _cms(F.PCP_COPAY, Copay(amount=Decimal("10.01")), Unit.PER_VISIT)
    assert _one(pdf, same, F.PCP_COPAY).verdict == Verdict.MATCH
    assert _one(pdf, off, F.PCP_COPAY).verdict == Verdict.MISMATCH  # exact to the cent
    assert _one(pdf, None, F.PCP_COPAY).verdict == Verdict.NOT_IN_CMS
    missing = _one(None, same, F.PCP_COPAY)
    assert missing.verdict == Verdict.NOT_EXTRACTED and missing.cms_value is not None
    assert _one(None, None, F.PCP_COPAY).verdict == Verdict.NOT_EXTRACTED


def test_copay_vs_coinsurance_is_a_mismatch() -> None:
    pdf = _field(F.OUTPATIENT_SURGERY, Coinsurance(percent=Decimal("20")), None)
    cms = _cms(F.OUTPATIENT_SURGERY, Copay(amount=Decimal("20")), Unit.PER_VISIT)
    result = _one(pdf, cms, F.OUTPATIENT_SURGERY)
    assert result.verdict == Verdict.MISMATCH
    assert result.reason is not None and "coinsurance" in result.reason


def test_units_must_agree_outside_allowances() -> None:
    pdf = _field(F.INPATIENT_STAY, Copay(amount=Decimal("295")), Unit.PER_STAY)
    cms = _cms(F.INPATIENT_STAY, Copay(amount=Decimal("295")), Unit.PER_DAY)
    assert _one(pdf, cms, F.INPATIENT_STAY).reason == "units differ"


@pytest.mark.parametrize(
    ("pdf_unit", "cms_unit", "cms_amount", "verdict", "reason"),
    [
        (Unit.PER_QUARTER, Unit.PER_YEAR, "200", Verdict.MATCH, None),
        (Unit.PER_QUARTER, Unit.PER_YEAR, "150", Verdict.MISMATCH, "yearly amounts differ"),
        (Unit.PER_QUARTER, None, "200", Verdict.MISMATCH, "period not comparable"),
        (None, Unit.PER_YEAR, "200", Verdict.MISMATCH, "period not comparable"),
    ],
)
def test_allowances_compare_yearly(
    pdf_unit: Unit | None, cms_unit: Unit | None, cms_amount: str, verdict: Verdict, reason: str
) -> None:
    pdf = _field(F.OTC_ALLOWANCE, Money(amount=Decimal("50")), pdf_unit)
    cms = _cms(F.OTC_ALLOWANCE, Money(amount=Decimal(cms_amount)), cms_unit)
    result = _one(pdf, cms, F.OTC_ALLOWANCE)
    assert (result.verdict, result.reason) == (verdict, reason)
    assert result.pdf_value == Money(amount=Decimal("50"))  # the page value, never rewritten


def test_not_covered_matches_cms_not_covered(tmp_path: Path) -> None:
    pdf = _field(F.DENTAL_ALLOWANCE, NotCovered(), None)
    assert _one(pdf, _cms(F.DENTAL_ALLOWANCE, NotCovered(), None), F.DENTAL_ALLOWANCE).verdict == (
        Verdict.MATCH
    )
    pbp = tmp_path / "pbp"
    pbp.mkdir()
    for src in (CMS / "pbp_2026").iterdir():
        text = src.read_text()
        if src.name == "pbp_b16_dental.txt":
            head, *rows = text.splitlines()
            rows = [r.rsplit("\t", 1)[0] + "\tNot covered" for r in rows]
            text = "\n".join([head, *rows]) + "\n"
        (pbp / src.name).write_text(text)
    cms = cms_values_for("H9999-001", pbp=read_pbp(pbp, 2026, plan_ids=["H9999-001"]))
    assert cms[F.DENTAL_ALLOWANCE].value == NotCovered()
    assert F.MONTHLY_PREMIUM not in cms  # no Landscape given: not in CMS, never guessed


def _item(sev: Severity, plan: str | None, field: FieldName | None, tag: str) -> ReviewItem:
    return ReviewItem(
        kind=ReviewKind.PDF_CMS_MISMATCH,
        plan_id=plan,
        year=2026,
        field=field,
        evidence=(),
        reason=tag,
        severity=sev,
    )


def test_review_queue_order_is_stable(tmp_path: Path) -> None:
    items = [
        _item(Severity.LOW, "H9999-001", F.PCP_COPAY, "a"),
        _item(Severity.HIGH, "H9999-002", F.MOOP_IN_NETWORK, "b"),
        _item(Severity.MEDIUM, None, None, "c"),
        _item(Severity.HIGH, "H9999-001", F.PCP_COPAY, "d"),
        _item(Severity.HIGH, "H9999-001", F.PCP_COPAY, "e"),
        _item(Severity.HIGH, "H9999-001", F.MONTHLY_PREMIUM, "f"),
    ]
    out = tmp_path / "review_queue.jsonl"
    write_review_queue(items, out)
    first = out.read_text()
    tags = [json.loads(line)["reason"] for line in first.splitlines()]
    assert tags == ["f", "d", "e", "b", "c", "a"]
    write_review_queue(list(reversed(items)), out)
    again = [json.loads(line)["reason"] for line in out.read_text().splitlines()]
    assert again == ["f", "e", "d", "b", "c", "a"]  # ties keep their input order


def test_accuracy_math(tmp_path: Path) -> None:
    pdf = _field(F.PCP_COPAY, Copay(amount=Decimal("10")), Unit.PER_VISIT)
    results = [
        _one(pdf, _cms(F.PCP_COPAY, Copay(amount=Decimal("10")), Unit.PER_VISIT), F.PCP_COPAY),
        _one(pdf, _cms(F.PCP_COPAY, Copay(amount=Decimal("10")), Unit.PER_VISIT), F.PCP_COPAY),
        _one(pdf, _cms(F.PCP_COPAY, Copay(amount=Decimal("12")), Unit.PER_VISIT), F.PCP_COPAY),
        _one(pdf, None, F.PCP_COPAY),
        _one(None, None, F.URGENT_CARE),
    ]
    table = accuracy(results)
    pcp = next(r for r in table.rows if r.field == F.PCP_COPAY)
    assert (pcp.matched, pcp.mismatched, pcp.not_in_cms, pcp.not_extracted) == (2, 1, 1, 0)
    assert pcp.match_rate == pytest.approx(2 / 3)
    urgent = next(r for r in table.rows if r.field == F.URGENT_CARE)
    assert urgent.not_extracted == 1 and urgent.match_rate is None
    total = next(r for r in table.rows if r.field is None)
    assert (total.matched, total.mismatched, total.not_extracted) == (2, 1, 1)
    out = tmp_path / "accuracy.json"
    write_accuracy(table, out)
    assert json.loads(out.read_text())["rows"][0]["field"] == "pcp_copay"
