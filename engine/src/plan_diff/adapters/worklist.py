"""A synthetic, evidence-bound client worklist. It makes no suitability recommendations."""

import re
from collections import Counter
from pathlib import Path
from typing import Literal

from plan_diff.adapters.contract import (
    Artifact,
    Client,
    ContractModel,
    Coverage,
    CoverageFile,
    Issue,
    Packet,
    Policy,
    Sha,
    Text,
    canonical_json,
    pin,
    read_pinned,
    stable_id,
    verify,
)
from plan_diff.models.diff import PlanDiff
from plan_diff.models.fields import FieldName
from plan_diff.models.ids import PLAN_ID_REGEX
from plan_diff.models.plan import PlanRecord
from plan_diff.models.review import ReviewItem
from plan_diff.models.run import RunManifest


class WorkItem(ContractModel):
    item_id: Text
    client_id: Text
    client_record_id: Text | None
    policy_id: Text | None
    coverage: Coverage | None
    identity_state: str
    state: Literal["ready_for_review", "needs_review", "unsupported"]
    review_state: Literal["needs_review"] = "needs_review"
    reasons: tuple[str, ...]
    plan_diff: PlanDiff | None
    plan_artifact: Text | None


class Worklist(ContractModel):
    schema_version: Literal["1.0.0"] = "1.0.0"
    agency_id: Text
    run_id: Text
    intake_run_id: Text
    bob_run_id: Text
    plan_run_id: Text
    data_kind: Literal["synthetic"] = "synthetic"
    packet_sha256: Sha
    coverage_artifact: Artifact
    plan_artifacts: tuple[Artifact, ...]
    items: tuple[WorkItem, ...]
    issues: tuple[Issue, ...]
    purpose: Literal["synthetic review worklist; no suitability recommendation"] = (
        "synthetic review worklist; no suitability recommendation"
    )


def pin_plan_run(root: Path) -> tuple[Artifact, ...]:
    """Pin once, retain pins, and pass them back on each rerun to detect stale artifacts."""
    paths = ["manifest.json", "review_queue.jsonl"]
    paths += [
        p.relative_to(root).as_posix()
        for folder in ("plans", "diff")
        for p in sorted((root / folder).glob("*.json"))
    ]
    return tuple(pin(root, path) for path in sorted(paths))


