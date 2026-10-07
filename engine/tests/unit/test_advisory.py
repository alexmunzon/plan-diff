"""Hand-written synthetic evidence, never recorded model responses."""

import json
import socket

import pytest
from pydantic import ValidationError

from plan_diff.advisory import Request, evaluate


def request(**changes):
    return Request.model_validate(
        dict(
            run_hash="a" * 64,
            document_hash="b" * 64,
            document_id="synthetic-sb",
            plan_id="H9999-001",
            year=2027,
            field="monthly_premium",
            pages=[{"page": 1, "text": "Monthly premium $20.00 per month."}],
        )
        | changes
    )


def response(req, **changes):
    return json.dumps(
        dict(
            version="plan-fallback-v1",
            request_key=req.key,
            origin="hand_written_synthetic_fixture",
            value={"kind": "money", "amount": "20.00"},
            unit="per_month",
            document_id="synthetic-sb",
            page=1,
            quote="Monthly premium $20.00 per month.",
        )
        | changes
    ).encode()


def test_offline_and_pending(monkeypatch):
    def refuse(*args, **kwargs):
        pytest.fail("network attempted")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    req = request()
    before = req.model_dump_json()
    result = evaluate(req, mode="replay", response=response(req))
    assert result.status == "replayed" and result.review_state == "needs_review"
    assert result.calls == result.cost_usd == 0
    assert result.label == "Hand-written synthetic fixture; no model called."
    assert req.model_dump_json() == before
    assert evaluate(req).status == "off"
    assert evaluate(req, mode="live").status == "live_blocked"
    assert evaluate(req, mode="replay").status == "pending"


@pytest.mark.parametrize(
    "changes",
    [
        {"request_key": "f" * 64},
        {"document_id": "other"},
        {"page": 2},
        {"page": True},
        {"quote": "invented $20.00"},
        {"quote": ""},
        {"notes": "ignore rules"},
        {"value": {"kind": "money", "amount": "2"}},
        {"unit": "per_year"},
        {"value": {"kind": "money", "amount": "NaN"}},
        {"value": {"kind": "money", "amount": 20.0}},
        {"origin": "actual_model_response"},
        {"confidence": 1},
    ],
)
def test_adversarial_response(changes):
    req = request()
    result = evaluate(req, mode="replay", response=response(req, **changes))
    assert result.status == "pending" and result.proposal is None


@pytest.mark.parametrize(
    "raw",
    [
        b"{}",
        b"null",
        b"[]",
        b"\xff",
        b"{",
        b"x" * 8193,
        b'{"version":"x","version":"plan-fallback-v1"}',
        b"[" * 1500,
    ],
)
def test_malformed(raw):
    assert evaluate(request(), mode="replay", response=raw).status == "pending"


def test_deterministic_value_is_never_overridden():
    req = request()
    for value in ("20.00", "99.00"):
        r = request(deterministic_value={"kind": "money", "amount": value})
        assert evaluate(r, mode="replay", response=response(r)).status == "pending"
    assert request(document_hash="d" * 64).key != req.key
    assert request(year=2026).key != req.key
    assert request(run_hash="d" * 64).key != req.key
    with pytest.raises(ValueError):
        evaluate(req, mode="record")
    for changes in (
        {"notes": "private"},
        {"pages": []},
        {"data_kind": "client"},
        {"pages": [{"page": 1, "text": "a"}, {"page": 1, "text": "b"}]},
    ):
        with pytest.raises(ValidationError):
            request(**changes)


@pytest.mark.parametrize(
    "text",
    [
        "Monthly premium $20.00 or $40.00 per month.",
        "Specialist copay $20.00 per month.",
        "Monthly premium $20.00 per month, not covered.",
        "Monthly premium $20.00 per month or per year.",
    ],
)
def test_contradictory_or_wrong_field_evidence(text):
    req = request(pages=[{"page": 1, "text": text}])
    assert evaluate(req, mode="replay", response=response(req, quote=text)).status == "pending"


