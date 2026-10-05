"""Tunable constants. Each PR adds its own block under a `# PR N` header."""

# PR 4
# Document classifier (SPEC section 6 step 2). Deterministic: regex and phrase tables only.

# How many leading pages the classifier reads. Title, plan id, and year sit near the front.
CLASSIFY_FIRST_PAGES = 3

# The first lines of page 1 count as the title. A value found there beats one found in body text.
CLASSIFY_TITLE_LINES = 3

# Medicare contract-plan id, for example H0028-030. A trailing segment (-001) is ignored.
PLAN_ID_PATTERN = r"\b(H\d{4}-\d{3})(?:-\d{3})?\b"

# A plan year from 2010 to 2099. Not part of a dollar amount or a longer number.
PLAN_YEAR_PATTERN = r"(?<![$\d.,])(20[1-9]\d)(?![\d])(?!,\d)"

# Title phrase, lowercase, to document type value (plan_diff.models.DocumentType).
DOCUMENT_TYPE_PHRASES: dict[str, str] = {
    "summary of benefits": "SB",
    "evidence of coverage": "EOC",
    "annual notice of change": "ANOC",
    "annual notice of changes": "ANOC",
}

# Lowercase name seen in a document to the canonical carrier name. Add aliases here.
CARRIER_ALIASES: dict[str, str] = {
    "example health plan": "Example Health Plan",
    "humana": "Humana",
    "wellcare": "Wellcare",
    "superior healthplan": "Wellcare",
}

# Confidence per attribute: found in the title lines, found only in body text, two or more
# different values found, nothing found.
CONFIDENCE_TITLE = 0.95
CONFIDENCE_BODY = 0.75
CONFIDENCE_AMBIGUOUS = 0.3
CONFIDENCE_MISSING = 0.0

# PR 2
FETCH_DELAY_S = 5  # seconds to wait between downloads, so carrier and CMS sites are not hammered
FETCH_MAX_BYTES = 200 * 1024 * 1024  # refuse any single download larger than 200 MB
FETCH_TIMEOUT_S = 60.0
