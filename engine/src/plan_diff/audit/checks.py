"""Deterministic audit checks and the verdict rules.

Separate questions, each its own checks: does the claim's text say only what its typed parts
say; does the citation resolve (document, bytes, page, quote); does the document apply (plan,
booklet pages, year, effective dates, supersession); does the cited row support the part (the
extractor's own labels and value parser, inside a narrow declared grammar); and does any other
applicable evidence, including the run's recorded CMS disagreements, read differently.

The deterministic lane proves only exact typed facts written as one plain table row on a page
with no qualifying wording. It is not a general semantic judge. Anything else goes to a person.
"""

import re
import unicodedata
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, fields
from datetime import date
from decimal import Decimal
from functools import lru_cache

from plan_diff import config
from plan_diff.audit.evidence import CmsConflict, Corpus
from plan_diff.audit.models import (
    Check,
    CheckName,
    Claim,
    ClaimAudit,
    ClaimPart,
    ClaimSource,
    Contrary,
    EvidenceDocument,
    Location,
    PartResult,
    SourceResult,
    Verdict,
)
from plan_diff.classify.booklet import BookletResult, plan_pages, plans_named
from plan_diff.extract.extractor import drug_section_flags, drug_section_label, skip_section_flags
from plan_diff.extract.values import FAMILIES, FieldParser, Parsed, parse_value, value_count
from plan_diff.models.fields import FieldName, FieldValue, Unit
from plan_diff.models.ids import DocumentType

V = Verdict
PARSERS: dict[FieldName, FieldParser] = {p.field: p for fam in FAMILIES.values() for p in fam}
# Claim wording uses sentence forms, not the extractor's table-row lookaheads. Keep a small
# explicit alias set; amounts or unique units alone never identify the benefit being claimed.
_CLAIM_LABELS = {f: p.label for f, p in PARSERS.items()} | {
    FieldName.MONTHLY_PREMIUM: re.compile(r"\b(?:monthly (?:plan )?)?premium\b", re.I),
    FieldName.MEDICAL_DEDUCTIBLE: re.compile(r"\b(?:medical|plan|health) deductible\b", re.I),
    FieldName.MOOP_IN_NETWORK: re.compile(r"\bmaximum out[- ]of[- ]pocket\b", re.I),
    FieldName.EMERGENCY_ROOM: re.compile(r"\bemergency (?:room|care)\b", re.I),
    FieldName.INPATIENT_STAY: re.compile(r"\binpatient (?:hospital )?(?:stay|care)\b", re.I),
    FieldName.OTC_ALLOWANCE: re.compile(
        r"\b(?:otc|over[- ]the[- ]counter) (?:allowance|credit|card)\b", re.I
    ),
}
_EXCLUDE = {f: re.compile(p, re.IGNORECASE) for f, p in config.EXTRACT_CELL_EXCLUDE.items()}
_DASHES = str.maketrans({"–": "-", "—": "-"})
_MONEY = r"\$\s?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{1,2})?"
_PERCENT = r"\d{1,3}(?:\.\d{1,2})?\s?%"
_AMOUNT = re.compile(f"{_MONEY}|{_PERCENT}")
# Every unit phrase the extractor knows, and the unit it names. Longest first, so "per calendar
# year" wins over "a calendar year" and "per year" at the same place.
_UNIT_OF: dict[str, str] = {**config.EXTRACT_UNIT_PHRASES, **config.EXTRACT_COST_UNIT_PHRASES}
_PHRASES = sorted(_UNIT_OF, key=len, reverse=True)
_PHRASE = re.compile(r"\b(?:" + "|".join(re.escape(p) for p in _PHRASES) + r")\b")
_FILLER = re.compile(r"\b(?:copay|coinsurance|not covered)\b|[,.;:()\s]+", re.IGNORECASE)
# Footnote markers, plus every character that compatibility folding would turn into a digit
# (superscript, subscript, circled, fullwidth digits): "$45" then a circled 1 must never read as
# "$451". Such characters are kept as they are and treated as footnote markers.
_DIGIT_LIKE = "".join(
    ch
    for ch in map(chr, range(0x80, 0x20000))
    if (folded := unicodedata.normalize("NFKC", ch)) != ch and any(c.isdigit() for c in folded)
)
_MARKERS = "".join(dict.fromkeys(config.EXTRACT_FOOTNOTE_MARKERS + _DIGIT_LIKE))
_FOOTNOTE = re.compile("[" + re.escape(_MARKERS) + "]")
# Wording that can narrow, negate, or share a benefit. On the page outside the checked row, or in
# the claim's own text without a matching condition, any of these sends the claim to a person.
_QUALIFIER = re.compile(
    r"\b(?:not|no|never|except\w*|exclud\w*|unless|only|limit\w*|referral\w*|prior auth\w*"
    r"|authoriz\w*|shar\w*|combined|pooled|out[- ]of[- ]network|non[- ]network|depend\w*"
    r"|eligib\w*|waiv\w*|after|before|up to|or)\b",
    re.IGNORECASE,
)
_CLAIM_SCOPE = re.compile(
    r"\b(?:all|every|any|always|unlimited|dedicated|without|includ\w*|cover\w*|guarant\w*"
    r"|free)\b",
    re.IGNORECASE,
)
# Lines every synthetic SB carries that say nothing about a benefit. Kept narrow on purpose.
_BOILERPLATE = re.compile(
    r"^(?:benefit what you pay|page \d+ of \d+|january 1, \d{4} to december 31, \d{4})$",
    re.IGNORECASE,
)

