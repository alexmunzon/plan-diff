"""Tunable constants. Each PR adds its own block under a `# PR N` header."""

from decimal import Decimal
from typing import Final

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

# PR 6
# Deterministic extraction of the drug and allowance fields. These add to the PR 5 tables above.

# Row labels for the drug and allowance fields (PR 5 rules: case-insensitive, start of line).
# A tier label may name its drug group, for example "Tier 1 (preferred generic)".
_TIER_GROUP = r"(?:\s*\(?(?:preferred |non-preferred )?(?:generics?|brands?)(?: drugs?)?\)?)?"
EXTRACT_LABELS |= {
    "drug_deductible": r"(?:part d (?:drug )?|(?:prescription |rx )?drug |pharmacy )deductible\b",
    "drug_tier_1": r"tier 1\b" + _TIER_GROUP,
    "drug_tier_2": r"tier 2\b" + _TIER_GROUP,
    "drug_tier_3": r"tier 3\b" + _TIER_GROUP,
    "dental_allowance": r"(?:comprehensive )?dental(?: services| care| benefits?)?"
    r" (?:allowance|maximum|limit)\b",
    "otc_allowance": r"(?:over[- ]the[- ]counter|otc)(?: \(otc\))?(?: items| products| benefits?)?"
    r" (?:allowance|credit|card)\b",
}

# Allowance periods. The first phrase found in a cell wins over the field's default unit.
EXTRACT_UNIT_PHRASES |= {
    "per quarter": "per_quarter",
    "a quarter": "per_quarter",
    "every quarter": "per_quarter",
    "each quarter": "per_quarter",
    "quarterly": "per_quarter",
    "every 3 months": "per_quarter",
    "every three months": "per_quarter",
    "every month": "per_month",
    "each month": "per_month",
    "every year": "per_year",
    "each year": "per_year",
    "per calendar year": "per_year",
    "a calendar year": "per_year",
    "each calendar year": "per_year",
    "annual": "per_year",
    "annually": "per_year",
    "yearly": "per_year",
    "monthly": "per_month",
    "every 6 months": "per_half_year",
    "every six months": "per_half_year",
    "twice a year": "per_half_year",
    "twice per year": "per_half_year",
    "twice yearly": "per_half_year",
    "semiannual": "per_half_year",
    "semiannually": "per_half_year",
    "semi-annual": "per_half_year",
    "semi-annually": "per_half_year",
}

# Any period wording in an allowance cell. If it is here but not in the phrase table above, the
# amount is kept with no unit and goes to review (kind unknown_period); it never defaults to a year.
EXTRACT_PERIOD_PATTERN = (
    r"\b(?:every|each|per|a|once|twice|times)\b[^$%;,]{0,20}?\b(?:days?|weeks?|months?|quarters?"
    r"|years?|benefit periods?)\b|\b(?:bi-?monthly|bi-?annual(?:ly)?|bi-?weekly|weekly|monthly"
    r"|annual(?:ly)?|yearly)\b"
)
EXTRACT_CONFIDENCE_UNKNOWN_PERIOD = 0.6

# When one cell holds two or more values, segments with these markers win, tried in this order;
# a field lists the markers it uses. A drug tier takes the standard pharmacy, 30-day supply price.
EXTRACT_PREFER_MARKERS: dict[str, str] = {
    "in-network": r"\bin[- ]network\b",
    "standard pharmacy": r"\bstandard\b",
    "30-day supply": r"\b(?:30|thirty)[- ]day\b|\bone[- ]month\b",
}

# Review 1
# CMS money cells, checked on the requested plans only, before the decimal cast. Matched without
# case after "$", thousands commas, and spaces are stripped. Anything else that is not a plain
# non-negative amount with at most 2 decimal places stops the read, naming file, column, and row.
CMS_MISSING_MARKERS = frozenset({"", "n/a", "na", "not applicable"})
CMS_NOT_COVERED_MARKERS = frozenset({"not covered", "no coverage", "not offered"})

# PR 7
# Validation against CMS (SPEC section 6 step 6, decision 5: flag it, never pick).

# The unit a CMS value carries, per field. None means CMS does not say: an allowance with no CMS
# period is never compared ("period not comparable"); docs/cms-fields.md says the OTC and dental
# period columns are not read yet. Inpatient is the per-day first day range.
VALIDATE_CMS_UNITS: dict[str, str | None] = {
    "monthly_premium": "per_month",
    "medical_deductible": "per_year",
    "moop_in_network": "per_year",
    "pcp_copay": "per_visit",
    "specialist_copay": "per_visit",
    "emergency_room": "per_visit",
    "urgent_care": "per_visit",
    "inpatient_stay": "per_day",
    "outpatient_surgery": "per_visit",
    "drug_deductible": "per_year",
    "drug_tier_1": "per_prescription",
    "drug_tier_2": "per_prescription",
    "drug_tier_3": "per_prescription",
    "dental_allowance": None,
    "otc_allowance": None,
}

# Severity of a PDF vs CMS mismatch. Fields behind the shop-again flag (decision 4) are high.
VALIDATE_SEVERITY_DEFAULT = "medium"
VALIDATE_SEVERITY: dict[str, str] = {
    "monthly_premium": "high",
    "moop_in_network": "high",
    "drug_deductible": "high",
}

# Confidence on a mismatch review item: low, because two official sources disagree.
VALIDATE_MISMATCH_CONFIDENCE = 0.3

