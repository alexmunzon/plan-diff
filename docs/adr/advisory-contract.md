# Advisory extraction fallback v1 (2026-10-07)

`plan_diff.advisory.Request`, `Response`, `Result` expose JSON schemas through
`model_json_schema()` and JSON artifacts through `model_dump(mode="json")`.

Integration hook: after deterministic extraction, call `evaluate` for one missing field.
Provide a run SHA-256, source document SHA-256, document ID, plan/year, optional county FIPS,
and at most three 200-character page excerpts from a verified public or synthetic document.
No clients, enrollment rows or personal notes enter this contract. The integrator must verify
source bytes/hash, page numbering, plan/year/county association and data classification before
building Request. User-provided hashes and labels alone do not establish provenance.

`evaluate(request, mode="replay", response=fixture_bytes)` returns a separate review artifact.
An existing deterministic_value blocks fallback, whether the proposed value agrees or disagrees.
Keep existing fields and review items intact. No automatic conversion into ExtractedField and
no changes to the deterministic parser, thresholds, canonical plans or diff decisions occur.

Proposals must bind to the exact request hash and cite a supplied document/page and exact quote.
Conservative lexical screening requires the quote to equal the entire selected excerpt and
its exact supplied page. Every supplied excerpt must independently match one complete requested
field row and agree on kind, value and unit. The narrow grammar allows the configured label,
an optional colon or "is", a dollar amount or percentage (up to two decimal places), an optional
matching "copay" or "coinsurance" marker, one explicit unit and an optional final period.
A complete "not covered" row has no unit. No value is borrowed from another benefit.

Premiums, deductibles, MOOP and allowances require money; visit, stay and drug tier cost-sharing
requires copay or coinsurance. Premiums require per month; deductibles/MOOP/dental allowance
require per year; OTC allows month/quarter/half year/year; office/emergency/urgent/surgery costs
require per visit; inpatient allows per day/per stay; drug tiers require per prescription.
These advisory-only rules do not modify deterministic parser/config behavior.

Negations, alternatives, mixed cost sharing, signed numbers, unit prefixes, extra prose,
conditions, unrelated rows, partial quotes, missing/default units and conflicting pages stay
pending with no proposal. Valid but unsupported layouts or wording also stay pending. These
checks are not semantic proof of benefit coverage or conditions; every valid replay still has
review_state=needs_review. Human review must establish meaning and resolve missing evidence
before accepting any value.

Off (default) ignores bytes. Replay accepts only explicitly hand-written synthetic fixtures,
never claims a fixture is a model response. Live returns live_blocked. All modes report zero
calls/cost; no network, credential, file or environment access exists in this adapter.
Session 7 owns CLI/navigation wiring and mapping Session 1's artifact IDs to these hash bindings.
This change does not register the adapter in the run pipeline.

Live validation is outstanding: Alex must approve exact provider/model and a specific USD cap,
authorize the session, and securely configure credentials without agents reading secret files.
A future transport needs enforced spending limits, timeout/retry tests and actual provider/model,
request IDs and usage provenance under a new recording contract. Evaluate source-grounding,
contradictions and failures on synthetic/public excerpts before considering live rollout.

Aligned with Session 1's agency-integration 1.0.0 contract: review_state is always
needs_review, never approved/resolved. Hash canonical_json(packet) bytes (including the
trailing newline) for run_hash so agency_id, run_id and intake_run_id remain bound locally.
Verify artifact byte pins before constructing requests; retain provenance outside the payload.
Use the verified source artifact SHA-256 for document_hash. county_fips accepts only an
explicit source FIPS; leave null for county labels and never infer FIPS from names or ZIP.
