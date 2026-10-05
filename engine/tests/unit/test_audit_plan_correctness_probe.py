"""Independent, synthetic, offline correctness regressions. Expected behavior assertions.

Run from the audit root with audit_run.py. No repository files/PDFs/network are written.
Failure on an unpatched snapshot demonstrates the finding; no xfail hides it.
"""

from pathlib import Path

import pytest
from pydantic import ValidationError

from plan_diff.classify import classify_pages
from plan_diff.cms.layouts import PBP_LAYOUTS
from plan_diff.cms.readers import _pbp_value
from plan_diff.extract import extract_pages
from plan_diff.extract.extractor import ExtractionResult
from plan_diff.extract.values import FAMILIES, parse_value
from plan_diff.models import (
    Citation,
    CitationMethod,
    Coinsurance,
    Copay,
    ExtractedField,
    FieldName,
    Money,
    ReviewKind,
    Unit,
    ValidationResult,
    Verdict,
)
from plan_diff.models.validation import disagreement
from plan_diff.run.documents import Document, _targets, merge_fields
from plan_diff.validate.validator import _typed

PARSERS = {p.field: p for family in FAMILIES.values() for p in family}
F = FieldName


def classification(doc="sb", year=2027, kind="SB"):
    title = {
        "SB": "Summary of Benefits",
        "EOC": "Evidence of Coverage",
        "ANOC": "Annual Notice of Change",
    }[kind]
    return classify_pages([f"Example Health Plan {year} {title}\nH9999-001"], document_id=doc)


def field(name, amount, doc="sb", method=CitationMethod.RULE, confidence=0.9):
    money = name in {F.MONTHLY_PREMIUM, F.MOOP_IN_NETWORK, F.DRUG_DEDUCTIBLE}
    unit = (
        Unit.PER_MONTH if name == F.MONTHLY_PREMIUM else Unit.PER_YEAR if money else Unit.PER_VISIT
    )
    return ExtractedField(
        name=name,
        value=Money(amount=amount) if money else Copay(amount=amount),
        unit=unit,
        citation=Citation(document_id=doc, page=1, method=method, text=f"${amount}"),
        confidence=confidence,
    )


def document(value, kind="SB", year=2027):
    c = classification(value.citation.document_id, year, kind)
    return Document(
        Path("unused.pdf"),
        c,
        ExtractionResult(document_id=c.document_id, fields={value.name: value}, review_items=()),
    )


def test_p01_not_covered_does_not_erase_another_networks_100_percent():
    actual = parse_value(
        "Out-of-network: not covered; In-network: 100% coinsurance", PARSERS[F.URGENT_CARE]
    )
    assert actual is not None
    assert actual.value == Coinsurance(percent="100"), actual


def test_p02_one_network_marker_cannot_resolve_two_same_network_amounts():
    result = extract_pages(["Maximum out-of-pocket In-network: $3,400 to $5,000"], classification())
    actual = result.fields[F.MOOP_IN_NETWORK]
    assert actual.confidence < 0.7, actual


def test_p03_cms_coinsurance_range_is_not_a_match_to_its_lower_bound():
    spec = PBP_LAYOUTS[2026].fields[F.PCP_COPAY]
    assert spec is not None
    row = {
        "source_row": 1,
        "pbp_b7a_copay_amt_mc_min": "",
        "pbp_b7a_copay_amt_mc_max": "",
        "pbp_b7a_coins_pct_mc_min": "10",
        "pbp_b7a_coins_pct_mc_max": "30",
    }
    output = _pbp_value(row, spec, Path("synthetic_pbp.txt"))
    value = _typed(
        F.PCP_COPAY, output.get("amount"), output["amount_status"], output.get("percent")
    )
    assert value is not None
    actual = disagreement(
        F.PCP_COPAY,
        Coinsurance(percent="10"),
        Unit.PER_VISIT,
        value,
        Unit.PER_VISIT,
        cms_max=output.get("max_amount"),
    )
    assert actual is not None, output


def test_p04_unit_incomparability_precedes_numeric_difference():
    actual = disagreement(
        F.INPATIENT_STAY, Copay(amount="100"), Unit.PER_STAY, Copay(amount="200"), Unit.PER_DAY
    )
    assert actual == "unit not comparable", actual