NOTICE = (
    "Document review aid only. Deterministic rules check exact typed facts against one cited "
    "table row; they are not a general semantic judge, and no model was called. Not coverage "
    "adjudication, clinical or legal advice, or a recommendation for any person's plan."
)


@dataclass(frozen=True)
class Policy:
    """Each switch is on in the real audit. Turning one off is a negative control (a mutant)."""

    require_support: bool = True  # off: citation-exists-only baseline
    check_plan_year: bool = True
    check_effective_dates: bool = True
    check_contrary: bool = True
    unknown_blocks: bool = True  # off: an unknown is treated as a pass
    # Policy 2 (Alex, 2026-10-25): a document whose effective dates do not cover the claim can
    # neither support nor contradict it. Off: policy 1, where unknown dates alone did not block
    # (kept to score the original frozen labels, never the real audit's default).
    unknown_dates_block: bool = True

    def as_dict(self) -> dict[str, bool]:
        return {f.name: getattr(self, f.name) for f in fields(self)}


# Footnote markers are kept through compatibility folding: NFKC would turn "$45" plus a
# superscript 1 into "$451", a different amount. Each marker rides through as a private-use
# character (which NFKC leaves alone) and is put back afterwards.
_KEEP = {m: chr(0xE000 + i) for i, m in enumerate(_MARKERS)}
_HIDE, _SHOW = str.maketrans(_KEEP), str.maketrans({v: k for k, v in _KEEP.items()})


def norm(text: str) -> str:
    """Whitespace collapsed, dashes plain, compatibility forms folded except footnote markers.
    Case is kept."""
    folded = unicodedata.normalize("NFKC", text.translate(_HIDE)).translate(_SHOW)
    return " ".join(folded.translate(_DASHES).split())


def _amount(token: str) -> tuple[str, Decimal]:
    kind = "percent" if token.endswith("%") else "money"
    return kind, Decimal(re.sub(r"[$,%\s]", "", token))


@dataclass(frozen=True)
class _Said:
    amount: tuple[str, Decimal]
    before: str  # the words since the previous amount, where the benefit is usually named
    unit: str | None  # the unit phrase after it, before the next amount (None: no phrase)


def _said(text: str) -> list[_Said]:
    """Each amount in free text with the words before it and the unit phrase after it.
    "Premium is $45 per month and specialist visits $25 per visit" gives 45 with "premium is"
    and per_month, then 25 with "per month and specialist visits" and per_visit."""
    low = norm(text).lower()
    found = []
    matches = list(_AMOUNT.finditer(low))
    for i, m in enumerate(matches):
        start = matches[i - 1].end() if i else 0
        end = matches[i + 1].start() if i + 1 < len(matches) else len(low)
        phrase = _PHRASE.search(low, m.end(), end)
        unit = _UNIT_OF[phrase.group(0)] if phrase else None
        found.append(_Said(_amount(m.group(0)), low[start : m.start()], unit))
    return found


def _part_amount(value: FieldValue | None) -> tuple[str, Decimal] | None:
    if value is None or value.kind == "not_covered":
        return None
    if value.kind == "coinsurance":
        return ("percent", value.percent)
    return ("money", value.amount)


def _is_any_label(line: str) -> bool:
    return any(p.label.match(line) for p in PARSERS.values())


@dataclass(frozen=True)
class Row:
    page: int
    line: str  # the whole row as read, normalized
    cell: str  # the text after the label


@dataclass(frozen=True)
class _Lines:
    lines: list[list[str]]  # per page, normalized, blank lines dropped
    drug: list[list[bool]]  # inside a drug section (the extractor's rule, across pages)
    skip: list[list[bool]]  # inside a section the extractor never reads


@lru_cache(maxsize=64)
def _lines(texts: tuple[str, ...]) -> _Lines:
    """One document's lines and section flags, computed once per document text."""
    lines = [[ln for raw in t.splitlines() if (ln := norm(raw))] for t in texts]
    return _Lines(lines, drug_section_flags(lines), skip_section_flags(lines))


def carried_qualifier(texts: Sequence[str], page: int) -> list[str]:
    """A heading from an earlier page that may still govern this one ("OUT-OF-NETWORK
    BENEFITS" at the end of page 1, rows on page 2): the last line before the page that has no
    amount, is no benefit row, and is not page boilerplate. Listed only when it qualifies."""
    for lines in reversed(_lines(tuple(texts)).lines[: page - 1]):
        for line in reversed(lines):
            if _BOILERPLATE.match(line) or _AMOUNT.search(line) or _is_any_label(line):
                continue
            return (
                [f"carried from an earlier page: {line[:100]}"] if _QUALIFIER.search(line) else []
            )
    return []


