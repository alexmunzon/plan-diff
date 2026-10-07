"""Missing evidence stays visible; client worklists never assert suitability."""

import shutil
from datetime import date
from pathlib import Path

import pytest

from plan_diff.adapters.contract import (
    Client,
    Coverage,
    CoverageFile,
    Identity,
    Packet,
    Policy,
    Provenance,
    canonical_json,
    pin,
)
from plan_diff.adapters.worklist import Worklist, build_worklist, pin_plan_run
from plan_diff.models.run import RunManifest

DEMO = Path(__file__).resolve().parents[3] / "dashboard/public/demo-run"


@pytest.fixture
def inputs(tmp_path: Path):
    (tmp_path / "clean.csv").write_text("synthetic clean data\n")
    (tmp_path / "enrollment.csv").write_text("explicit synthetic enrollment\n")
    lin = Provenance(
        source_file="crm.csv",
        sheet=None,
        row_number=2,
        raw_hash="a" * 64,
        run_id="intake-1",
        mapping_version="v1",
        artifact="clean.csv",
        artifact_row=1,
    )
    client = Client(
        record_id="r1",
        client_id="c1",
        first_name="Example",
        last_name="Person",
        dob=date(1950, 1, 1),
        mbi=None,
        phone=None,
        email=None,
        address_line1=None,
        city=None,
        state="TX",
        zip=None,
        household_id=None,
        provenance=lin,
    )
    policy = Policy(
        record_id="p1",
        policy_id="p1",
        client_id="c1",
        plan_id="H9999-001",
        line_of_business="MA",
        status="ACTIVE",
        effective_date=date(2020, 1, 1),
        termination_date=None,
        provenance=lin,
    )
    packet = Packet(
        agency_id="a",
        run_id="bob-1",
        intake_run_id="intake-1",
        data_kind="synthetic",
        artifacts=(pin(tmp_path, "clean.csv"),),
        clients=(client,),
        policies=(policy,),
        identities=(
            Identity(
                person_id="person1",
                record_ids=("r1",),
                client_ids=("c1",),
                state="unresolved",
                review_state="needs_review",
            ),
        ),
    )
    cov = Coverage(
        agency_id="a",
        client_id="c1",
        policy_id="p1",
        plan_id="H9999-001",
        plan_year=2026,
        county="Bexar",
        provenance=lin.model_copy(update={"artifact": "enrollment.csv"}),
    )
    plan = tmp_path / "plan"
    shutil.copytree(DEMO, plan)
    return packet, cov, plan


def run_worklist(tmp_path, inputs, rows=None, packet=None, pins=None, run_id="worklist-1"):
    p, cov, plan = inputs
    coverage = CoverageFile(
        data_kind="synthetic",
        artifacts=(pin(tmp_path, "enrollment.csv"),),
        rows=(cov,) if rows is None else rows,
    )
    (tmp_path / "coverage.json").write_text(canonical_json(coverage))
    return build_worklist(
        packet or p,
        tmp_path,
        coverage_root=tmp_path,
        coverage_artifact=pin(tmp_path, "coverage.json"),
        plan_root=plan,
        plan_artifacts=pins or pin_plan_run(plan),
        run_id=run_id,
    )


def test_native_diff_and_citations_are_preserved(tmp_path, inputs):
    result = run_worklist(tmp_path, inputs)
    item = result.items[0]
    assert item.plan_diff.old_plan_id == "H9999-001"
    assert item.plan_diff.reasons == ("premium up $25 a month",)
    assert item.plan_diff.changes[0].old.citation.document_id
    assert item.review_state == "needs_review"
    assert result.purpose.endswith("no suitability recommendation")
    assert canonical_json(result) == canonical_json(run_worklist(tmp_path, inputs))


def test_missing_coverage_does_not_use_policy_effective_year(tmp_path, inputs):
    result = run_worklist(tmp_path, inputs, rows=())
    assert len(result.items) == 1
    assert "MISSING_COVERAGE" in result.items[0].reasons
    assert result.items[0].coverage is None and result.items[0].plan_diff is None