def build_worklist(
    packet: Packet,
    intake_root: Path,
    *,
    coverage_root: Path,
    coverage_artifact: Artifact,
    plan_root: Path,
    plan_artifacts: tuple[Artifact, ...],
    run_id: str,
) -> Worklist:
    """Use explicit coverage only; do not infer year from effective date or county from ZIP."""
    import hashlib

    packet = Packet.model_validate_json(packet.model_dump_json())
    verify(intake_root, packet)
    coverage = CoverageFile.model_validate_json(read_pinned(coverage_root, coverage_artifact))
    evidence = {a.path: a for a in coverage.artifacts}
    if len(evidence) != len(coverage.artifacts):
        raise ValueError("duplicate coverage evidence path")
    for artifact in coverage.artifacts:
        read_pinned(coverage_root, artifact)
    for row in coverage.rows:
        if row.provenance.artifact not in evidence:
            raise ValueError("coverage evidence is not pinned")
    blobs = {a.path: read_pinned(plan_root, a) for a in plan_artifacts}
    if len(blobs) != len(plan_artifacts):
        raise ValueError("duplicate plan artifact path")
    actual = {a.path for a in pin_plan_run(plan_root)}
    if actual != set(blobs):
        raise ValueError("plan snapshot file inventory changed")
    manifest = RunManifest.model_validate_json(blobs["manifest.json"])
    if manifest.data_kind != "synthetic":
        raise ValueError("integration worklist requires a synthetic plan run")
    plans = [
        PlanRecord.model_validate_json(b)
        for path, b in sorted(blobs.items())
        if path.startswith("plans/")
    ]
    diffs = [
        (path, PlanDiff.model_validate_json(b))
        for path, b in sorted(blobs.items())
        if path.startswith("diff/")
    ]
    reviews = [
        ReviewItem.model_validate_json(line)
        for line in blobs["review_queue.jsonl"].splitlines()
        if line.strip()
    ]
    client_counts = Counter(c.client_id for c in packet.clients)
    policy_counts = Counter(p.policy_id for p in packet.policies)
    coverage_counts = Counter(
        (c.agency_id, c.client_id, c.policy_id, c.plan_year) for c in coverage.rows
    )
    items: list[WorkItem] = []
    used: set[int] = set()

    def item(
        client: Client | None,
        policy: Policy | None,
        cov: Coverage | None,
        extra: tuple[str, ...],
        index: int,
    ) -> None:
        reasons = list(extra)
        identity_state = "unresolved"
        chosen: PlanDiff | None = None
        chosen_path: str | None = None
        cid = (
            client.client_id
            if client
            else policy.client_id
            if policy
            else cov.client_id
            if cov
            else "unknown"
        )
        if client:
            identities = [i for i in packet.identities if client.record_id in i.record_ids]
            if len(identities) == 1:
                identity_state = identities[0].state
                if identity_state == "resolved" and identities[0].review_state in {
                    "needs_review",
                    "blocked",
                    "rejected",
                }:
                    reasons.append("IDENTITY_REVIEW_PENDING")
            if identity_state != "resolved":
                reasons.append("IDENTITY_NOT_RESOLVED")
            if client_counts[cid] != 1:
                reasons.append("DUPLICATE_CLIENT_ID")
        if not policy:
            reasons.append("MISSING_POLICY")
        elif policy_counts[policy.policy_id] != 1:
            reasons.append("AMBIGUOUS_POLICY")
        unsupported = bool(policy and policy.line_of_business != "MA")
        if policy and policy.status != "ACTIVE":
            reasons.append("POLICY_NOT_ACTIVE")
        if cov is None:
            reasons.append("MISSING_COVERAGE")
        else:
            if cov.agency_id != packet.agency_id:
                reasons.append("WRONG_AGENCY")
            if coverage_counts[(cov.agency_id, cov.client_id, cov.policy_id, cov.plan_year)] != 1:
                reasons.append("AMBIGUOUS_COVERAGE")
            if cov.plan_id is None or cov.plan_year is None or cov.county is None:
                reasons.append("INCOMPLETE_COVERAGE")
            if cov.plan_id and not re.fullmatch(PLAN_ID_REGEX, cov.plan_id):
                unsupported = True
            if (
                policy
                and cov.plan_year is not None
                and (
                    cov.plan_year < policy.effective_date.year
                    or (
                        policy.termination_date is not None
                        and cov.plan_year > policy.termination_date.year
                    )
                )
            ):
                reasons.append("COVERAGE_OUTSIDE_POLICY_DATES")
            if policy and cov.plan_id != policy.plan_id:
                reasons.append("POLICY_PLAN_CONFLICT")
            matches = [
                (path, d)
                for path, d in diffs
                if d.old_plan_id == cov.plan_id and d.old_year == cov.plan_year
            ]
            if len(matches) != 1:
                reasons.append("MISSING_PLAN_DIFF" if not matches else "AMBIGUOUS_PLAN_DIFF")
            else:
                chosen_path, chosen = matches[0]
                old = [p for p in plans if p.plan_id == cov.plan_id and p.year == cov.plan_year]
                if len(old) != 1:
                    reasons.append("MISSING_OR_AMBIGUOUS_PLAN")
                else:
                    if cov.county not in old[0].counties:
                        reasons.append("COUNTY_NOT_COVERED")
                    if set(old[0].fields) != set(FieldName):
                        reasons.append("INCOMPLETE_PLAN_BENEFITS")
                    if any(
                        c.old is not None
                        and c.field in old[0].fields
                        and c.old != old[0].fields[c.field]
                        for c in chosen.changes
                    ):
                        reasons.append("PLAN_BENEFIT_EVIDENCE_CONFLICT")
                if chosen.new_plan_id is not None:
                    new = [
                        p
                        for p in plans
                        if p.plan_id == chosen.new_plan_id and p.year == chosen.new_year
                    ]
                    if len(new) != 1:
                        reasons.append("MISSING_OR_AMBIGUOUS_NEXT_PLAN")
                    else:
                        if cov.county not in new[0].counties:
                            reasons.append("NEXT_YEAR_COUNTY_NOT_COVERED")
                        if set(new[0].fields) != set(FieldName):
                            reasons.append("INCOMPLETE_NEXT_PLAN_BENEFITS")
                        if any(
                            c.new is not None
                            and c.field in new[0].fields
                            and c.new != new[0].fields[c.field]
                            for c in chosen.changes
                        ):
                            reasons.append("PLAN_BENEFIT_EVIDENCE_CONFLICT")
                if chosen.shop_again is None or chosen.review:
                    reasons.append("PLAN_REVIEW_PENDING")
                if not chosen.evidence:
                    reasons.append("MISSING_CROSSWALK_CITATION")
                if len({c.field for c in chosen.changes}) != len(chosen.changes):
                    reasons.append("AMBIGUOUS_BENEFIT_COMPARISON")
                if chosen.crosswalk_status != "terminated":
                    if {c.field for c in chosen.changes} != set(FieldName) or any(
                        c.old is None or c.new is None or c.direction == "not_comparable"
                        for c in chosen.changes
                    ):
                        reasons.append("INCOMPLETE_BENEFIT_COMPARISON")
                if any(
                    r.plan_id is None or r.plan_id in {chosen.old_plan_id, chosen.new_plan_id}
                    for r in reviews
                ):
                    reasons.append("PLAN_SOURCE_REVIEW_PENDING")
        if unsupported:
            reasons.append("UNSUPPORTED_LINE_OF_BUSINESS_OR_PLAN")
        items.append(
            WorkItem(
                item_id=stable_id(
                    packet.agency_id,
                    packet.run_id,
                    client.record_id if client else cid,
                    policy.record_id if policy else "",
                    str(index),
                ),
                client_id=cid,
                client_record_id=client.record_id if client else None,
                policy_id=policy.policy_id if policy else cov.policy_id if cov else None,
                coverage=cov,
                identity_state=identity_state,
                state="unsupported"
                if unsupported
                else "needs_review"
                if reasons
                else "ready_for_review",
                reasons=tuple(sorted(set(reasons))),
                plan_diff=chosen,
                plan_artifact=chosen_path,
            )
        )

    for client in packet.clients:
        policies = [p for p in packet.policies if p.client_id == client.client_id]
        if not policies:
            item(client, None, None, (), -1)
        for policy in policies:
            claims = [
                (i, c)
                for i, c in enumerate(coverage.rows)
                if c.agency_id == packet.agency_id
                and c.client_id == client.client_id
                and c.policy_id == policy.policy_id
            ]
            if not claims:
                item(client, policy, None, (), -1)
            for index, cov in claims:
                used.add(index)
                item(client, policy, cov, (), index)
    for policy in packet.policies:
        if policy.client_id not in client_counts:
            claims = [
                (i, c)
                for i, c in enumerate(coverage.rows)
                if c.agency_id == packet.agency_id
                and c.client_id == policy.client_id
                and c.policy_id == policy.policy_id
            ]
            if not claims:
                item(None, policy, None, ("ORPHAN_POLICY",), -1)
            for index, cov in claims:
                used.add(index)
                item(None, policy, cov, ("ORPHAN_POLICY",), index)
    for index, cov in enumerate(coverage.rows):
        if index not in used:
            item(None, None, cov, ("ORPHAN_COVERAGE",), index)
    return Worklist(
        agency_id=packet.agency_id,
        run_id=run_id,
        intake_run_id=packet.intake_run_id,
        bob_run_id=packet.run_id,
        plan_run_id=manifest.run_id,
        packet_sha256=hashlib.sha256(canonical_json(packet).encode()).hexdigest(),
        coverage_artifact=coverage_artifact,
        plan_artifacts=plan_artifacts,
        items=tuple(sorted(items, key=lambda i: i.item_id)),
        issues=packet.issues + (() if packet.clients else (Issue(code="NO_CLEAN_CLIENTS"),)),
    )
