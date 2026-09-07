"""python.org/jobs adapter.

This is the "real" static-HTML scrape in the project: no API, no feed, just a
server-rendered page parsed with BeautifulSoup. robots.txt allows /jobs/.

Markup (one listing):

    <li>
      <h2 class="listing-company">
        <span class="listing-company-name">
          <a href="/jobs/8131/">Senior Python Developer</a><br/> Adzuna
        </span>
        <span class="listing-location"><a ...>Remote, Remote</a></span>
      </h2>
      <span class="listing-posted">Posted: <time datetime="2026-09-03T...">...</time></span>
    </li>
"""

from __future__ import annotations

from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..models import Job, clean_text, parse_date
from .base import Source

JOBS_URL = "https://www.python.org/jobs/"


class PythonOrgSource(Source):
    name = "pythonorg"
    label = "python.org jobs"

    def fetch(self, fetcher, keyword=None, location=None) -> list[Job]:
        html = fetcher.get_text(JOBS_URL)
        soup = BeautifulSoup(html, "lxml")

        jobs: list[Job] = []
        for li in soup.select("ol.list-recent-jobs > li"):
            name_span = li.select_one("span.listing-company-name")
            if name_span is None:
                continue

            link = name_span.find("a")
            if link is None or not link.get("href"):
                continue

            title = link.get_text(strip=True)

            # Company is the bare text node after the <br/>. Remove the title
            # link and the "New" badge from a copy, keep the remaining text.
            name_copy = BeautifulSoup(str(name_span), "lxml")
            for junk in name_copy.select("a, span.listing-new"):
                junk.extract()
            company = clean_text(name_copy.get_text(" ", strip=True))

            location_el = li.select_one("span.listing-location")
            time_el = li.select_one("span.listing-posted time")
            job_types = [a.get_text(strip=True) for a in li.select("span.listing-job-type a")]

            jobs.append(
                Job(
                    source=self.name,
                    title=title,
                    company=company or "(not listed)",
                    location=clean_text(location_el.get_text()) if location_el else "",
                    url=urljoin(JOBS_URL, link["href"]),
                    posted_date=parse_date(time_el.get("datetime")) if time_el else None,
                    tags=job_types,
                    description="",
                )
            )
        return jobs
