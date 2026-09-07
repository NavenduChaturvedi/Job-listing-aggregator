"""Optional local web dashboard for the job aggregator.

A thin Flask layer over ``job_aggregator.runner`` - it adds no scraping or
filtering logic of its own, it just renders an ``aggregate()`` result and
offers the same CSV / JSON as downloads.

Run it with:  python -m webapp   (from the repo root)
"""
