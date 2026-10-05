## PR 14: Trust page and Documents view (2026-10-05)

- The run manifest now records, for each PDF, its page count and the carrier's own https URL when `--sources` pins that exact file (same SHA-256). Synthetic demo documents have no URL.
- The run manifest records the config it used (confidence floor and shop-again thresholds). The dashboard reads the floor from there instead of keeping its own copy.
- New Trust page: "Which values can a broker quote?" Accuracy per field and method with not comparable counted apart, every PDF and CMS disagreement with both values and both citations, and the review queue grouped by severity and kind with a plain explanation of each kind.
- New Documents page: "Show me the page." Every document the run read, its hash, page count, and the page each value came from. A link goes only to the carrier's own https URL, in a new tab; this site never serves a PDF.
- The Trust and Documents nav entries are now live.
