# PR 12 notes: dashboard shell and Overview

Decisions made while building, without questions to Alex (subagent run, 2026-10-05). Branch
`pr-12-dashboard`, local only.

1. **Design source.** Tokens and patterns are copied from agency-intake-kit at commit `a54faee`
   (its `docs/design.md`): Tailwind's built-in slate neutrals, one indigo accent, the fixed severity
   palette with an icon and a word for every color, `tabular-nums` on numbers, light and dark, a
   240px left nav plus a content column up to 1120px. Copied files say so in a first-line comment:
   `components/severity-badge.tsx`, `tiles.tsx`, `theme-toggle.tsx`, `nav-link.tsx` (adapted),
   `lib/money.ts` (formatMoney only), the loader pattern, and the parseFloat lint rule.
2. **Dark mode without next-themes.** aik uses a tiny inline script in the layout (applies the saved
   choice or the system setting before the first paint) plus its own toggle. Copying that keeps
   both dashboards identical and needs no new library, so next-themes was not added.
3. **No shadcn, no TanStack, no `cn` package.** The Overview has no table and no shadcn primitive.
   `lib/utils.ts` has a 3-line `cn`. PRs 13 and 14 can add TanStack Table when the tables arrive.
4. **One library added:** `lucide-react` 1.52.0 (ISC), the icon set aik uses.
5. **No web font.** aik loads Inter through `next/font/google`, which downloads the font at build
   time. plan-diff makes no external fetches, so it uses the system font stack.
6. **Loader.** `lib/run-loader.ts` parses text, so the server (demo run, read at build time by
   `lib/run-dir.ts`) and a future in-browser loader share the same checks. It reads the manifest,
   accuracy table, every `diff/*.json`, and the review queue (plans and validation wait for PRs 13
   and 14). It refuses money, percents, or costs written as JSON numbers, a shop_again that is not
   true, false, or null, an unknown severity, and an accuracy table from another run, naming the
   file (and line for the queue). Types in `lib/types.ts` mirror `plan-diff schema export`.
7. **Undecided is never No.** `shop_again: null` always shows "Undecided, needs review" with a
   circle-alert icon, and the reason comes from the diff's high review items. Yes uses the orange
   triangle, No the green check.
8. **Order.** Yes first, then undecided, then No; plan id order within each group.
9. **Review item count per plan** counts queue items whose plan id is the plan's own (old) id, so a
   consolidated plan does not repeat its new plan's items. The tile counts the whole queue (10),
   which includes 1 item with no plan (the unreadable demo SB).
10. **Accuracy tile.** Match rate is matched over matched plus mismatched from the per-method total
    rows, same as the engine. The label says "on synthetic fixtures" when every plan id uses the
    made-up H9999 contract, otherwise the plan count; the run's `as_of` date is always shown.
11. **Loading another run in the browser** is not in this PR: the parser is ready for it, the page
    to pick files is left for a later PR to keep this one small.
12. **Screenshots.** aik's Playwright shots need a browser download, so none were added here and
    nothing new runs in `npm run verify`. The Overview was checked by hand on a local production
    build: at 1440 by 900 the page height is exactly 900 (no scrolling) and no sideways scroll; at
    375 there is no sideways scroll and the nav scrolls sideways inside its own bar.
13. The old placeholder page test was replaced by the Overview tests.

## Risks and follow-ups

- The demo has no plan whose answer is No, so the No path is covered by unit tests only.
- The "synthetic" label is inferred from the H9999 plan ids. PR 15's real run must not use H9999.
- "Coming soon" nav items are plain text, so keyboard users skip them; PRs 13 and 14 turn them into links.