@pytest.mark.parametrize(
    "update,reason",
    [
        ({"county": None}, "INCOMPLETE_COVERAGE"),
        ({"plan_year": None}, "INCOMPLETE_COVERAGE"),
        ({"county": "Uncovered"}, "COUNTY_NOT_COVERED"),
        ({"plan_year": 2025}, "MISSING_PLAN_DIFF"),
        ({"agency_id": "other"}, "WRONG_AGENCY"),
        ({"client_id": "unknown"}, "ORPHAN_COVERAGE"),
        ({"plan_id": "ACA-EXAMPLE"}, "UNSUPPORTED_LINE_OF_BUSINESS_OR_PLAN"),
    ],
)
def test_unsupported_or_missing_evidence(tmp_path, inputs, update, reason):
    cov = inputs[1].model_copy(update=update)
    result = run_worklist(tmp_path, inputs, rows=(cov,))
    assert any(reason in item.reasons for item in result.items)
    assert all(item.state != "ready_for_review" for item in result.items)


def test_duplicate_coverage_keeps_both_claims(tmp_path, inputs):
    result = run_worklist(tmp_path, inputs, rows=(inputs[1], inputs[1]))
    assert len(result.items) == 2
    assert len({i.item_id for i in result.items}) == 2
    assert all("AMBIGUOUS_COVERAGE" in i.reasons for i in result.items)


def test_stale_plan_hash_and_new_file_are_refused(tmp_path, inputs):
    plan = inputs[2]
    pins = pin_plan_run(plan)
    path = plan / "diff/H9999-001.json"
    path.write_text(path.read_text() + "\n")
    with pytest.raises(ValueError, match="stale"):
        run_worklist(tmp_path, inputs, pins=pins)
    pins = pin_plan_run(plan)
    shutil.copy(path, plan / "diff/duplicate.json")
    with pytest.raises(ValueError, match="inventory"):
        run_worklist(tmp_path, inputs, pins=pins)


def test_ambiguous_diff_and_unresolved_identity(tmp_path, inputs):
    plan = inputs[2]
    shutil.copy(plan / "diff/H9999-001.json", plan / "diff/duplicate.json")
    p = inputs[0].model_copy(update={"identities": ()})
    item = run_worklist(tmp_path, inputs, packet=p).items[0]
    assert "AMBIGUOUS_PLAN_DIFF" in item.reasons
    assert "IDENTITY_NOT_RESOLVED" in item.reasons
    assert item.plan_diff is None


def test_actual_intake_to_bob_fixture_keeps_coverage_gaps() -> None:
    root = Path(__file__).resolve().parents[3] / "fixtures/integration-v1"
    packet = Packet.model_validate_json((root / "bob-packet.json").read_text())
    result = build_worklist(
        packet,
        root / "intake-run",
        coverage_root=root,
        coverage_artifact=pin(root, "coverage.json"),
        plan_root=root / "plan-run",
        plan_artifacts=pin_plan_run(root / "plan-run"),
        run_id="worklist-synthetic-v1",
    )
    assert {c.client_id for c in packet.clients} <= {i.client_id for i in result.items}
    linked = [i for i in result.items if i.plan_diff is not None]
    assert len(linked) == 1
    assert linked[0].client_id == "C-00002" and linked[0].policy_id == "P-00003"
    assert linked[0].coverage.plan_year == 2026  # policy effective date is 2023, not used
    assert "IDENTITY_NOT_RESOLVED" in linked[0].reasons
    assert any("MISSING_COVERAGE" in i.reasons for i in result.items)
    assert canonical_json(result) == (root / "worklist.json").read_text()


def test_stale_enrollment_evidence_is_refused(tmp_path, inputs):
    p, cov, plan = inputs
    coverage = CoverageFile(
        data_kind="synthetic", artifacts=(pin(tmp_path, "enrollment.csv"),), rows=(cov,)
    )
    (tmp_path / "coverage.json").write_text(canonical_json(coverage))
    expected = pin(tmp_path, "coverage.json")
    (tmp_path / "enrollment.csv").write_text("changed evidence\n")
    with pytest.raises(ValueError, match="stale"):
        build_worklist(
            p,
            tmp_path,
            coverage_root=tmp_path,
            coverage_artifact=expected,
            plan_root=plan,
            plan_artifacts=pin_plan_run(plan),
            run_id="w",
        )


def test_incomplete_benefits_and_missing_citations_stay_in_review(tmp_path, inputs):
    import json

    path = inputs[2] / "diff/H9999-001.json"
    data = json.loads(path.read_text())
    data["changes"] = data["changes"][:1]
    data["evidence"] = []
    path.write_text(json.dumps(data))
    item = run_worklist(tmp_path, inputs).items[0]
    assert "INCOMPLETE_BENEFIT_COMPARISON" in item.reasons
    assert "MISSING_CROSSWALK_CITATION" in item.reasons
    assert item.state == "needs_review"