def rows_on(texts: Sequence[str], field: FieldName, page: int) -> list[Row]:
    """Rows for `field` on one page of a document: a line that starts with the extractor's label
    for it, with the extractor's section rules (a drug section's stricter label, skipped
    sections). `texts` is every page, since a section can start on an earlier page."""
    parser, exclude = PARSERS[field], _EXCLUDE.get(field.value)
    doc = _lines(tuple(texts))
    found = []
    for line, in_drug, skipped in zip(
        doc.lines[page - 1], doc.drug[page - 1], doc.skip[page - 1], strict=True
    ):
        m = (drug_section_label(parser) if in_drug else parser.label).match(line)
        if m is None or skipped:
            continue
        cell = line[m.end() :].strip(" :")
        if exclude is not None and exclude.search(cell):
            continue
        found.append(Row(page, line[:300], cell))
    return found


def residue(cell: str) -> str:
    """What the declared grammar cannot explain: the cell minus amounts, unit phrases, filler."""
    rest = _AMOUNT.sub(" ", norm(cell).lower())
    for phrase in _PHRASES:
        rest = re.sub(rf"\b{re.escape(phrase)}\b", " ", rest)
    return " ".join(_FILLER.sub(" ", rest).split())


def page_qualifiers(text: str, row: Row | None) -> list[str]:
    """Lines outside the checked row that carry qualifying wording (headers, notes, footnotes)."""
    found = []
    for raw in text.splitlines():
        line = norm(raw)
        if not line or (row is not None and line == row.line) or _BOILERPLATE.match(line):
            continue
        if _is_any_label(line):
            continue  # another benefit's row; its own words are checked when it is cited
        if _QUALIFIER.search(line) or _FOOTNOTE.match(line):
            found.append(line[:120])
    return found


def _clean(parsed: Parsed | None, cell: str) -> bool:
    return (
        parsed is not None
        and value_count(cell) == 1
        and not (
            parsed.multiple or parsed.ambiguous or parsed.unknown_period or parsed.unexpected_unit
        )
    )


@dataclass(frozen=True)
class RowReading:
    row: Row
    parsed: Parsed | None
    grammar_problem: str | None  # None: one plain value the rules fully explain


def read_row(row: Row, part: ClaimPart) -> RowReading:
    parsed = parse_value(row.cell, PARSERS[part.benefit]) if row.cell else None
    leftover = residue(row.cell)
    for condition in part.conditions:
        leftover = " ".join(leftover.replace(residue(condition), " ").split())
    problem = None
    if not row.cell:
        problem = "the row has no value on the same line"
    elif _FOOTNOTE.search(row.cell):
        problem = "the row carries a footnote marker, so a footnote may qualify it"
    elif not _clean(parsed, row.cell):
        problem = "the row holds more than one value or an unclear unit"
    elif (
        parsed is not None
        and (stated := _stated_units(row.cell))
        and stated != {parsed.unit.value if parsed.unit else None}
    ):
        # The value parser falls back to a field's default unit ("$45 per month" on a specialist
        # row reads per visit), so a period the row states in words is compared directly.
        problem = f"the row states {sorted(stated)}, which the rules do not read as one unit"
    elif leftover:
        problem = f"the row says more than the rules can check: {leftover!r}"
    return RowReading(row, parsed, problem)


def _stated_units(cell: str) -> set[str]:
    return {_UNIT_OF[m.group(0)] for m in _PHRASE.finditer(norm(cell).lower())}


def _show(value: FieldValue, unit: Unit | None) -> str:
    if value.kind == "not_covered":
        return "not covered"
    text = f"{value.percent}%" if value.kind == "coinsurance" else f"${value.amount}"
    return f"{text} {unit.value.replace('_', ' ')}" if unit is not None else text


def compare(part: ClaimPart, parsed: Parsed) -> tuple[str, str]:
    """pass, fail (the row states another value), or unknown (the two are not comparable)."""
    if part.value is None:
        return "unknown", "the claim names no typed value, so the rules cannot check it"
    shown = _show(parsed.value, parsed.unit)
    if part.value == parsed.value and part.unit == parsed.unit:
        return "pass", f"the row states exactly {shown}"
    if part.value.kind == parsed.value.kind and part.unit != parsed.unit:
        # Like validation's not_comparable: a different period or unit is not a contradiction.
        return "unknown", f"the row states {shown}, a different unit; not comparable"
    return "fail", f"the row states {shown}, not {_show(part.value, part.unit)}"


def _loc(doc: EvidenceDocument, page: int, row: str | None = None) -> Location:
    printed = doc.meta.printed_page_labels.get(str(page))
    return Location(document_id=doc.document_id, page=page, printed_page=printed, row=row)


def _dates(doc: EvidenceDocument, claim: Claim, loc: Location) -> Check:
    """Do the document's declared effective dates cover the claim? Fail only when a declared
    date excludes it; pass only when both dates are declared and cover the claim's as-of date,
    or the whole plan year when no as-of date is given; anything else is unknown, never assumed.
    """
    start, end = doc.meta.effective_from, doc.meta.effective_to
    first, last = date(claim.year, 1, 1), date(claim.year, 12, 31)
    lo, hi = (claim.as_of, claim.as_of) if claim.as_of else (first, last)
    said = f"the claim's date {claim.as_of}" if claim.as_of else f"plan year {claim.year}"
    if (start is not None and hi < start) or (end is not None and lo > end):
        why = f"{said} is outside the document's declared effective dates"
        return _check("effective_date_applies", "fail", why, loc)
    if start is not None and end is not None and start <= lo and hi <= end:
        return _check("effective_date_applies", "pass", f"the declared dates cover {said}")
    if start is None and end is None:
        why = "effective dates unknown (not declared)"
    elif claim.as_of:
        why = f"only one effective date is declared, so it is unknown whether it covers {said}"
    else:
        why = f"no as-of date, and the declared dates do not cover all of {said}"
    return _check("effective_date_applies", "unknown", why)


