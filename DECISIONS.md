# Design decisions

Why the aggregator is built the way it is. The code shows *what*; this file is
the *why*, and the main thing to study later.

---

## 1. Sources: RemoteOK, We Work Remotely, python.org/jobs

**Decision:** aggregate these three, not LinkedIn / Indeed / Glassdoor.

**Why:**

- **They can actually be scraped, repeatably.** LinkedIn and Indeed rate-limit
  and block fast; the brief says so, and it is right. A portfolio piece has to
  keep working for whoever clones it.
- **Deliberate variety of formats**, to show the tool is a real framework and
  not one hard-coded parser:
  | Source | Format | What it demonstrates |
  |---|---|---|
  | RemoteOK | JSON API (`/api`) | consuming a documented feed |
  | We Work Remotely | RSS / XML | parsing a markup feed with BeautifulSoup |
  | python.org/jobs | server-rendered HTML | a genuine CSS-selector scrape |
- All three are **allowed by robots.txt** and need **no account**.
- Each keeps the fields the brief asks for: title, company, location, link,
  posted date.

**Consequence / how to extend:** a new board is one file in
`job_aggregator/sources/` implementing `fetch(fetcher, keyword, location) ->
list[Job]`, plus one line in `sources/__init__.py:REGISTRY`. The pipeline,
CLI, dedup and export never change.

**Attribution:** RemoteOK's and WWR's terms ask that re-published listings link
back and name the source. Every exported row keeps the original `url` and a
`source` column, which honours that. This tool is built for personal job
searching, not for re-publishing a competing board.

---

## 2. `requests` + `BeautifulSoup`, no Selenium

**Decision:** static fetching only.

**Why:** every source serves the data we need without running JavaScript - a
JSON endpoint, an RSS feed, and a server-rendered page. A headless browser
would add hundreds of MB, a browser binary, and a lot of flakiness for zero
benefit. `lxml` is the parser backend (fast, tolerant, and handles both the
HTML and the XML feed).

---

## 3. One normalised `Job` record

**Decision:** every source returns `Job` dataclass instances
(`job_aggregator/models.py`); nothing downstream knows which site a row came
from except via the `source` field.

