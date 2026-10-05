"""PR 15: multi-plan booklets. Some carriers print one Summary of Benefits for several plans; each
plan's pages name its id (or its name) in the page header. Extraction must read only the
requested plan's pages, so a value from a neighbouring plan can never be cited as this plan's.

Rule: a page that names exactly one plan belongs to that plan, and so do the pages after it until
another plan is named. A page that names two or more plans (a contents or comparison page)
belongs to nobody. A document that names no plan but the requested one is not a booklet.
The requested plan's pages must be one unbroken range, else the document goes to review.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass

from plan_diff import config
from plan_diff.models import normalize_plan_id

_PLAN_ID = re.compile(config.PLAN_ID_PATTERN)


@dataclass(frozen=True)
class PageRange:
    first: int  # 1-based, inclusive
    last: int

    def __str__(self) -> str:
        return f"{self.first} to {self.last}"


@dataclass(frozen=True)
class BookletResult:
    """`pages` is None for a document that is not a booklet (read every page)."""

    plan_id: str
    pages: PageRange | None
    problem: str | None = None  # set when the plan's pages cannot be told apart: send to review
    others: tuple[str, ...] = ()  # the other plans named in the document


def plans_named(text: str, plan_id: str | None = None, plan_name: str | None = None) -> set[str]:
    """Every plan id on a page, through the one id rule. With `plan_name`, a page that prints the
    requested plan's name counts as naming `plan_id` too."""
    found = {normalize_plan_id(m.group(1)) for m in _PLAN_ID.finditer(text)}
    if plan_id and plan_name and plan_name.casefold() in " ".join(text.split()).casefold():
        found.add(plan_id)
    return found


def plan_pages(
    page_texts: Sequence[str], plan_id: str, plan_name: str | None = None
) -> BookletResult:
    """Which pages of a document describe `plan_id` (module docstring has the rule)."""
    named = [plans_named(text, plan_id, plan_name) for text in page_texts]
    others = sorted(set().union(*named) - {plan_id}) if named else []
    if not others:
        return BookletResult(plan_id, None)
    owner: list[str | None] = []
    current: str | None = None
    for ids in named:
        if len(ids) == 1:
            current = next(iter(ids))
        elif len(ids) > 1:
            current = None
        owner.append(current)
    mine = [page for page, who in enumerate(owner, start=1) if who == plan_id]
    if not mine:
        why = f"multi-plan booklet ({', '.join(others)}): no page belongs to {plan_id} alone"
        return BookletResult(plan_id, None, why, tuple(others))
    if mine != list(range(mine[0], mine[-1] + 1)):
        why = f"multi-plan booklet: {plan_id} pages are not one range ({mine})"
        return BookletResult(plan_id, None, why, tuple(others))
    return BookletResult(plan_id, PageRange(mine[0], mine[-1]), None, tuple(others))


def mask_pages(page_texts: Sequence[str], pages: PageRange | None) -> list[str]:
    """Blank every page outside the range, so page numbers (and citations) stay the real ones."""
    if pages is None:
        return list(page_texts)
    return [
        text if pages.first <= number <= pages.last else ""
        for number, text in enumerate(page_texts, start=1)
    ]
