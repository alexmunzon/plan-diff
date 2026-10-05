"""PR 15: the plan id forms in the real carrier documents, and multi-plan booklets.

The short strings below are copied from the pinned public documents (sources/manifest.json), each
well under the 200 character citation limit. No PDF is committed."""

import pytest

from plan_diff.classify import ClassifyStatus, classify_pages
from plan_diff.classify.booklet import PageRange, mask_pages, plan_pages, plans_named
from plan_diff.models import normalize_plan_id
from plan_diff.run.documents import _targets


@pytest.mark.parametrize(
    ("text", "canonical"),
    [
        ("H5294_014", "H5294-014"),
        ("H5294 | 014 | 000", "H5294-014"),
        ("H5294, Plan 014, 000", "H5294-014"),
        ("H5294, Plan 014, 001", "H5294-014-001"),
        ("H0028-030", "H0028-030"),
    ],
)
def test_real_id_forms_normalize(text: str, canonical: str) -> None:
    assert normalize_plan_id(text) == canonical


@pytest.mark.parametrize(
    ("first_page", "plan_id"),
    [
        # Wellcare 2026 and 2027 Summary of Benefits, page 1 (the file code has no plan number)
        (
            "2026\nSummary of Benefits\nTexas\nWellcare Patriot Simple (HMO)\nH5294 | 014 | 000\n"
            "H5294_2026_TX_SB_HMAO_4626794ENG_M",
            "H5294-014",
        ),
        # Wellcare Evidence of Coverage, page 1 file code
        (
            "Evidence of Coverage for 2026:\nWellcare Patriot Simple (HMO)\n"
            "H5294_014_2026_TX_EOC_HMAO_4608938ENG_C",
            "H5294-014",
        ),
        # Wellcare SB page header
        (
            "Summary of Benefits 2026\nWellcare Patriot Simple (HMO)\nH5294, Plan 014, 000",
            "H5294-014",
        ),  # fmt: skip
        # Humana Summary of Benefits, page 1
        ("2026\nSummary of Benefits\nHumana Gold Plus H0028-030 (HMO)\nSan Antonio", "H0028-030"),
    ],
)
def test_classifier_reads_each_real_id_form(first_page: str, plan_id: str) -> None:
    result = classify_pages([first_page], document_id="d")
    assert result.status is ClassifyStatus.SURE, result.review_item
    assert result.plan_id.value == plan_id


def test_file_code_year_is_not_a_plan_number() -> None:
    # "H5294_2026_TX" must never read as plan 202 (an earlier look at this file did exactly that).
    assert plans_named("H5294_2026_TX_SB_HMAO_4626794ENG_M") == set()


def _booklet() -> list[str]:
    return [
        # the cover names both plans, so it is nobody's page
        "Example Health Plan 2026 Summary of Benefits\nH9999-001 and H9999-002",
        "Benefits\nH9999, Plan 001, 000\nMonthly Plan Premium $0",
        "Doctor Visits\nSpecialists $10 copay",  # no header: still plan 001
        "Benefits\nH9999, Plan 002, 000\nMonthly Plan Premium $45",
        "Specialists $50 copay",
    ]


def test_booklet_pages_for_each_plan() -> None:
    assert plan_pages(_booklet(), "H9999-001").pages == PageRange(2, 3)
    second = plan_pages(_booklet(), "H9999-002")
    assert second.pages == PageRange(4, 5) and second.problem is None
    assert second.others == ("H9999-001",)
    masked = mask_pages(_booklet(), PageRange(4, 5))
    assert masked[:3] == ["", "", ""] and "$45" in masked[3]  # page numbers stay real


def test_booklet_by_plan_name() -> None:
    pages = ["H9999-002 Silver plan\nPremium $45", "Gold Plan HMO\nPremium $0"]
    assert plan_pages(pages, "H9999-001", plan_name="Gold Plan HMO").pages == PageRange(2, 2)


def test_single_plan_document_is_not_a_booklet() -> None:
    pages = ["Wellcare Patriot Simple (HMO)\nH5294 | 014 | 000", "Specialists $10 copay"]
    assert plan_pages(pages, "H5294-014").pages is None


def test_broken_booklet_range_goes_to_review() -> None:
    pages = [*_booklet(), "H9999, Plan 001, 000\nUrgent care $40"]
    result = plan_pages(pages, "H9999-001")
    assert result.pages is None and result.problem and "not one range" in result.problem


def test_run_extracts_only_the_requested_plans_pages() -> None:
    texts = _booklet()
    result = classify_pages(texts[:3], document_id="booklet")
    assert result.status is ClassifyStatus.UNSURE  # two plan ids on the cover
    targets, problems = _targets(result, texts, ["H9999-002"])
    assert problems == []
    [(narrowed, booklet)] = targets
    assert narrowed.status is ClassifyStatus.SURE
    assert narrowed.plan_id.value == "H9999-002" and narrowed.plan_id.page == 4
    assert booklet.pages == PageRange(4, 5)


def test_booklet_with_no_page_of_its_own_goes_to_review() -> None:
    texts = ["Example Health Plan 2026 Summary of Benefits\nH9999-001 and H9999-002", "Premium $0"]
    result = classify_pages(texts, document_id="booklet")
    targets, problems = _targets(result, texts, ["H9999-001"])
    assert targets == [] and problems and "no page belongs to H9999-001" in problems[0]
