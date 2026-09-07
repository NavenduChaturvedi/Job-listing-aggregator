#!/usr/bin/env python3
"""Job Listing Aggregator - command line entry point.

Examples
--------
    python aggregator.py --keyword "python developer" --location "remote"
    python aggregator.py -k "react" --source remoteok --source weworkremotely
    python aggregator.py -k data --max-age-days 14 --limit 50 --print
    python aggregator.py --output-dir out --csv jobs.csv --json jobs.json

This file only parses arguments and hands off to ``job_aggregator.runner``.
"""

from __future__ import annotations

import argparse
import sys

from job_aggregator import __version__
from job_aggregator.runner import run_cli
from job_aggregator.sources import REGISTRY


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aggregator.py",
        description="Scrape remote job boards, dedupe, and export clean CSV/JSON.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"job-aggregator {__version__}")

    parser.add_argument("-k", "--keyword", help="filter: term(s) that must appear in the listing")
    parser.add_argument(
        "-l", "--location", help='filter: location substring (e.g. "remote", "europe")'
    )
    parser.add_argument(
        "--source",
        action="append",
        choices=sorted(REGISTRY),
        help="restrict to this source (repeatable); default: all",
    )
    parser.add_argument(
        "--max-age-days", type=int, dest="max_age_days", help="drop listings older than N days"
    )
    parser.add_argument("--limit", type=int, help="keep at most N listings after dedup")

    parser.add_argument("--output-dir", default=".", help="directory for the export files")
    parser.add_argument("--csv", default="jobs.csv", help="CSV filename")
    parser.add_argument("--json", default="jobs.json", help="JSON filename")
    parser.add_argument("--no-export", action="store_true", help="do not write files, just report")
    parser.add_argument(
        "--print", dest="print_table", action="store_true", help="also print the listings"
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return run_cli(args)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\ninterrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
