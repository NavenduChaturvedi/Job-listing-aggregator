"""RemoteOK adapter.

RemoteOK publishes a documented public JSON feed at https://remoteok.com/api
(allowed by their robots.txt; the AJAX ``?action=get_jobs`` endpoints are not).
The first array element is a legal/attribution notice, not a job - we skip it.

Notes / limitations:
  * The feed returns roughly the 100 most recent listings across all tags. There
    is no reliable server-side keyword filter - RemoteOK attaches a large, noisy
    tag list to every posting - so keyword matching is left to the central
    pipeline, which scores against title + company + description.
  * RemoteOK asks API users to link back to the listing URL and credit
    "RemoteOK" as the source. Keeping the ``url`` field and tagging every row
    ``source = remoteok`` satisfies that.
"""

from __future__ import annotations

from ..models import Job, clean_text, parse_date
from .base import Source

API_URL = "https://remoteok.com/api"


class RemoteOkSource(Source):
    name = "remoteok"
    label = "RemoteOK"

    def fetch(self, fetcher, keyword=None, location=None) -> list[Job]:
        payload = fetcher.get_json(API_URL)
        if not isinstance(payload, list):
            return []

        jobs: list[Job] = []
        for entry in payload:
            # skip the leading {"legal": ...} notice and malformed rows
            if not isinstance(entry, dict) or "position" not in entry:
                continue

            tags = [str(t) for t in entry.get("tags", []) if t]
            location_txt = (entry.get("location") or "").strip() or "Remote"

            # RemoteOK appends an anti-bot "Please mention the word X..." line to
            # every description - cut it off, it is not part of the posting.
            raw_desc = entry.get("description", "") or ""
            raw_desc = raw_desc.split("Please mention the word")[0]

            jobs.append(
                Job(
                    source=self.name,
                    title=(entry.get("position") or "").strip(),
                    company=(entry.get("company") or "").strip(),
                    location=location_txt,
                    url=(entry.get("url") or entry.get("apply_url") or "").strip(),
                    posted_date=parse_date(entry.get("date")),
                    tags=tags,
                    description=clean_text(raw_desc, limit=300),
                )
            )
        return jobs
