"""Tunable constants. Each PR adds its own block under a `# PR N` header."""

# PR 4
# Document classifier (SPEC section 6 step 2). Deterministic: regex and phrase tables only.

# How many leading pages the classifier reads. Title, plan id, and year sit near the front.
CLASSIFY_FIRST_PAGES = 3

# The first lines of page 1 count as the title. A value found there beats one found in body text.
CLASSIFY_TITLE_LINES = 3

# Medicare Advantage contract-plan id, H (local) or R (regional PPO), for example H0028-030.
# A trailing segment is kept unless it is 000 (models.ids.normalize_plan_id). ASCII digits only.
PLAN_ID_PATTERN = r"\b([HR][0-9]{4}-[0-9]{3}(?:-[0-9]{3})?)\b"

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

# PR 3
# CMS public files: how money columns are typed and how text files are decoded.
CMS_MONEY_PRECISION = 12  # total digits, matches the Amount type in plan_diff.models.fields
CMS_MONEY_SCALE = 2  # cents
CMS_ENCODING = "utf8-lossy"  # CMS text files are not always clean UTF-8; never fail on one byte

# PR 5
# Deterministic extraction of the cost-sharing fields (SPEC section 6 step 3).

# A row starts with one of these labels (case-insensitive regex, matched at the start of a line).
# Keyed by plan_diff.models.FieldName value. PR 6 adds the drug and allowance labels.
EXTRACT_LABELS: dict[str, str] = {
    "monthly_premium": r"monthly (?:plan )?premium\b",
    "medical_deductible": r"(?:medical |plan |health )?deductible\b",
    "moop_in_network": r"maximum out[- ]of[- ]pocket(?: amount)?(?: \(?in[- ]network\)?)?",
    "pcp_copay": r"primary care(?: provider| physician)?(?: \(pcp\))?(?: office)? visits?\b",
    "specialist_copay": r"specialist(?: office)? visits?\b",
    "emergency_room": r"emergency (?:room|care)\b",
    "urgent_care": r"urgent(?:ly needed)? care\b",
    "inpatient_stay": r"inpatient hospital(?: stay| care| coverage)?\b",
    "outpatient_surgery": r"outpatient surgery\b",
}

# Text after the amount that names its unit. The first phrase found wins over the field default.
EXTRACT_UNIT_PHRASES: dict[str, str] = {
    "per day": "per_day",
    "per stay": "per_stay",
    "per admission": "per_stay",
    "per visit": "per_visit",
    "per month": "per_month",
    "a month": "per_month",
    "per year": "per_year",
    "a year": "per_year",
}

# Confidence for a rule value: one clean value, one cell with two or more values (in-network or
# first value taken), and two different values for one field on different pages (first page kept).
EXTRACT_CONFIDENCE_RULE = 0.9
EXTRACT_CONFIDENCE_MULTIPLE = 0.6
EXTRACT_CONFIDENCE_CONFLICT = 0.3

# Longest snippet kept on a citation (the schema allows 200 characters).
EXTRACT_SNIPPET_CHARS = 120

# Review 1
# CMS money cells, checked on the requested plans only, before the decimal cast. Matched without
# case after "$", thousands commas, and spaces are stripped. Anything else that is not a plain
# non-negative amount with at most 2 decimal places stops the read, naming file, column, and row.
CMS_MISSING_MARKERS = frozenset({"", "n/a", "na", "not applicable"})
CMS_NOT_COVERED_MARKERS = frozenset({"not covered", "no coverage", "not offered"})
