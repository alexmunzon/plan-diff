"""Tunable constants. Each PR adds its own block under its own header; never reorder others."""

# PR 2
FETCH_DELAY_S = 5  # seconds to wait between downloads, so carrier and CMS sites are not hammered
FETCH_MAX_BYTES = 200 * 1024 * 1024  # refuse any single download larger than 200 MB
FETCH_TIMEOUT_S = 60.0
