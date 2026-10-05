## Fix: Review 1, CMS readers and plan ids (2026-10-05)

- One plan id rule for the whole engine: segment 000 is dropped, any other segment is kept, so plans that differ only by segment stay separate. The document classifier no longer drops segments.
- Plan ids now accept regional PPO contracts (R). The CMS readers keep only the plans asked for, so Part D and employer rows in national files are skipped instead of causing errors.
- Money in CMS files is checked before it is typed: more than 2 decimal places or a negative amount stops the read and names the file, column, and row. "N/A" reads as missing and "Not covered" as not covered.
- Duplicate PBP rows are reported with the plan and row numbers; rows with a blank plan id are skipped and counted.
- New messy test fixtures for each reader in `fixtures/cms/messy/`.