def _cyclic_replacement(doc: EvidenceDocument, replacement: str, corpus: Corpus) -> bool:
    """A cycle establishes no authority order. Visit each declared document at most once."""
    pending = list(doc.meta.supersedes)
    seen = {doc.document_id}
    while pending:
        current = pending.pop()
        if current == replacement:
            return True
        if current in seen:
            continue
        seen.add(current)
        if current in corpus.documents:
            pending.extend(corpus.documents[current].meta.supersedes)
    return False


def _superseded_by(
    doc: EvidenceDocument, corpus: Corpus, claim: Claim, policy: Policy
) -> str | None:
    """The id of a document that explicitly replaces `doc` for the claim, from metadata only.

    A replacement for another plan or plan year never counts. Its declared dates must cover the
    claim's as_of date; with no as_of date, they must cover the whole plan year, since a
    replacement that starts later or ends sooner may not cover the date the claim speaks about."""
    first, last = date(claim.year, 1, 1), date(claim.year, 12, 31)
    for other in corpus.documents.values():
        if doc.document_id not in other.meta.supersedes:
            continue
        if not other.readable or other.document_id == doc.document_id:
            continue  # unverifiable bytes or self-reference cannot establish authority
        if _cyclic_replacement(doc, other.document_id, corpus):
            continue
        if other.year is not None and other.year != claim.year:
            continue
        if other.plan_id is not None and other.plan_id != claim.plan_id:
            continue
        if other.plan_id is None and claim.plan_id not in _named(
            corpus.pages.get(other.sha256, ())
        ):
            continue  # a booklet (or unknown document) that never names the claim's plan
        start, end = other.meta.effective_from, other.meta.effective_to
        if policy.unknown_dates_block and policy.unknown_blocks and (start is None or end is None):
            continue  # unknown replacement coverage cannot dismiss applicable evidence
        if start is not None and (claim.as_of or first) < start:
            continue  # the replacement had not taken effect yet (or may not have)
        if end is not None and (claim.as_of or last) > end:
            continue  # the replacement had already ended (or may have)
        texts = corpus.pages[other.sha256]
        page = 1
        if len(_named(texts)) > 1:
            booklet = _booklet(texts, claim.plan_id)
            if booklet.problem or booklet.pages is None:
                continue
            page = booklet.pages.first
        context = _context(claim, other, corpus, policy, page, supersession=False)
        if any(
            c.outcome == "fail"
            or (
                c.outcome == "unknown"
                and policy.unknown_blocks
                and (c.name != "effective_date_applies" or policy.unknown_dates_block)
            )
            for c in context
        ):
            continue
        return other.document_id
    return None


def _check(name: CheckName, outcome: str, reason: str, loc: Location | None = None) -> Check:
    return Check.model_validate(
        {"name": name, "outcome": outcome, "reason": reason, "location": loc}
    )


def _tie_problem(claim: Claim, part: ClaimPart, said: list[_Said]) -> str | None:
    """Bind each amount to its own named benefit and unit, including equal-amount parts."""
    mine = _part_amount(part.value)
    here = [s for s in said if s.amount == mine]
    if not here:
        return "the text does not state this amount"
    if any(
        not any(
            _CLAIM_LABELS[p.benefit].search(s.before)
            for p in claim.parts
            if _part_amount(p.value) == mine
        )
        for s in here
    ):
        return "an occurrence of this amount has no matching named typed benefit"
    tied = [s for s in here if _CLAIM_LABELS[part.benefit].search(s.before)]
    if not tied:
        return "the rules cannot tie this amount to its named benefit in the text"
    if any(
        label.search(s.before)
        for s in tied
        for benefit, label in _CLAIM_LABELS.items()
        if benefit != part.benefit
    ):
        return "the text names another benefit next to this amount"
    if any(s.unit and s.unit != (part.unit.value if part.unit else None) for s in tied):
        return "the text gives this benefit's amount a different unit than its typed part"
    return None


