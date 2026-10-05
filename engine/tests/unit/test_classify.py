from pathlib import Path

import pdfplumber
import pytest
from pdf_factory import LABELS, make_plan_pdf
from pypdf import PdfReader

from plan_diff.classify import ClassifyStatus, classify_pages, classify_pdf, document_type_of
from plan_diff.models import DocumentType, FieldName, ReviewKind


def test_factory_pdf_opens_with_expected_pages_and_fields(tmp_path: Path) -> None:
    values = {
        FieldName.MONTHLY_PREMIUM: "$25 per month",
        FieldName.OTC_ALLOWANCE: "$60 per quarter",
    }
    fake = make_plan_pdf(tmp_path, year=2027, values=values)
    assert fake.page_count == 2
    assert len(PdfReader(fake.path).pages) == 2
    with pdfplumber.open(fake.path) as pdf:
        assert len(pdf.pages) == 2
        texts = [page.extract_text() or "" for page in pdf.pages]
    assert "Example Health Plan 2027 Summary of Benefits" in texts[0]
    assert "H9999-001" in texts[0]
    assert set(fake.field_pages) == set(FieldName)
    assert set(fake.field_pages.values()) == {1, 2}
    for field, page in fake.field_pages.items():
        assert LABELS[field] in texts[page - 1]
    assert "$25 per month" in texts[fake.field_pages[FieldName.MONTHLY_PREMIUM] - 1]
    assert "$60 per quarter" in texts[fake.field_pages[FieldName.OTC_ALLOWANCE] - 1]


@pytest.mark.parametrize("doc_type", [DocumentType.SB, DocumentType.EOC, DocumentType.ANOC])
def test_classifier_labels_each_variant_with_page_citations(
    tmp_path: Path, doc_type: DocumentType
) -> None:
    fake = make_plan_pdf(tmp_path, year=2027, document_type=doc_type)
    result = classify_pdf(fake.path, document_id="fake-doc")
    assert result.status is ClassifyStatus.SURE
    assert result.review_item is None
    assert document_type_of(result) is doc_type
    assert result.plan_id.value == "H9999-001"
    assert result.year.value == "2027"  # the ANOC also names 2026 in its body; the title wins
    assert result.carrier.value == "Example Health Plan"
    for finding in (result.document_type, result.plan_id, result.year, result.carrier):
        assert finding.page == 1
        assert finding.evidence[0].document_id == "fake-doc"
        assert finding.evidence[0].method == "rule"
        assert finding.confidence > 0.5
    assert result.year.confidence == 0.95  # read from the title line


def test_two_plan_ids_is_unsure_with_a_review_item(tmp_path: Path) -> None:
    fake = make_plan_pdf(tmp_path, plan_ids=("H9999-001", "H9999-002"))
    result = classify_pdf(fake.path)
    assert result.status is ClassifyStatus.UNSURE
    assert result.plan_id.value is None
    assert result.plan_id.problem == "ambiguous"
    assert [c.text for c in result.plan_id.evidence] == ["H9999-001", "H9999-002"]
    item = result.review_item
    assert item is not None
    assert item.kind is ReviewKind.UNCLASSIFIED_DOCUMENT
    assert item.plan_id is None
    assert item.year == 2026
    assert "plan id" in item.reason and "H9999-002" in item.reason
    assert {c.page for c in item.evidence} == {1}


def test_no_year_is_unsure(tmp_path: Path) -> None:
    fake = make_plan_pdf(tmp_path, year=None)
    result = classify_pdf(fake.path)
    assert result.status is ClassifyStatus.UNSURE
    assert result.year.problem == "missing"
    assert result.year.confidence == 0.0
    assert result.review_item is not None
    assert result.review_item.plan_id == "H9999-001"
    assert "plan year" in result.review_item.reason


def test_two_years_on_title_lines_is_unsure() -> None:
    pages = ["Example Health Plan 2026 Summary of Benefits\nH9999-001\n2027 Summary of Benefits"]
    result = classify_pages(pages, document_id="doc")
    assert result.status is ClassifyStatus.UNSURE
    assert result.year.problem == "ambiguous"


def test_carrier_alias_maps_to_canonical_name(tmp_path: Path) -> None:
    fake = make_plan_pdf(tmp_path, carrier="Superior HealthPlan", plan_ids=("H5294-014",))
    result = classify_pdf(fake.path)
    assert result.status is ClassifyStatus.SURE
    assert result.carrier.value == "Wellcare"
    assert result.carrier.evidence[0].text == "Superior HealthPlan"


def test_custom_alias_table_and_unknown_carrier() -> None:
    pages = ["Acme Care 2026 Evidence of Coverage\nH1234-001"]
    assert classify_pages(pages, document_id="d").carrier.problem == "missing"
    custom = classify_pages(pages, document_id="d", carrier_aliases={"acme care": "Acme"})
    assert custom.status is ClassifyStatus.SURE
    assert custom.carrier.value == "Acme"
    assert custom.document_type.value == "EOC"


def test_dollar_amounts_are_not_years_and_segments_are_dropped() -> None:
    pages = ["Humana 2026 Summary of Benefits\nH0028-030-001\nDeductible $2050 or 2,020.00"]
    result = classify_pages(pages, document_id="d")
    assert result.status is ClassifyStatus.SURE
    assert result.year.value == "2026"
    assert result.plan_id.value == "H0028-030"
