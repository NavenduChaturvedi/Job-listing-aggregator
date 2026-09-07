"""Job Listing Aggregator.

Scrapes job listings from a few scraping-friendly remote-work sources,
normalises them into one shape, removes duplicates, filters by keyword /
location, and exports clean CSV + JSON.

Modules, by responsibility:

    config      - tunable settings (delays, timeouts) with env overrides
    models      - the Job dataclass and the text/URL/date normalisers
    http        - polite fetching: robots.txt, crawl-delay, retry/back-off
    sources/    - one small adapter per site (RemoteOK, WeWorkRemotely, python.org)
    pipeline    - dataframe assembly, filtering, deduplication, stats
    export      - CSV / JSON writers
"""

__version__ = "1.0.0"
