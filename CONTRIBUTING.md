# Contributing

Read [CLAUDE.md](CLAUDE.md), the [README](README.md), and the [documentation index](docs/README.md)
before changing behavior. This repository is a public/synthetic-only recruiting demo.

## Reproducible setup and checks

Use Node 24 and uv with Python 3.12. From the root:

```sh
cd engine && uv sync --locked && cd ..
cd dashboard && npm ci && cd ..
npm run verify
```

The root has no installable dependencies. The two lockfiles are the canonical dependency inputs.
`npm run verify` runs Ruff lint and format checks, mypy, pytest, dashboard lint, generated Next.js
types and TypeScript checks, Vitest, and a production build. Run it before committing. Focused tests
help during development but do not replace this gate. Engine tests refuse real network connections;
use mock transports. CI uses replay mode and never downloads carrier sources.

## Change boundaries

- Keep changes focused and reviewable, ideally below 400 changed lines. Use one PR per worktree.
- Add tests for changed behavior and a fragment in `changelog.d/`; do not edit `CHANGELOG.md` directly.
- Preserve every field's source/page citation, exact decimal money, separate excluded counts,
  missing values, disagreements, and review items. A matching CMS value does not erase uncertainty.
- Treat the Texas 48/48 result as in-sample only. Keep 10 missing and 2 incomparable values visible,
  along with the shared-OTC-card limitation. New layouts need held-out checks before accuracy claims.
- Keep PDFs and generated local runs out of git. Only approved small fixtures and public/synthetic
  JSON snapshots belong in committed demo data; never add PHI or real client records.
- Do not read environment files, commit credentials, enable live/record model calls, or fetch new
  carrier files as part of routine verification. Downloads and paid calls need explicit approval.
- Dependency changes need license review, intentional lockfile updates, and fresh checks. Do not
  force audit fixes or introduce an unverified override for an advisory without an upstream fix. The
  braces fast-glob stand-in is the tested exception; see SECURITY.md.
- Record lasting architectural decisions in `docs/adr/`. Publishing, merging, and deployment need
  the maintainer's explicit go-ahead; successful local checks do not authorize them.

See [SECURITY.md](SECURITY.md) before reporting a suspected vulnerability or proposing security work.