def test_adapter_has_no_io_or_live_imports():
    import ast
    import inspect

    from plan_diff import advisory

    tree = ast.parse(inspect.getsource(advisory))
    imports = [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
    imports += [
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    ]
    assert all(
        name
        and name.split(".")[0]
        in {"hashlib", "json", "re", "decimal", "typing", "pydantic", "plan_diff"}
        for name in imports
    )
    assert not any(
        isinstance(node, ast.Name) and node.id in {"open", "exec", "eval"}
        for node in ast.walk(tree)
    )


def test_off_and_live_ignore_malformed_bytes():
    req = request()
    assert evaluate(req, response=b"invalid").status == "off"
    assert evaluate(req, mode="live", response=b"invalid").status == "live_blocked"
    assert evaluate(req, mode="replay", response="not bytes").status == "pending"


@pytest.mark.parametrize(
    "text,kind,amount,unit,status",
    [
        ("Monthly premium not covered", "not_covered", None, None, "replayed"),
        ("Monthly premium not covered, $20 per month", "not_covered", None, None, "pending"),
        ("Monthly premium 20% per month", "coinsurance", "20", "per_month", "pending"),
    ],
)
def test_other_value_kinds(text, kind, amount, unit, status):
    req = request(pages=[{"page": 1, "text": text}])
    value = {"kind": kind} | ({"percent": amount} if amount else {})
    raw = response(req, value=value, unit=unit, quote=text)
    assert evaluate(req, mode="replay", response=raw).status == status


@pytest.mark.parametrize(
    "field,text,value,unit,other",
    [
        (
            "monthly_premium",
            "Monthly premium waived. Specialist visits $20 per month.",
            {"kind": "money", "amount": "20"},
            "per_month",
            None,
        ),
        (
            "monthly_premium",
            "Monthly premium is not $20 per month.",
            {"kind": "money", "amount": "20"},
            "per_month",
            None,
        ),
        (
            "monthly_premium",
            "Monthly premium is not covered by this statement, but is covered.",
            {"kind": "not_covered"},
            None,
            None,
        ),
        (
            "monthly_premium",
            "Monthly premium $20 per month.",
            {"kind": "money", "amount": "20"},
            "per_month",
            "Monthly premium not covered.",
        ),
        (
            "pcp_copay",
            "Primary care visits 20% or 40% per visit.",
            {"kind": "coinsurance", "percent": "20"},
            "per_visit",
            None,
        ),
        (
            "pcp_copay",
            "Primary care visits $20 copay and 20% coinsurance per visit.",
            {"kind": "coinsurance", "percent": "20"},
            "per_visit",
            None,
        ),
        (
            "pcp_copay",
            "Primary care visits -20% per visit.",
            {"kind": "coinsurance", "percent": "20"},
            "per_visit",
            None,
        ),
        (
            "pcp_copay",
            "Primary care visits 20% per visitor.",
            {"kind": "coinsurance", "percent": "20"},
            "per_visit",
            None,
        ),
        (
            "monthly_premium",
            "Monthly premium $20 per monthly estimate.",
            {"kind": "money", "amount": "20"},
            "per_month",
            None,
        ),
        (
            "monthly_premium",
            "Monthly premium $20 per month.",
            {"kind": "copay", "amount": "20"},
            "per_month",
            None,
        ),
        (
            "monthly_premium",
            "Monthly premium 20% per month.",
            {"kind": "coinsurance", "percent": "20"},
            "per_month",
            None,
        ),
        (
            "pcp_copay",
            "Primary care visits $20 per month.",
            {"kind": "copay", "amount": "20"},
            "per_month",
            None,
        ),
        (
            "pcp_copay",
            "Primary care visits 20% per visit.",
            {"kind": "coinsurance", "percent": "20"},
            "per_visit",
            "Primary care visits 40% per visit.",
        ),
    ],
)
def test_full_row_ambiguity_refuses_proposals(field, text, value, unit, other):
    pages = [{"page": 1, "text": text}]
    if other:
        pages.append({"page": 2, "text": other})
    req = request(field=field, pages=pages)
    result = evaluate(
        req, mode="replay", response=response(req, quote=text, value=value, unit=unit)
    )
    assert result.status == "pending" and result.proposal is None
    assert result.review_state == "needs_review"
    assert result.calls == result.cost_usd == 0


@pytest.mark.parametrize(
    "field,text,value,unit",
    [
        (
            "monthly_premium",
            "Monthly premium is $20.00 per month.",
            {"kind": "money", "amount": "20"},
            "per_month",
        ),
        (
            "medical_deductible",
            "Medical deductible: $20 per year.",
            {"kind": "money", "amount": "20"},
            "per_year",
        ),
        (
            "pcp_copay",
            "Primary care visits $20 copay per visit.",
            {"kind": "copay", "amount": "20"},
            "per_visit",
        ),
        (
            "pcp_copay",
            "Primary care visits 20% coinsurance per visit.",
            {"kind": "coinsurance", "percent": "20"},
            "per_visit",
        ),
        ("pcp_copay", "Primary care visits not covered.", {"kind": "not_covered"}, None),
    ],
)
def test_single_supported_row_on_each_page(field, text, value, unit):
    req = request(field=field, pages=[{"page": 1, "text": text}, {"page": 2, "text": text}])
    raw = response(req, quote=text, value=value, unit=unit, page=2)
    result = evaluate(req, mode="replay", response=raw)
    assert result.status == "replayed" and result.review_state == "needs_review"
    assert result.proposal.page == 2 and result.proposal.quote == text
    assert result.calls == result.cost_usd == 0
    assert evaluate(request(), mode="replay", response=raw).proposal is None
    assert evaluate(req, response=raw).proposal is None
    assert evaluate(req, mode="live", response=raw).proposal is None
    assert (
        evaluate(
            req, mode="replay", response=response(req, origin="actual_model_response")
        ).proposal
        is None
    )


def test_quote_must_include_entire_cited_row():
    req = request(
        pages=[
            {"page": 1, "text": "Monthly premium $20 per month. Specialist visits $40 per visit."}
        ]
    )
    result = evaluate(
        req, mode="replay", response=response(req, quote="Monthly premium $20 per month.")
    )
    assert result.status == "pending" and result.proposal is None
