# Security

plan-diff is a read-only demonstration using synthetic fixtures and public carrier/CMS data. It is
not approved for PHI, private client records, enrollment, or production decision-making. No release
has a security-support guarantee. Review the current main branch rather than assuming old snapshots
receive fixes.

## Reporting privately

Use the repository's GitHub **Security → Report a vulnerability** option if private reporting is
enabled: [private reporting](https://github.com/alexmunzon/plan-diff/security/advisories/new).
If it is unavailable, ask [the maintainer](https://github.com/alexmunzon) for a private reporting
channel without posting exploit details, credentials, or personal data in public issues. Include the
affected commit, minimal public/synthetic reproduction, expected behavior, and possible impact.
Never send real client data to demonstrate a problem.

## Trust boundaries

- **Published snapshot:** the dashboard reads code-selected committed run folders at build time.
  Their JSON is downloadable public data. There is no client-record workflow, live source refresh,
  or public upload/mutation endpoint in this demo. Do not place private data in `dashboard/public/`.
- **Run evidence:** TypeScript checks basic JSON shape, decimal-text amounts, and file counts.
  Python's canonical models provide stronger validation. Neither layer authenticates arbitrary
  third-party run files; provenance hashes do not establish that a source is safe or correct.
- **External sources:** carrier citations open the original HTTPS PDF, not a proxy hosted here.
  Fetching is an explicitly approved local action, disabled in CI. The fetcher checks pinned hashes,
  file markers and size, and refuses cross-host redirects. First-use pinning still needs human review.
- **Local parsing:** downloaded PDFs and CMS archives are untrusted inputs to parser libraries.
  Existing archive/run-path safeguards and tests reduce specific risks; this is not a malware
  sandbox or a complete hostile-file assessment. Keep raw files and generated runs git-ignored.
- **Models and uncertainty:** committed runs have Jev/LLM calls off; CI uses replay mode. Live/record
  calls require approval. Missing values, disputed text, and non-comparable periods remain review
  items. Shop-again is a broker review flag, not coverage or suitability advice.
- **Build and deployment:** lockfiles and full-SHA CI action pins improve reproducibility. CI has
  read-only repository permissions, no persisted checkout credentials, a timeout, and cancellation
  of superseded PR runs. These do not establish hosted access controls or deployment security.

## Dependency review and known residual risk

The bounded 2026-10-06 review of `dashboard/package-lock.json` found **0 production npm findings**
with `npm audit --package-lock-only --ignore-scripts --omit=dev`. The full audit still reports the
high-severity development-tool advisory [GHSA-vfj7-8cjw-p6xm](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm)
(`braces`, CVE-2026-93687): deeply nested brace patterns can exhaust the stack. The reviewed advisory
lists no patched version. Multiple affected parent nodes are not separate underlying advisories.
No forced update or override is applied. Avoid untrusted glob patterns in affected tooling and
recheck the advisory before the next dependency update; install/build tooling still carries risk.

The same review found no known advisories for the 44 registry-locked Python packages. Known-advisory
checks do not prove absence of unknown vulnerabilities, malicious packages, or runtime reachability.
The tracked-text credential review found no convincing credential candidate, but excluded all
environment files, binary/non-UTF-8 content, untracked files, and git history. Do not read or commit
`.env` or `.env.*` contents, or share credentials in issues, logs, fixtures, or run outputs.

Repository hosting settings, branch protection, collaborator permissions, deployed authentication
and headers, private runtime storage, hostile-file fuzzing, and a production threat model were not
assessed or changed. Recheck advisories and the final tree after dependency changes. These bounded
checks are not a security certification or a production-readiness claim.
