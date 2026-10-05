from datetime import UTC, datetime
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import BaseModel, TypeAdapter, ValidationError

from plan_diff.models import (
    Citation,
    CitationMethod,
    Coinsurance,
    Copay,
    CrosswalkStatus,
    Direction,
    DocumentType,
    ExtractedField,
    FieldChange,
    FieldName,
    Money,
    NotCovered,
    PlanDiff,
    PlanId,
    PlanRecord,
    ReviewItem,
    ReviewKind,
    Severity,
    SourceDocument,
    SourcesManifest,
    Unit,
    ValidationResult,
    Verdict,
    category_for,
    crosswalk_status_from_cms,
)

plan_id = TypeAdapter(PlanId)
cite = Citation(document_id="sb-h0028-030-2026", page=3, method=CitationMethod.RULE, text="$0")


def premium(amount: str, doc: str = "sb-h0028-030-2026") -> ExtractedField:
    return ExtractedField(
        name=FieldName.MONTHLY_PREMIUM,
        value=Money(amount=Decimal(amount)),
        unit=Unit.PER_MONTH,
        citation=Citation(document_id=doc, page=1, method=CitationMethod.RULE),
        confidence=0.95,
    )


@pytest.mark.parametrize("good", ["H0028-030", "H5294-014", "H5294-014-001"])
def test_plan_id_accepts_real_shapes(good: str) -> None:
    assert plan_id.validate_python(good) == good


@pytest.mark.parametrize(
    "bad",
    [
        "h0028-030",
        "H028-030",
        "H0028030",
        "H0028-30",
        "H0028-030-1",
        " H0028-030",
        "",
        "H\u0660028-030",
    ],
)
def test_plan_id_rejects_bad_shapes(bad: str) -> None:
    with pytest.raises(ValidationError):
        plan_id.validate_python(bad)


@given(st.from_regex(r"\AH[0-9]{4}-[0-9]{3}(-[0-9]{3})?\Z"))
def test_plan_id_accepts_any_valid_pattern(value: str) -> None:
    assert plan_id.validate_python(value) == value


def test_field_name_has_exactly_the_15_spec_fields() -> None:
    assert [f.value for f in FieldName] == [
        "monthly_premium",
        "medical_deductible",
        "moop_in_network",
        "pcp_copay",
        "specialist_copay",
        "emergency_room",
        "urgent_care",
        "inpatient_stay",
        "outpatient_surgery",
        "drug_deductible",
        "drug_tier_1",
        "drug_tier_2",
        "drug_tier_3",
        "dental_allowance",
        "otc_allowance",
    ]
    assert all(category_for(f) for f in FieldName)


def test_money_rejects_float_and_keeps_two_places() -> None:
    with pytest.raises(ValidationError):
        Money(amount=0.1)  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        Money(amount=Decimal("1.005"))
    assert str(Money(amount=Decimal("25")).amount) == "25.00"
    assert Money.model_validate_json('{"kind": "money", "amount": "25"}').amount == Decimal("25.00")
    assert Money(amount=25).model_dump_json() == '{"kind":"money","amount":"25.00"}'  # type: ignore[arg-type]


def test_copay_and_coinsurance_reject_float() -> None:
    with pytest.raises(ValidationError):
        Copay(amount=45.0)  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        Coinsurance(percent=120)  # type: ignore[arg-type]


def test_models_are_frozen_and_forbid_extra_fields() -> None:
    with pytest.raises(ValidationError):
        cite.page = 4  # type: ignore[misc]
    with pytest.raises(ValidationError):
        Citation(document_id="x", page=1, method=CitationMethod.CMS, extra="no")  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        Citation(document_id="x", page=0, method=CitationMethod.CMS)
    with pytest.raises(ValidationError):
        Citation(document_id="x", page=1, method=CitationMethod.LLM, text="a" * 201)


def test_plan_record_keys_must_match_field_names_and_cite_its_documents() -> None:
    with pytest.raises(ValidationError):
        PlanRecord(
            plan_id="H0028-030",
            year=2026,
            carrier="Humana",
            plan_name="Humana Gold Plus H0028-030 (HMO)",
            counties=("Bexar",),
            fields={FieldName.MEDICAL_DEDUCTIBLE: premium("0")},
            documents=("sb-h0028-030-2026",),
        )
    with pytest.raises(ValidationError):
        PlanRecord(
            plan_id="H0028-030",
            year=2026,
            carrier="Humana",
            plan_name="Humana Gold Plus",
            counties=("Bexar",),
            fields={FieldName.MONTHLY_PREMIUM: premium("0", doc="not-listed")},
            documents=("sb-h0028-030-2026",),
        )


def test_consolidated_diff_requires_new_plan_id() -> None:
    with pytest.raises(ValidationError):
        PlanDiff(
            old_plan_id="H5294-016",
            new_plan_id=None,
            old_year=2026,
            new_year=2027,
            crosswalk_status=CrosswalkStatus.CONSOLIDATED,
            changes=(),
            shop_again=True,
            reasons=("plan consolidated",),
        )


def test_shop_again_needs_reasons() -> None:
    with pytest.raises(ValidationError):
        PlanDiff(
            old_plan_id="H0028-030",
            new_plan_id="H0028-030",
            old_year=2026,
            new_year=2027,
            crosswalk_status=CrosswalkStatus.CONTINUING,
            changes=(),
            shop_again=True,
            reasons=(),
        )


