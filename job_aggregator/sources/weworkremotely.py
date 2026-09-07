"""We Work Remotely adapter.

WeWorkRemotely offers RSS feeds (allowed by robots.txt, and the polite way to
consume a site that publishes one). We read the site-wide feed and parse it
with BeautifulSoup's XML mode.

Feed quirks handled here:
  * ``<title>`` is "Company: Role" - split on the first ": "
  * the useful location lives in ``<region>``
  * ``<pubDate>`` is RFC-822
"""

from __future__ import annotations

from bs4 import BeautifulSoup

from ..models import Job, clean_text, parse_date
from .base import Source

FEED_URL = "https://weworkremotely.com/remote-jobs.rss"


class WeWorkRemotelySource(Source):
    name = "weworkremotely"
    label = "We Work Remotely"

    def fetch(self, fetcher, keyword=None, location=None) -> list[Job]:
        xml = fetcher.get_text(FEED_URL)
        soup = BeautifulSoup(xml, "xml")

        jobs: list[Job] = []
        for item in soup.find_all("item"):
            raw_title = _text(item, "title")
            company, title = _split_company_title(raw_title)

            link = _text(item, "link") or _text(item, "guid")
            region = _text(item, "region") or "Remote"
            category = _text(item, "category")

            jobs.append(
                Job(
                    source=self.name,
                    title=title,
                    company=company,
                    location=region,
                    url=link,
                    posted_date=parse_date(_text(item, "pubDate")),
                    tags=[category] if category else [],
                    description=clean_text(_text(item, "description"), limit=300),
                )
            )
        return jobs


def _text(item, tag: str) -> str:
    el = item.find(tag)
    return el.get_text(strip=True) if el else ""


def _split_company_title(raw: str) -> tuple[str, str]:
    """ "Lemon.io: Senior Java & React Developer" -> ("Lemon.io", "Senior ...").

    Falls back to ("", raw) when there is no colon.
    """
    if ": " in raw:
        company, title = raw.split(": ", 1)
        return company.strip(), title.strip()
    return "", raw.strip()