# PR 8
# Shop-again thresholds (SPEC decision 4). A rise of at least this much flags the plan. Money is
# Decimal. Termination, consolidation, a lost county, and a removed benefit always flag.
SHOP_AGAIN_PREMIUM_UP = Decimal("20.00")  # monthly premium, per month
SHOP_AGAIN_MOOP_UP = Decimal("1000.00")  # in-network maximum out-of-pocket, per year
SHOP_AGAIN_DRUG_DEDUCTIBLE_UP = Decimal("0.01")  # any rise at all

# Review 2
# The shop-again flag is never confidently wrong (SPEC decisions 4 and 5). A threshold field
# (premium, MOOP, drug deductible) or a removed benefit cannot decide the flag when either year's
# value is below this confidence, missing, not comparable, in the wrong unit, or disagrees with CMS.
SHOP_AGAIN_CONFIDENCE_FLOOR = 0.7  # a value at the floor is trusted; below it goes to review

# County names compare after lowercasing, dropping punctuation, and dropping this trailing word, so
# "Bexar County", "BEXAR", and "Bexar" are one county.
COUNTY_SUFFIXES = ("county",)

# PR 9
# The run command (SPEC section 7) and the CMS unzip step (review 1 finding 6).

# A fetched CMS zip is refused before anything is written if it holds more members than this, or
# more uncompressed bytes than this (counted while writing, so a lying header cannot get past).
UNZIP_MAX_MEMBERS = 5_000
UNZIP_MAX_BYTES = 4 * 1024 * 1024 * 1024  # 4 GB; a full PBP release unzips to about 1 GB

# A run id becomes a folder name under --out: letters, digits, dot, dash, underscore only.
RUN_ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$"

# When several documents describe one plan year, a field is read from the first type that has it.
RUN_DOCUMENT_PRIORITY = ("SB", "EOC", "ANOC", "OTHER")

# Jev and the LLM are off in PR 9 (they arrive in PRs 10 and 11). The manifest records the mode.
RUN_JEV_MODE: Final = "off"
RUN_LLM_MODE: Final = "off"

# Review 2 (extraction)
# Extraction never turns an unreadable or ambiguous cell into a confident value (SPEC: never guess).

# Units a cost-sharing or drug value may state for itself (per day, stay, visit, prescription).
# Period words (monthly, a year, every quarter) set the unit only for allowances, and for the
# premium when written right next to the premium amount. Every other field keeps its default unit.
EXTRACT_COST_UNIT_PHRASES: dict[str, str] = {
    "per day": "per_day",
    "a day": "per_day",
    "per stay": "per_stay",
    "per admission": "per_stay",
    "per visit": "per_visit",
    "per prescription": "per_prescription",
}
EXTRACT_PERIOD_UNIT_PHRASES: dict[str, str] = {
    phrase: unit
    for phrase, unit in EXTRACT_UNIT_PHRASES.items()
    if unit in {"per_month", "per_quarter", "per_half_year", "per_year"}
}

# Section headings (a whole line with no amount that is not a field label). Inside a drug section,
# the fields listed in EXTRACT_DRUG_SECTION_LABELS use the stricter label, so a drug "Deductible"
# row never reads as the medical deductible. A medical heading ends the drug section.
EXTRACT_DRUG_SECTION_HEADING = (
    r"^(?:section [\w.]+[:.]?\s*)?(?:medicare )?(?:part d\b|(?:outpatient )?prescription drugs?\b"
    r"|rx drugs?\b|pharmacy\b|drug (?:benefits?|coverage)\b)"
)
EXTRACT_MEDICAL_SECTION_HEADING = (
    r"^(?:section [\w.]+[:.]?\s*)?(?:medical|hospital|doctor|health|dental|vision|hearing"
    r"|extra|additional|other)\b"
)
EXTRACT_DRUG_SECTION_LABELS: dict[str, str] = {
    "medical_deductible": r"(?:medical|health) deductible\b",
}

# Footnote markers stripped before amounts are read ("$45*", "$45" plus a superscript 1).
EXTRACT_FOOTNOTE_MARKERS = "¹²³⁰⁴⁵⁶⁷⁸⁹*†‡"
# A digit glued to an amount ("$1,5001") or one or two lone digits right after it ("$45 1") may
# be a footnote marker or part of the number. The first reading is kept at this confidence and a
# conflicting_values review item says why.
EXTRACT_AMBIGUOUS_DIGIT = r"^(?:\d|\s\d{1,2}(?![\d,.%$\w-]))"
EXTRACT_CONFIDENCE_AMBIGUOUS_DIGIT = 0.6

# Two values in one cell: when the chosen value's own words carry one of these markers (keys of
# EXTRACT_PREFER_MARKERS), it is read at this confidence with a low-severity review item noting
# the rule. A "first value" pick with no marker stays at EXTRACT_CONFIDENCE_MULTIPLE (0.6). Kept
# above SHOP_AGAIN_CONFIDENCE_FLOOR so an in-network MOOP or premium can still decide the flag.
EXTRACT_LABELED_RULES = frozenset({"in-network", "standard pharmacy"})
EXTRACT_CONFIDENCE_LABELED = 0.85

# A yearly field (MOOP, medical or drug deductible) whose own words state another period ("$3,400
# per month") keeps the amount and the stated unit at this confidence, below
# SHOP_AGAIN_CONFIDENCE_FLOOR, with an unexpected_unit review item.
EXTRACT_CONFIDENCE_UNEXPECTED_UNIT = 0.5