def test_p05_validation_rejects_values_without_citations():
    with pytest.raises(ValidationError):
        ValidationResult(
            plan_id="H9999-001",
            year=2027,
            field=F.MONTHLY_PREMIUM,
            pdf_value=Money(amount="25"),
            cms_value=Money(amount="25"),
            pdf_unit=Unit.PER_MONTH,
            cms_unit=Unit.PER_MONTH,
            verdict=Verdict.MATCH,
            pdf_citation=None,
            cms_citation=None,
        )


def test_p06_booklet_with_first_plan_in_title_still_targets_second_requested_plan():
    texts = [
        "Example Health Plan 2027 Summary of Benefits\nH9999-001\nMonthly plan premium $0",
        "Benefits for H9999-001",
        "Specialist visits $10",
        "H9999-002\nMonthly plan premium $45",
    ]
    result = classify_pages(texts[:3], document_id="booklet")
    targets, problems = _targets(result, texts, ["H9999-002"])
    actual = [c.plan_id.value for c, _ in targets]
    assert not problems and actual == ["H9999-002"], (actual, problems)


def test_p07_anoc_single_prior_year_value_is_not_current_year_evidence():
    result = extract_pages(
        ["Monthly plan premium $25 for 2026. The 2027 amount is listed elsewhere."],
        classification(kind="ANOC"),
    )
    actual = result.fields.get(F.MONTHLY_PREMIUM)
    assert actual is None or actual.confidence < 0.7, actual


def test_p08_cross_document_conflict_blocks_deciding_confidence_saved_fix():
    sb = field(F.MONTHLY_PREMIUM, "25", "sb")
    eoc = field(F.MONTHLY_PREMIUM, "0", "eoc")
    fields, queue = merge_fields([document(sb), document(eoc, "EOC")])
    assert any(r.kind == ReviewKind.CONFLICTING_VALUES for r in queue)
    assert fields[F.MONTHLY_PREMIUM].confidence < 0.7, fields[F.MONTHLY_PREMIUM]


def test_p09_llm_sb_candidate_never_overrides_a_deterministic_eoc_value():
    pytest.importorskip("plan_diff.extract.llm_fallback")
    candidate = field(F.MONTHLY_PREMIUM, "25", "sb", CitationMethod.LLM, 0.55)
    rule = field(F.MONTHLY_PREMIUM, "0", "eoc")
    fields, _ = merge_fields([document(candidate), document(rule, "EOC")])
    assert fields[F.MONTHLY_PREMIUM].value == rule.value, fields[F.MONTHLY_PREMIUM]
    assert fields[F.MONTHLY_PREMIUM].citation.method == CitationMethod.RULE


def test_p10_no_part_d_contradiction_retains_negative_evidence_for_review():
    # On base this is also unresolved: only the positive Tier 3 row is retained.
    result = extract_pages(["Plan does not cover Part D.\nTier 3 $5"], classification())
    actual = result.fields[F.DRUG_TIER_3]
    assert actual.confidence < 0.7, actual
    assert any(
        any("does not cover Part D" in (c.text or "") for c in r.evidence)
        for r in result.review_items
    ), result.review_items


def test_p11_out_of_range_percent_becomes_unreadable_review_instead_of_exception():
    result = extract_pages(["Urgent care 120% coinsurance"], classification())
    assert F.URGENT_CARE not in result.fields
    assert any(
        r.field == F.URGENT_CARE and r.kind == ReviewKind.NOT_EXTRACTED for r in result.review_items
    )


def test_control_local_not_covered_100_percent_remains_one_value():
    actual = parse_value("Not covered (you pay 100%)", PARSERS[F.URGENT_CARE])
    assert actual is not None and actual.value.kind == "not_covered" and not actual.multiple


def test_control_unambiguous_network_pick_stays_above_confidence_floor():
    result = extract_pages(
        ["Maximum out-of-pocket $3,400 in-network / $6,700 out-of-network"], classification()
    )
    assert result.fields[F.MOOP_IN_NETWORK].value == Money(amount="3400")
    assert result.fields[F.MOOP_IN_NETWORK].confidence >= 0.7


def test_control_anoc_explicit_current_year_single_value_can_be_read():
    result = extract_pages(["Monthly plan premium $25 for 2027."], classification(kind="ANOC"))
    assert result.fields[F.MONTHLY_PREMIUM].value == Money(amount="25")
