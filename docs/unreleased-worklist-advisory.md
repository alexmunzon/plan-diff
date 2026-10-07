# Unreleased offline review candidate

`/worklist` displays the existing integration worklist, including unresolved identities,
missing coverage/year/county, unsupported plans and orphan outcomes. State/reason filters
never remove records from the inventory totals. Expand a row to read source/page evidence.
Every row requires broker review; no suitability recommendation or approval action exists.

Import accepts only synthetic worklist JSON, bounded to 2 MB and 1,000 items. Parsing uses
a checked-in snapshot of the engine Worklist JSON Schema plus explicit version/data-kind,
unique-item and review-state gates. Invalid imports retain the previous valid view. Files
remain in browser memory and are not uploaded, stored or automatically passed between apps.
Hashes describe upstream evidence; the browser cannot independently verify absent source bytes.
The integration CLI remains the authority for constructing and pinning upstream artifacts.

Offline advisory wiring:

    uv run --project engine plan-diff advisory evaluate REQUEST.json SOURCE.pdf MANIFEST.json PLAN.json
    uv run --project engine plan-diff advisory evaluate REQUEST.json SOURCE.pdf MANIFEST.json PLAN.json --mode replay --response HANDWRITTEN.json

Output is a JSON sidecar on stdout. Default mode is off. The request binds exact manifest and
PDF bytes, plan/year/document identity and quoted page text. The supplied canonical plan record
controls the deterministic value, so an existing value blocks fallback even if the request
claims it is missing. County FIPS is refused because the command cannot verify that binding.
Only explicit synthetic inputs and handwritten synthetic response fixtures are supported.
No credentials, paid calls, live mode, output mutation or automatic approvals are available.
Malformed, absent, stale or ungrounded response fixtures remain pending review. No fixture is
represented as an actual model result. Local metadata checks do not authenticate the author
of an imported manifest or plan. Callers must use trusted generated synthetic artifacts.
