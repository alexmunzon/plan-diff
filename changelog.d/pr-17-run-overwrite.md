## PR 17: Preserve runs during overwrite (2026-10-05)

- Keep the previous completed run until its replacement is installed, and restore it if installation fails.
- Retain a named backup for recovery if restoration also fails.
- Refuse an overwrite when the output folder contains the source documents or CMS inputs.