def test_orphan_policy_keeps_its_explicit_coverage(tmp_path, inputs):
    packet = inputs[0].model_copy(update={"clients": (), "identities": ()})
    result = run_worklist(tmp_path, inputs, packet=packet)
    assert len(result.items) == 1
    item = result.items[0]
    assert item.coverage == inputs[1]
    assert item.policy_id == "p1" and item.client_record_id is None
    assert "ORPHAN_POLICY" in item.reasons
    assert "MISSING_COVERAGE" not in item.reasons
    assert "MISSING_POLICY" not in item.reasons
    assert item.state == "needs_review"


@pytest.mark.parametrize("year,prefix", [(2026, "PLAN"), (2027, "NEXT_PLAN")])
def test_incomplete_native_plan_benefits_stay_visible(tmp_path, inputs, year, prefix):
    import json

    path = inputs[2] / f"plans/H9999-001_{year}.json"
    data = json.loads(path.read_text())
    del data["fields"]["monthly_premium"]
    path.write_text(json.dumps(data))
    item = run_worklist(tmp_path, inputs).items[0]
    assert f"INCOMPLETE_{prefix}_BENEFITS" in item.reasons
    assert item.plan_diff is not None
    assert item.state == "needs_review"


@pytest.mark.parametrize("year", [2026, 2027])
def test_native_plan_and_diff_evidence_conflict_needs_review(tmp_path, inputs, year):
    import json

    path = inputs[2] / f"plans/H9999-001_{year}.json"
    data = json.loads(path.read_text())
    data["fields"]["monthly_premium"]["value"]["amount"] = "999.00"
    path.write_text(json.dumps(data))
    item = run_worklist(tmp_path, inputs).items[0]
    assert "PLAN_BENEFIT_EVIDENCE_CONFLICT" in item.reasons
    assert item.plan_diff is not None
    assert item.state == "needs_review"


def test_empty_producer_run_id_is_refused(tmp_path, inputs):
    with pytest.raises(ValueError, match="run_id"):
        run_worklist(tmp_path, inputs, run_id="")


@pytest.mark.parametrize("field", ["agency_id", "intake_run_id", "bob_run_id", "plan_run_id"])
def test_empty_worklist_transport_ids_are_refused(tmp_path, inputs, field):
    data = run_worklist(tmp_path, inputs).model_dump()
    data[field] = ""
    with pytest.raises(ValueError, match=field):
        Worklist.model_validate(data)


def test_invalid_packet_fingerprint_is_refused(tmp_path, inputs):
    data = run_worklist(tmp_path, inputs).model_dump()
    data["packet_sha256"] = "invalid"
    with pytest.raises(ValueError, match="packet_sha256"):
        Worklist.model_validate(data)


@pytest.mark.parametrize("review_state", ["needs_review", "blocked", "rejected"])
def test_resolved_identity_with_pending_review_stays_in_review(tmp_path, inputs, review_state):
    packet = inputs[0]
    second = packet.clients[0].model_copy(update={"record_id": "r2", "client_id": "c2"})
    identity = Identity(
        person_id="person1",
        record_ids=("r1", "r2"),
        client_ids=("c1", "c2"),
        state="resolved",
        review_state=review_state,
    )
    packet = packet.model_copy(
        update={"clients": (*packet.clients, second), "identities": (identity,)}
    )
    (inputs[2] / "review_queue.jsonl").write_text("")
    item = next(
        i for i in run_worklist(tmp_path, inputs, packet=packet).items if i.client_record_id == "r1"
    )
    assert item.identity_state == "resolved"
    assert item.reasons == ("IDENTITY_REVIEW_PENDING",)
    assert item.state == "needs_review"
    assert item.review_state == "needs_review"


def test_public_plan_manifest_is_refused_with_fresh_pins(tmp_path, inputs):
    import json

    path = inputs[2] / "manifest.json"
    data = json.loads(path.read_text())
    data["data_kind"] = "public"
    path.write_text(json.dumps(data))
    assert RunManifest.model_validate_json(path.read_bytes()).data_kind == "public"
    with pytest.raises(ValueError, match="synthetic plan run"):
        run_worklist(tmp_path, inputs, pins=pin_plan_run(inputs[2]))