def text_check(claim: Claim, part: ClaimPart) -> Check:
    """The claim's own words must say no more than its typed parts (decomposition is declared)."""
    said = _said(claim.text)
    stated = {s.amount for s in said}
    typed = {a for p in claim.parts if (a := _part_amount(p.value)) is not None}
    mine = _part_amount(part.value)
    conditions = " ".join(c.lower() for p in claim.parts for c in p.conditions)
    plain = norm(claim.text)  # folded first, so fullwidth or styled letters cannot hide a word
    context = _AMOUNT.sub(" ", plain)
    if plans_named(context) - {claim.plan_id} or set(re.findall(r"\b20\d{2}\b", context)) - {
        str(claim.year)
    }:
        return _check("text_matches_parts", "unknown", "the text names a different plan or year")
    if any(
        not re.search(r"(?<!\w)" + re.escape(norm(c).lower()) + r"(?!\w)", plain.lower())
        for c in part.conditions
    ):
        return _check("text_matches_parts", "unknown", "the text omits a typed condition")
    words = {w.lower() for w in _CLAIM_SCOPE.findall(plain) + _QUALIFIER.findall(plain)}
    unexplained = sorted(w for w in words if w not in conditions)
    if part.value is not None and part.value.kind == "not_covered":
        if "not covered" not in plain.lower():
            return _check("text_matches_parts", "unknown", "the text does not say not covered")
        before = plain.lower().split("not covered", 1)[0]
        if not _CLAIM_LABELS[part.benefit].search(before) or any(
            label.search(before)
            for benefit, label in _CLAIM_LABELS.items()
            if benefit != part.benefit
        ):
            return _check("text_matches_parts", "unknown", "not covered names a different benefit")
    elif mine is not None and (problem := _tie_problem(claim, part, said)) is not None:
        return _check("text_matches_parts", "unknown", problem)
    if stated - typed:
        why = "the text states amounts no typed part carries"
        return _check("text_matches_parts", "unknown", why)
    if unexplained:
        why = f"the text says {unexplained}, which no typed condition carries"
        return _check("text_matches_parts", "unknown", why)
    return _check("text_matches_parts", "pass", "the text says what the typed parts say")


@lru_cache(maxsize=64)
def _named(texts: tuple[str, ...]) -> set[str]:
    return set().union(*(plans_named(t) for t in texts))


@lru_cache(maxsize=256)
def _booklet(texts: tuple[str, ...], plan_id: str) -> BookletResult:
    return plan_pages(texts, plan_id)


_UNKNOWN_IDENTITY = "the document's plan or year is unknown, so it cannot be shown to apply"


def _unknown_identity(doc: EvidenceDocument, named: set[str]) -> bool:
    return doc.year is None or (doc.plan_id is None and len(named) < 2)


def _context(
    claim: Claim,
    doc: EvidenceDocument,
    corpus: Corpus,
    policy: Policy,
    page: int,
    *,
    supersession: bool = True,
) -> list[Check]:
    loc = _loc(doc, page)
    out: list[Check] = []
    texts = corpus.pages[doc.sha256]
    named = _named(texts)
    if not policy.check_plan_year:
        out.append(_check("plan_year_matches", "not_run", "switched off"))
    elif doc.year is not None and doc.year != claim.year:
        why = f"document is {doc.plan_id} {doc.year}; claim is {claim.plan_id} {claim.year}"
        out.append(_check("plan_year_matches", "fail", why, loc))
    elif _unknown_identity(doc, named):
        out.append(_check("plan_year_matches", "unknown", _UNKNOWN_IDENTITY, loc))
    elif len(named) < 2 and doc.plan_id != claim.plan_id:
        why = f"document is {doc.plan_id} {doc.year}; claim is {claim.plan_id} {claim.year}"
        out.append(_check("plan_year_matches", "fail", why, loc))
    elif doc.document_type == DocumentType.ANOC:
        why = "an Annual Notice of Change lists two years' amounts side by side"
        out.append(_check("plan_year_matches", "unknown", why, loc))
    else:
        out.append(_check("plan_year_matches", "pass", f"the document is for {claim.year}", loc))
    if policy.check_plan_year and len(named) > 1:  # PR 15 booklet rule, reused as is
        booklet = _booklet(texts, claim.plan_id)
        if claim.plan_id not in named:
            out.append(_check("plan_pages", "fail", f"the booklet never names {claim.plan_id}"))
        elif booklet.problem or booklet.pages is None:
            out.append(_check("plan_pages", "unknown", booklet.problem or "pages unclear", loc))
        elif not booklet.pages.first <= page <= booklet.pages.last:
            why = f"page {page} is outside {claim.plan_id}'s pages {booklet.pages}"
            out.append(_check("plan_pages", "fail", why, loc))
        else:
            out.append(_check("plan_pages", "pass", f"inside pages {booklet.pages}", loc))
    if not policy.check_effective_dates:
        out.append(_check("effective_date_applies", "not_run", "switched off"))
        out.append(_check("not_superseded", "not_run", "switched off"))
        return out
    out.append(_dates(doc, claim, loc))
    if not supersession:
        return out  # replacement applicability reuses these checks without recursion
    if (newer := _superseded_by(doc, corpus, claim, policy)) is not None:
        out.append(_check("not_superseded", "fail", f"{newer} explicitly supersedes it", loc))
    else:
        out.append(_check("not_superseded", "pass", "no document is declared to supersede it"))
    return out


