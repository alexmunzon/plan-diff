"""Tunable constants. Each PR adds its own block under a header comment."""

# PR 3
# CMS public files: how money columns are typed and how text files are decoded.
CMS_MONEY_PRECISION = 12  # total digits, matches the Amount type in plan_diff.models.fields
CMS_MONEY_SCALE = 2  # cents
CMS_ENCODING = "utf8-lossy"  # CMS text files are not always clean UTF-8; never fail on one byte
