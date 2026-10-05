## PR 12: Dashboard shell and Overview (2026-10-05)

- The dashboard now opens on the Overview, which answers "Which plans changed enough that a client should shop again?" for the committed demo run.
- Flagged plans come first. Each plan shows its shop-again answer as a word and an icon (Yes, No, or "Undecided, needs review"), its reasons, its crosswalk status, and its review item count.
- Summary tiles: plans compared, flagged, undecided, review items, and the accuracy match rate labeled with its slice ("on synthetic fixtures").
- Left nav with dark mode. Plan comparison, Changes, Trust, and Documents show as "coming soon" until PRs 13 and 14.
- Design tokens, severity badges, tiles, and the money formatter are copied from agency-intake-kit. A lint rule bans parseFloat so money is never turned into a float.