def _support(
    part: ClaimPart, source: ClaimSource, doc: EvidenceDocument, texts: Sequence[str]
) -> list[Check]:
    out: list[Check] = []
    text = texts[source.page - 1]
    rows = rows_on(texts, part.benefit, source.page)
    loc = _loc(doc, source.page)
    if not rows:
        return [_check("row_found", "fail", f"no {part.benefit.value} row on the page", loc)]
    if len(rows) > 1:
        why = f"{len(rows)} {part.benefit.value} rows on the cited page; a person must pick"
        return [_check("row_found", "unknown", why, loc)]
    row = rows[0]
    loc = _loc(doc, source.page, row.line)
    out.append(_check("row_found", "pass", "one row found", loc))
    if source.quote is not None:
        q = norm(source.quote)
        covers = row.line in q or (q in row.line and _AMOUNT.search(q) is not None)
        why = "the quote contains the row" if covers else "the quote is not the row that is checked"
        out.append(_check("quote_covers_row", "pass" if covers else "fail", why))
    reading = read_row(row, part)
    grammar = reading.grammar_problem
    out.append(_check("row_in_grammar", "fail" if grammar else "pass", grammar or "one value"))
    if part.network == "out_of_network":
        why = "the rules read in-network rows only; an out-of-network claim needs a person"
        out.append(_check("network_matches", "unknown", why))
    else:
        out.append(_check("network_matches", "pass", "an in-network claim; rows read in-network"))
    if extra := page_qualifiers(text, row) + carried_qualifier(texts, source.page):
        why = f"qualifying wording elsewhere on the page: {extra[:3]}"
        out.append(_check("page_has_no_qualifiers", "unknown", why))
    else:
        out.append(_check("page_has_no_qualifiers", "pass", "no qualifying wording on the page"))
    if part.value is None:
        out.append(_check("value_matches", "unknown", "the claim names no typed value"))
    elif reading.parsed is not None and not grammar:
        outcome, why = compare(part, reading.parsed)
        out.append(_check("value_matches", outcome, why))
    missing = [c for c in part.conditions if residue(c) not in residue(row.cell)]
    if part.conditions:
        why = f"not in the row: {missing}" if missing else "every stated condition is in the row"
        out.append(_check("conditions_present", "fail" if missing else "pass", why))
    return out


def _resolve(
    source: ClaimSource, corpus: Corpus
) -> tuple[EvidenceDocument | None, str | None, list[Check]]:
    doc = corpus.documents.get(source.document_id)
    if doc is None:
        why = f"{source.document_id} is not a document of this run"
        return None, None, [_check("source_resolves", "fail", why)]
    out = [_check("source_resolves", "pass", "the document is in the run")]
    if not doc.readable:
        out.append(_check("hash_matches", "fail", doc.problem or "unreadable"))
        return doc, None, out
    if source.sha256 is not None and source.sha256 != doc.sha256:
        out.append(_check("hash_matches", "fail", "the claim cites different bytes than the run"))
        return doc, None, out
    out.append(_check("hash_matches", "pass", "bytes match the run's SHA-256"))
    text = corpus.page_text(doc.document_id, source.page)
    if text is None:
        why = f"page {source.page} does not exist; the document has {doc.page_count}"
        out.append(_check("page_in_range", "fail", why))
        return doc, None, out
    out.append(_check("page_in_range", "pass", f"page {source.page} exists"))
    if source.quote is not None:
        found = norm(source.quote) in norm(text)
        why = "the quote is on the cited page" if found else "the quote is not on the cited page"
        out.append(_check("quote_on_page", "pass" if found else "fail", why))
    return doc, text, out


# Which verdict a failed check means, in precedence order for one cited source. Location and
# context failures come first: a contradiction read from the wrong place or version means nothing.
_FAIL: tuple[tuple[frozenset[CheckName], Verdict], ...] = (
    (frozenset({"source_resolves", "hash_matches"}), V.UNVERIFIABLE),
    (
        frozenset({"plan_year_matches", "plan_pages", "effective_date_applies", "not_superseded"}),
        V.INAPPLICABLE_VERSION,
    ),
    (
        frozenset({"page_in_range", "quote_on_page", "row_found", "quote_covers_row"}),
        V.INSUFFICIENT_EVIDENCE,
    ),
    (frozenset({"row_in_grammar"}), V.NEEDS_HUMAN_REVIEW),
    (frozenset({"value_matches"}), V.CONTRADICTED),
    (frozenset({"conditions_present"}), V.INSUFFICIENT_EVIDENCE),
)
# Unknown effective dates are kept apart from other unknowns: they block a positive finding
# (supported or contradicted) under policy 2, but never turn missing evidence into a maybe.
_DATES: frozenset[CheckName] = frozenset({"effective_date_applies"})


def source_verdict(checks: Iterable[Check], policy: Policy) -> Verdict:
    checks = list(checks)
    failed = {c.name for c in checks if c.outcome == "fail"}
    unknown = {c.name for c in checks if c.outcome == "unknown"}
    dates_unknown = bool(unknown & _DATES) and policy.unknown_dates_block and policy.unknown_blocks
    unknown -= _DATES
    for names, verdict in _FAIL:
        if failed & names:
            # A contradiction or a missing condition read in an unclear context (another
            # network, qualifying wording) is not a finding the rules can stand behind.
            late = names in (_FAIL[-2][0], _FAIL[-1][0])
            if late and unknown and policy.unknown_blocks:
                return V.NEEDS_HUMAN_REVIEW
            if verdict is V.CONTRADICTED and dates_unknown:
                return V.NEEDS_HUMAN_REVIEW  # a different value from a version that may not apply
            return verdict
    if (unknown and policy.unknown_blocks) or dates_unknown:
        return V.NEEDS_HUMAN_REVIEW
    return V.SUPPORTED


