"""Offline fallback proposals. Never writes to deterministic extraction results."""

import hashlib
import json
import re
from decimal import Decimal
from typing import Annotated, Literal, Self

from pydantic import Field, StrictInt, model_validator

from plan_diff import config
from plan_diff.models.fields import FieldName, FieldValue, Unit
from plan_diff.models.ids import PlanId, PlanYear, Sha256, StrictModel

Text = Annotated[str, Field(strict=True, min_length=1, max_length=200, pattern=r"\S")]


class Page(StrictModel):
    page: Annotated[StrictInt, Field(ge=1)]
    text: Text


class Request(StrictModel):
    version: Literal["plan-fallback-v1"] = "plan-fallback-v1"
    data_kind: Literal["synthetic", "public"] = "synthetic"
    run_hash: Sha256
    document_hash: Sha256
    document_id: Annotated[str, Field(strict=True, pattern=r"^[a-zA-Z0-9_-]{1,80}$")]
    plan_id: PlanId
    year: PlanYear
    county_fips: Annotated[str, Field(pattern=r"^[0-9]{5}$")] | None = None
    field: FieldName
    pages: Annotated[tuple[Page, ...], Field(min_length=1, max_length=3)]
    deterministic_value: FieldValue | None = None

    @model_validator(mode="after")
    def unique_pages(self) -> Self:
        if len({p.page for p in self.pages}) != len(self.pages):
            raise ValueError("duplicate pages")
        return self

    @property
    def key(self) -> str:
        payload = json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()


class Response(StrictModel):
    version: Literal["plan-fallback-v1"]
    request_key: Sha256
    origin: Literal["hand_written_synthetic_fixture"]
    value: FieldValue
    unit: Unit | None
    document_id: Text
    page: Annotated[StrictInt, Field(ge=1)]
    quote: Text


class Result(StrictModel):
    mode: Literal["off", "replay", "live"]
    status: Literal["off", "pending", "replayed", "live_blocked"]
    request_key: Sha256
    review_state: Literal["needs_review"] = "needs_review"
    proposal: Response | None = None
    reason: str
    label: str = "No model called."
    calls: Literal[0] = 0
    cost_usd: Literal[0] = 0


def _unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


# Narrow advisory-only compatibility; units are never inferred.
_MONEY_UNITS: dict[str, tuple[str, ...]] = {
    "monthly_premium": ("per_month",),
    "medical_deductible": ("per_year",),
    "moop_in_network": ("per_year",),
    "drug_deductible": ("per_year",),
    "dental_allowance": ("per_year",),
    "otc_allowance": ("per_month", "per_quarter", "per_half_year", "per_year"),
}
_COST_UNITS: dict[str, tuple[str, ...]] = {
    "pcp_copay": ("per_visit",),
    "specialist_copay": ("per_visit",),
    "emergency_room": ("per_visit",),
    "urgent_care": ("per_visit",),
    "inpatient_stay": ("per_day", "per_stay"),
    "outpatient_surgery": ("per_visit",),
    "drug_tier_1": ("per_prescription",),
    "drug_tier_2": ("per_prescription",),
    "drug_tier_3": ("per_prescription",),
}


def _row_agrees(field: FieldName, text: str, response: Response) -> bool:
    """Recognize one complete row, never assemble scattered tokens."""
    label = config.EXTRACT_LABELS[field]
    prefix = rf"(?:{label})\s*(?::\s*|is\s+)?"
    value = response.value
    if value.kind == "not_covered":
        return (
            response.unit is None
            and re.fullmatch(prefix + r"not covered\.?", text.strip(), re.IGNORECASE) is not None
        )
    allowed = _MONEY_UNITS.get(field) if value.kind == "money" else _COST_UNITS.get(field)
    if response.unit is None or not allowed or response.unit.value not in allowed:
        return False
    number = value.percent if value.kind == "coinsurance" else value.amount
    token = r"(?P<number>[0-9]+(?:\.[0-9]{1,2})?)"
    if value.kind == "coinsurance":
        expression = token + r"\s*%(?:\s+coinsurance)?"
    else:
        suffix = r"(?:\s+copay)?" if value.kind == "copay" else ""
        expression = r"\$\s*" + token + suffix
    unit = re.escape(response.unit.value.replace("_", " "))
    match = re.fullmatch(prefix + expression + rf"\s+{unit}\.?", text.strip(), re.IGNORECASE)
    return match is not None and Decimal(match["number"]) == number


def _grounded(request: Request, response: Response) -> bool:
    if response.document_id != request.document_id:
        return False
    if not any(p.page == response.page and response.quote == p.text for p in request.pages):
        return False
    # Each excerpt independently supports the same full expression.
    # Conservative lexical screening is not semantic proof or extraction.
    return all(_row_agrees(request.field, p.text, response) for p in request.pages)


def evaluate(request: Request, *, mode: str = "off", response: bytes | None = None) -> Result:
    """Caller supplies bounded public/synthetic excerpts and response bytes; no I/O.

    Even a grounded proposal stays pending. It is never converted to an ExtractedField.
    Existing deterministic values make the request ineligible for fallback.
    """
    if mode not in {"off", "replay", "live"}:
        raise ValueError("mode must be off, replay or live")
    request = Request.model_validate(request.model_dump())
    key = request.key
    if mode == "off":
        return Result(mode="off", status="off", request_key=key, reason="disabled")
    if mode == "live":
        return Result(
            mode="live",
            status="live_blocked",
            request_key=key,
            reason="requires approved provider/model, secure credentials and spending cap; "
            "live transport is not implemented",
        )
    if request.deterministic_value is not None:
        return Result(
            mode="replay", status="pending", request_key=key, reason="deterministic_value_preserved"
        )
    reason = "missing_response"
    if response is not None:
        try:
            if not isinstance(response, bytes) or len(response) > 8192:
                raise ValueError("invalid response size or type")
            parsed = Response.model_validate(json.loads(response, object_pairs_hook=_unique))
            if parsed.request_key != key or not _grounded(request, parsed):
                raise ValueError("stale or ungrounded response")
            return Result(
                mode="replay",
                status="replayed",
                request_key=key,
                proposal=parsed,
                reason="human_review_required",
                label="Hand-written synthetic fixture; no model called.",
            )
        except (ValueError, UnicodeError, RecursionError):
            reason = "invalid_or_ungrounded_response"
    return Result(mode="replay", status="pending", request_key=key, reason=reason)
