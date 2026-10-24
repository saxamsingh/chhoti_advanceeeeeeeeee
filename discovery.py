"""Scheme discovery: Search for new circulars, Fetch them, and write candidate scheme records.

A discovered scheme is written with `reviewed: false`, no eligibility rules and no benefit amount, because a
page title is not a reviewed fact. A person reads it, writes its rules and reviews it. Nothing discovered is
ever shown to a farmer by itself."""

from __future__ import annotations

import logging
import re
from datetime import date

from .config import Settings
from .parsers import parse_date
from .schemes import Scheme, SchemeSource, load_schemes, save_discovered
from .tinyfish import WebClient, WebClientError

log = logging.getLogger("khetkaaj.discovery")

QUERIES = (
    "new agriculture subsidy scheme notice for farmers {state}",
    "myscheme.gov.in agriculture scheme farmers {state}",
)
MAX_PAGES = 4
_DEADLINE = re.compile(
    r"(?:last date|deadline|closes? on|apply (?:by|before))[^.\n]{0,40}?(\d{1,2}[ -][A-Za-z]{3,9}[ ,-]*\d{4})",
    re.IGNORECASE,
)


def find_deadline(text: str) -> str | None:
    """An ISO date from phrases like 'last date 30 November 2026', or None. Never a guess."""
    m = _DEADLINE.search(text)
    parsed = parse_date(m.group(1)) if m else None
    return parsed.isoformat() if parsed else None


def _slug(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:48] or "scheme"


async def discover(web: WebClient, settings: Settings, today: date | None = None) -> list[Scheme]:
    """Write and return the newly found candidate schemes."""
    known_urls = {s.apply_url for s in load_schemes(settings)} | {
        src.url for s in load_schemes(settings) for src in s.sources
    }
    urls: list[str] = []
    for template in QUERIES:
        try:
            found = await web.search(template.format(state=settings.demo_state), purpose="Find scheme notices")
        except WebClientError as e:
            log.warning("scheme search failed: %s", e)
            continue
        for hit in found.results:
            if hit.url not in known_urls and hit.url not in urls:
                urls.append(hit.url)
    if not urls:
        return []
    try:
        pages = await web.fetch(urls[:MAX_PAGES], purpose="Scheme notice, eligibility and last date")
    except WebClientError as e:
        log.warning("scheme fetch failed: %s", e)
        return []

    created: list[Scheme] = []
    stamp = (today or date.today()).isoformat()
    for page in pages.results:
        if not page.text:
            continue
        title = (page.title or page.text.strip().splitlines()[0]).strip()[:120]
        scheme = Scheme(
            id=_slug(title),
            name=title,
            benefit=page.text.strip().replace("\n", " ")[:240],
            apply_url=page.final_url or page.url,
            deadline=find_deadline(page.text),
            notes="Discovered automatically. Eligibility rules and any benefit amount are not written yet.",
            sources=[SchemeSource(url=page.final_url or page.url, title=title, retrieved=stamp)],
            discovered=True,
        )
        if save_discovered(settings, scheme):
            created.append(scheme)
    return created