def _check_source(
    claim: Claim, part: ClaimPart, source: ClaimSource, corpus: Corpus, policy: Policy
) -> list[Check]:
    doc, text, checks = _resolve(source, corpus)
    if doc is None or text is None:
        return checks
    if not policy.require_support:  # baseline: a resolving citation is enough
        return [c for c in checks if c.name != "quote_on_page"]
    checks += _context(claim, doc, corpus, policy, source.page)
    checks += _support(part, source, doc, corpus.pages[doc.sha256])
    return checks


@dataclass(frozen=True)
class OtherEvidence:
    contrary: list[Contrary]  # applicable rows or CMS values that read differently
    agreeing: list[Location]  # applicable rows nobody cited that state exactly the claim
    unclear: list[Contrary]  # rows that read differently where applicability or wording is unclear


def other_evidence(
    claim: Claim,
    part: ClaimPart,
    corpus: Corpus,
    checked: set[tuple[str, int]],
    policy: Policy,
) -> OtherEvidence:
    """Every row for the same benefit that no cited source decided, judged by the same
    applicability checks as a cited source (plan, year, booklet pages, ANOC, effective dates,
    supersession), plus the CMS disagreements the run already recorded. Never reparses CMS files.

    A row from another plan, year, or booklet's pages is left out. A row in a version that dates
    or supersession exclude is kept but dismissed. A clean row in an applicable document that
    states another value is live contrary evidence; one that states the claim is agreeing. Every
    other row is unclear: a different value where applicability is unknown (an unknown plan, an
    ANOC, unclear booklet pages), qualifying wording on its page or carried from an earlier one,
    a row outside the grammar, or a unit that is not comparable. Unclear evidence cannot make a
    conflict, but it blocks support. Qualifying wording blocks even when the amount matches (a
    matching amount does not cancel a restriction); a plain match in a document that may not
    apply is simply left out.
    """
    out = OtherEvidence([], [], [])
    for doc in corpus.documents.values():
        if not doc.readable:
            continue
        texts = corpus.pages[doc.sha256]
        for page, text in enumerate(texts, start=1):
            if (doc.document_id, page) in checked:
                continue
            rows = rows_on(texts, part.benefit, page)
            if not rows:
                continue
            context = _context(claim, doc, corpus, policy, page)
            failed = {c.name: c.reason for c in context if c.outcome == "fail"}
            if failed.keys() & {"plan_year_matches", "plan_pages"}:
                continue  # another plan, year, or booklet section: not evidence for this claim
            soft = (
                frozenset() if policy.unknown_dates_block else _DATES
            )  # policy 1: dates never block
            unknown = [c for c in context if c.outcome == "unknown" and c.name not in soft]
            dismissed = failed.get("not_superseded") or failed.get("effective_date_applies")
            carried = carried_qualifier(texts, page)
            for row in rows:
                reading = read_row(row, part)
                if reading.parsed is None:
                    continue  # no value on the line: a heading, not evidence either way
                loc = _loc(doc, page, row.line)
                applies = [c.reason for c in unknown]  # is the document for this claim at all?
                wording = page_qualifiers(text, row)[:1] + carried  # does wording narrow it?
                if reading.grammar_problem:
                    wording.append(reading.grammar_problem)
                outcome, said = "unknown", "the claim names no typed value"
                if part.value is not None and not reading.grammar_problem:
                    outcome, said = compare(part, reading.parsed)
                why = f"reads {_show(reading.parsed.value, reading.parsed.unit)}"
                if dismissed is not None:
                    if outcome != "pass":
                        out.contrary.append(Contrary(location=loc, reason=why, dismissed=dismissed))
                elif outcome == "pass" and not wording:
                    if not applies:  # a match in a document that may not apply says nothing
                        out.agreeing.append(loc)
                elif outcome == "fail" and not wording and not applies:
                    out.contrary.append(Contrary(location=loc, reason=why))
                else:
                    why = f"{why}; a person must judge it: {(wording + applies + [said])[0]}"
                    out.unclear.append(Contrary(location=loc, reason=why))
    for c in corpus.cms_conflicts:
        if (c.plan_id, c.year, c.field) == (claim.plan_id, claim.year, part.benefit):
            out.contrary.append(_cms(c))
    return out


def _cms(c: CmsConflict) -> Contrary:
    loc = Location(kind="cms_row", document_id=c.file, page=c.row, row=c.reason[:300])
    return Contrary(location=loc, reason=f"the run recorded a CMS mismatch: {c.reason}")


# Claim-level precedence when parts disagree: the most decision-relevant problem first.
# Support needs every part supported; one contradicted part contradicts the whole claim.
CLAIM_ORDER: tuple[Verdict, ...] = (
    V.CONTRADICTED,
    V.CONFLICTING_EVIDENCE,
    V.INAPPLICABLE_VERSION,
    V.UNVERIFIABLE,
    V.INSUFFICIENT_EVIDENCE,
    V.NEEDS_HUMAN_REVIEW,
    V.SUPPORTED,
)
# Among cited sources that neither support nor contradict a part, the one closest to support.
_SOURCE_ORDER: tuple[Verdict, ...] = (
    V.NEEDS_HUMAN_REVIEW,
    V.INAPPLICABLE_VERSION,
    V.INSUFFICIENT_EVIDENCE,
    V.UNVERIFIABLE,
)