def test_cms_crosswalk_labels_map_to_status() -> None:
    assert crosswalk_status_from_cms("Consolidated Renewal Plan") is CrosswalkStatus.CONSOLIDATED
    assert crosswalk_status_from_cms(" terminated/non-renewed contract ") is (
        CrosswalkStatus.TERMINATED
    )
    with pytest.raises(ValueError):
        crosswalk_status_from_cms("Something new")


def examples() -> list[BaseModel]:
    old, new = premium("0"), premium("25", doc="sb-h0028-030-2027")
    record = PlanRecord(
        plan_id="H0028-030",
        year=2026,
        carrier="  Humana   Inc ",
        plan_name="Humana Gold Plus H0028-030 (HMO)",
        counties=("Bexar", "Comal"),
        fields={
            FieldName.MONTHLY_PREMIUM: old,
            FieldName.SPECIALIST_COPAY: ExtractedField(
                name=FieldName.SPECIALIST_COPAY,
                value=Copay(amount=Decimal("45")),
                unit=Unit.PER_VISIT,
                citation=cite,
                confidence=0.9,
            ),
            FieldName.INPATIENT_STAY: ExtractedField(
                name=FieldName.INPATIENT_STAY,
                value=Coinsurance(percent=Decimal("20")),
                unit=Unit.PER_STAY,
                citation=cite,
                confidence=0.8,
            ),
            FieldName.DENTAL_ALLOWANCE: ExtractedField(
                name=FieldName.DENTAL_ALLOWANCE,
                value=NotCovered(),
                unit=None,
                citation=cite,
                confidence=1.0,
            ),
        },
        documents=("sb-h0028-030-2026",),
    )
    source = SourceDocument(
        document_id="sb-h0028-030-2026",
        url="https://example.com/sb.pdf",
        sha256="a" * 64,
        size_bytes=1024,
        retrieved_at=datetime(2026, 10, 5, tzinfo=UTC),
        carrier="Humana",
        plan_id="H0028-030",
        year=2026,
        document_type=DocumentType.SB,
    )
    unpinned = source.model_copy(
        update={"document_id": "eoc", "sha256": None, "size_bytes": None, "retrieved_at": None}
    )
    return [
        record,
        SourcesManifest(documents=(source, unpinned)),
        ValidationResult(
            plan_id="H0028-030",
            year=2026,
            field=FieldName.SPECIALIST_COPAY,
            pdf_value=Copay(amount=Decimal("45")),
            cms_value=Copay(amount=Decimal("40")),
            verdict=Verdict.MISMATCH,
            pdf_citation=cite,
            cms_citation=Citation(document_id="pbp-2026", page=12, method=CitationMethod.CMS),
        ),
        PlanDiff(
            old_plan_id="H0028-030",
            new_plan_id="H0028-030",
            old_year=2026,
            new_year=2027,
            crosswalk_status=CrosswalkStatus.CONTINUING,
            changes=(
                FieldChange(
                    field=FieldName.MONTHLY_PREMIUM,
                    old=old,
                    new=new,
                    category=category_for(FieldName.MONTHLY_PREMIUM),
                    direction=Direction.INCREASED,
                ),
            ),
            shop_again=True,
            reasons=("premium up $25 a month",),
        ),
        ReviewItem(
            kind=ReviewKind.PDF_CMS_MISMATCH,
            plan_id="H0028-030",
            year=2026,
            field=FieldName.SPECIALIST_COPAY,
            evidence=(cite,),
            reason="PDF says $45, CMS PBP says $40",
            severity=Severity.HIGH,
        ),
    ]


@pytest.mark.parametrize("model", examples(), ids=lambda m: type(m).__name__)
def test_every_model_round_trips_through_json(model: BaseModel) -> None:
    assert type(model).model_validate_json(model.model_dump_json()) == model


def test_carrier_whitespace_is_normalized() -> None:
    record = examples()[0]
    assert isinstance(record, PlanRecord)
    assert record.carrier == "Humana Inc"


def test_pinned_source_needs_size_and_date_and_ids_are_unique() -> None:
    source = examples()[1]
    assert isinstance(source, SourcesManifest)
    doc = source.documents[0]
    with pytest.raises(ValidationError):
        SourceDocument.model_validate({**doc.model_dump(), "size_bytes": None})
    with pytest.raises(ValidationError):
        SourcesManifest(documents=(doc, doc))


def test_validation_verdict_must_fit_the_values() -> None:
    with pytest.raises(ValidationError):
        ValidationResult(
            plan_id="H0028-030",
            year=2026,
            field=FieldName.PCP_COPAY,
            pdf_value=None,
            cms_value=Copay(amount=Decimal("0")),
            verdict=Verdict.MATCH,
            pdf_citation=None,
            cms_citation=None,
        )


def test_source_without_url_needs_a_note_and_carrier_docs_need_a_plan() -> None:
    manifest = examples()[1]
    assert isinstance(manifest, SourcesManifest)
    unpinned = manifest.documents[1].model_dump()
    SourceDocument.model_validate({**unpinned, "url": None, "note": "find by hand"})
    with pytest.raises(ValidationError):
        SourceDocument.model_validate({**unpinned, "url": None})
    with pytest.raises(ValidationError):
        SourceDocument.model_validate({**unpinned, "plan_id": None})
    SourceDocument.model_validate({**unpinned, "plan_id": None, "document_type": "CMS_PBP"})
