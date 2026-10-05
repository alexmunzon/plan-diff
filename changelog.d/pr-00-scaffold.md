## PR 0: Scaffold (2026-10-05)

- Repo layout copied from agency-intake-kit's scaffold. No feature code yet.
- Engine: Python 3.12 with uv. One package, plan_diff, with a `plan-diff` command whose only subcommand is `version`. ruff, mypy strict, pytest, hypothesis.
- Dashboard: Next.js 16 (App Router, TypeScript, Tailwind), ESLint, vitest. One placeholder page.
- Root `npm run verify` runs every check. CI runs it on every push and PR once a remote exists.
- `.claude/settings.json` permissions and a Stop hook that runs verify before Claude can end a turn with uncommitted changes.
- Changelog moves to one fragment file per PR in changelog.d/.
- No PDF library yet: the choice waits for SPEC because of license fit (see docs/pr-0-notes.md).