_HEADLINE: dict[Verdict, str] = {
    V.NEEDS_HUMAN_REVIEW: "the cited evidence may support the part, but only a person can tell",
    V.INAPPLICABLE_VERSION: "the cited evidence is for another plan, year, booklet, or version",
    V.INSUFFICIENT_EVIDENCE: "the cited location does not hold evidence for the part",
    V.UNVERIFIABLE: "the cited source cannot be checked",
}


def _decide(verdicts: list[Verdict], other: OtherEvidence, policy: Policy) -> tuple[Verdict, str]:
    live = [c for c in other.contrary if c.dismissed is None]
    if V.SUPPORTED in verdicts and (V.CONTRADICTED in verdicts or live):
        return V.CONFLICTING_EVIDENCE, (
            "a cited row supports the part, but other applicable evidence reads differently and "
            "no explicit metadata says which controls"
        )
    if V.SUPPORTED in verdicts and other.unclear and policy.unknown_blocks:
        return V.NEEDS_HUMAN_REVIEW, (
            "a cited row supports the part, but another row for it is unclear (its applicability, "
            "its wording, or its unit); only a person can tell"
        )
    if V.SUPPORTED in verdicts:
        return V.SUPPORTED, "a cited row states exactly the claimed value in an applicable document"
    if V.CONTRADICTED in verdicts and other.agreeing:
        return V.CONFLICTING_EVIDENCE, (
            "the cited row reads differently, but another applicable row states the claim; "
            "no explicit metadata says which controls"
        )
    if V.CONTRADICTED in verdicts:
        return V.CONTRADICTED, "the cited row in an applicable document states a different value"
    for verdict in _SOURCE_ORDER:
        if verdict in verdicts:
            return verdict, _HEADLINE[verdict]
    return V.INSUFFICIENT_EVIDENCE, "the claim cites no evidence for this part"


def audit_part(claim: Claim, part: ClaimPart, corpus: Corpus, policy: Policy) -> PartResult:
    part_checks = [text_check(claim, part)] if policy.require_support else []
    results = []
    for i, source in enumerate(claim.sources):
        if source.parts and part.part_id not in source.parts:
            continue
        checks = _check_source(claim, part, source, corpus, policy)
        verdict = source_verdict(checks, policy)
        results.append(SourceResult(source_index=i, verdict=verdict, checks=tuple(checks)))
    # A cited page counts as decided only when its row's value decided the source's verdict. A
    # citation that failed for another reason (a fabricated quote, say) leaves its page to the
    # search for other evidence, so a bad citation can never hide a real contradiction.
    checked = {
        (claim.sources[r.source_index].document_id, claim.sources[r.source_index].page)
        for r in results
        if r.verdict in (V.SUPPORTED, V.CONTRADICTED)
    }
    other = OtherEvidence([], [], [])
    if policy.check_contrary and policy.require_support and part.value is not None:
        other = other_evidence(claim, part, corpus, checked, policy)
    verdict, headline = _decide([r.verdict for r in results], other, policy)
    blocked = [c for c in part_checks if c.outcome == "unknown"]
    if verdict is V.SUPPORTED and blocked and policy.unknown_blocks:
        verdict, headline = V.NEEDS_HUMAN_REVIEW, "the claim's text says more than its typed part"
    reasons = [headline]
    reasons += [c.reason for c in blocked]
    for r in results:
        bad = [c for c in r.checks if c.outcome in ("fail", "unknown")]
        reasons += [f"source {r.source_index + 1}: {c.reason}" for c in bad]
    for c in [*other.contrary, *other.unclear]:
        if c.dismissed is None:
            where = "row" if c.location.kind == "cms_row" else "page"
            reasons.append(
                f"other evidence {c.location.document_id} {where} {c.location.page}: {c.reason}"
            )
    unknowns = {c.reason for r in results for c in r.checks if c.outcome == "unknown"}
    unknowns |= {c.reason for c in blocked}
    return PartResult(
        part_id=part.part_id,
        checks=tuple(part_checks),
        verdict=verdict,
        reasons=tuple(dict.fromkeys(reasons)),
        sources=tuple(results),
        contrary=(*other.contrary, *other.unclear),
        unknowns=tuple(sorted(unknowns)),
    )


def audit_claim(claim: Claim, corpus: Corpus, policy: Policy) -> ClaimAudit:
    parts = [audit_part(claim, p, corpus, policy) for p in claim.parts]
    verdicts = {p.verdict for p in parts}
    verdict = next(v for v in CLAIM_ORDER if v in verdicts)
    reasons = [f"{p.part_id}: {p.verdict.value}" for p in parts] if len(parts) > 1 else []
    reasons += [r for p in parts for r in p.reasons]
    unknown = sorted({u for p in parts for u in p.unknowns})
    uncertainty = "Deterministic rules only; the model lane was not run."
    if unknown:
        uncertainty += " Unknown: " + "; ".join(unknown) + "."
    return ClaimAudit(
        claim=claim,
        verdict=verdict,
        reasons=tuple(dict.fromkeys(reasons)),
        parts=tuple(parts),
        uncertainty=uncertainty,
    )
