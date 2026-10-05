# PR 0 notes: scaffold decisions

Decisions made while building the scaffold, for the orchestrator and Alex to review.

## Copied from agency-intake-kit (aik)
- Same stack and commands: Python 3.12 with uv, Next 16.3.8, React 19.2.8, Node 24, and the same
  `npm run verify` shape at the root (root package.json has scripts only, so there is no root lockfile).
- Same ruff rules (line length 100; E, F, I, UP, B) and mypy strict on src.
- Dashboard config files copied as-is: tsconfig.json, vitest.config.mts, vitest.setup.ts,
  next.config.ts, postcss.config.mjs, .gitignore. Same scripts: lint, typecheck, test, build.
- .claude/settings.json: same allow, ask, and deny lists. No entry was aik-specific, so none was renamed.
  Every deny line and every Jev ask line is kept.
- Stop hook copied unchanged. It holds nothing aik-specific (it runs `npm run verify` from
  $CLAUDE_PROJECT_DIR and loads nvm and uv if the shell lacks them).
- .github/workflows/verify.yml copied unchanged. It will not run until the repo has a GitHub remote.
- .env.example matches aik: JEV_MODE=replay and empty TYPESAFE_API_KEY and ANTHROPIC_API_KEY.

## Different from aik, and why
- One Python package (plan_diff), not four. The Jev client and shared schema will be extracted from
  aik later (ROADMAP section 8), so copying them now would fork them.
- Engine dependencies are only polars, pydantic, typer, rich, httpx, duckdb. No openpyxl, faker,
  anthropic, or PDF library yet. Dev drops pytest-cov and the types-* stubs that only aik needs.
- No PDF library. PyMuPDF (fitz) is AGPL, which would force the whole repo onto AGPL and conflicts with
  the MIT license. Candidates for the SPEC: pypdf (BSD), pdfplumber (MIT, built on pdfminer.six, MIT),
  pypdfium2 (Apache or BSD). The choice and its reasons go in ADR 0001.
- Dashboard drops shadcn, base-ui, TanStack Table, lucide, Playwright, and axe. They arrive with the
  first PR that needs them, so the scaffold stays small. ESLint keeps the Next rules but drops aik's
  money rule (no `parseFloat`), because there is no money code yet; re-add it when premiums arrive.
- No aik components copied. The layout is a bare shell with a light and dark background.
- .gitignore ignores `.env.*` (not just `.env.local`) with `!.env.example`, and ignores `data/raw/*`
  for downloaded public PDFs and CMS files.
- Two extra deny lines in .claude/settings.json: `Read(**/.env)` and `Read(**/.env.*)`, so an .env
  in a subfolder (for example dashboard/) is also unreadable. This only adds protection.
- Changelog uses fragments: one file per PR in changelog.d/, assembled into CHANGELOG.md at release.
  aik edits CHANGELOG.md in every PR, which caused merge conflicts between parallel PRs.
- No `demo` or `shots` scripts yet; they need a pipeline and Playwright.
- No ROADMAP.md, BUILD-GUIDE, or SPEC.md copied in. series-docs/ holds the masters and the SPEC comes next.

## Risks and open items
- The Stop hook runs the full verify (including `next build`) whenever the tree is dirty. Fine now;
  split it by changed path if verify grows past about three minutes.
- npm warns that unrs-resolver (an ESLint dependency) has an install script not yet approved. aik has
  the same dependency. Nothing is broken by it.
- `next dev` may write dashboard/AGENTS.md and dashboard/CLAUDE.md. The generated AGENTS.md contains
  em dashes, so do not commit it as-is.