**Why:** dedup, filtering and export only have to understand one shape. The
messy, site-specific work (an RSS `<title>` that packs "Company: Role" into one
string, python.org putting the company in a bare text node after a `<br/>`,
RemoteOK's HTML-in-JSON descriptions) is contained in each adapter and never
leaks out.

Shared normalisers live in `models.py`:
- `clean_text` runs everything through BeautifulSoup to strip tags and collapse
  whitespace, so a plain-text field and an HTML field come out the same.
- `parse_date` accepts both ISO-8601 (RemoteOK, python.org `<time>`) and
  RFC-822 (RSS `<pubDate>`) and always returns `YYYY-MM-DD` or `None`. A
  missing date must never break a run.

---

## 4. pandas for the pipeline

**Decision:** assemble the listings into a DataFrame and do filtering, dedup and
export with pandas.

**Why:** dedup, keyword/location filtering, sorting and CSV/JSON writing are
exactly what a DataFrame is good at. The alternative - hand-rolled loops and
`csv`/`json` modules - would be longer and buggier. The brief also asks for
pandas specifically.

---

## 5. De-duplication: URL first, then title + company

**Decision:** drop rows with a duplicate normalised URL, then rows with a
duplicate `(title, company)` key. Report how many were removed.

**Why:**

- **Normalised URL** (`models.normalize_url`) is the strong signal: lowercase
  host, no query/fragment, no trailing slash, `http` == `https`. This catches
  the same posting fetched twice.
- **title + company**, loosely normalised (lowercased, non-alphanumerics
  stripped), catches the *same job cross-posted to two boards* under different
  URLs - which URL-only dedup would miss. "Senior Python Dev" at "Acme" and
  "senior python dev" at "ACME!" collapse to one.
- Order matters: URL dedup is exact and safe, so it runs first; the fuzzier
  identity dedup runs on what is left.

---

## 6. Keyword filter matches title + company + description — not tags

**Decision:** a keyword's terms must all appear in title + company +
description. Tags are exported but not searched.

**Why:** RemoteOK attaches a huge, only-loosely-related tag list to every
posting (a business-development role tagged `python`, `react`, `golang`, …). If
tags were in the searchable text, `--keyword python` would match almost
everything from that source. Title and the description snippet are the honest
signal. This trades a little recall for a lot of precision.

**Location filter:** plain case-insensitive substring, except that "remote"
also matches "anywhere", "worldwide", "distributed", "global", and blank
locations (a blank location on a remote board means remote).

---

## 7. Politeness: shared fetcher, robots.txt, crawl-delay, back-off

**Decision:** one `Fetcher` instance per run (`job_aggregator/http.py`), shared
by every source, enforcing:
- robots.txt checked and cached per host;
- a site's declared `Crawl-delay` honoured when longer than our 2 s default;
- ≥ 2 s between *any* two requests (a single global clock, not per-host);
- retry on 429 / 5xx / connection errors with exponential back-off that
  respects `Retry-After`.

**Why a custom robots fetch:** `urllib.robotparser` fetches robots.txt with its
own `python-urllib` User-Agent, which Cloudflare-fronted sites (We Work
Remotely) answer with `403` - and the stdlib then treats that as "disallow
everything", silently killing the source. So `Fetcher` fetches robots.txt with
*our* session and applies RFC 9309 rules: `2xx` parse, `4xx` (except 429) means
"no restrictions", `5xx` means back off. Network failure reading robots.txt
fails open (crawl), matching mainstream crawler behaviour.

---

## 8. Error handling: one bad source never kills the run

**Decision:** each source is run inside `try/except` in
`job_aggregator/runner.py`. A `FetchError` (or anything unexpected) is recorded
in `RunStats.errors`, printed, and the run continues with the other sources.
The exit code is non-zero only if *every* source failed.

**Why:** an aggregator's value is resilience. "We Work Remotely is down today"
should still give you RemoteOK and python.org results, with a clear note about
what failed - not a stack trace and no output. "Zero listings matched" is a
normal outcome, not an error.

---

## 9. CLI shape

**Decision:** `python aggregator.py --keyword "..." --location "..."` with
optional `--source` (repeatable), `--max-age-days`, `--limit`, `--output-dir`,
`--csv`, `--json`, `--no-export`, `--print`. `aggregator.py` only parses args
and calls `runner.run_cli`.

**Why:** matches the brief's interface exactly, and keeps the entry point
trivial so all logic stays in the testable package.

---

## 10. Tests use saved fixtures, never the network

**Decision:** `tests/` feeds each adapter a small saved fixture
(`tests/fixtures/`) through a fake fetcher, and tests the pipeline on
constructed `Job` objects.

**Why:** the suite must pass offline and deterministically - a test that hits
live job boards would be slow and would break whenever a listing rolls off the
feed. The fixtures are trimmed real payloads, so they still catch the fiddly
bits (the RSS "Company: Role" split, python.org's company-after-`<br/>`,
skipping RemoteOK's legal-notice element, `http`/`https` dedup).

---

## 11. The web dashboard is an optional, logic-free layer

**Decision:** `webapp/` is a small Flask app in its own optional dependency
(`requirements-web.txt`). It calls `runner.aggregate()` and renders the result;
the CSV / JSON buttons use the same `export` functions as the CLI.

**Why:**

- The scraper stays a dependency-light CLI; Flask is only pulled in if you want
  the UI.
- No logic in `webapp/` means the dashboard and the CLI can't diverge, and the
  existing pipeline tests still cover everything that matters.
- One extra touch the CLI doesn't need: results are cached in-process for a few
  minutes, keyed by the query, so clicking "Download CSV" right after a search
  serves the already-scraped data instead of hitting all three boards again.
- Server-rendered Jinja + plain CSS, no JS framework - enough for a local tool.
