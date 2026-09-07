"""CSV and JSON serialisation.

CSV is for spreadsheets (tags flattened to a "; "-joined string); JSON keeps
``tags`` as a real list and is pretty-printed for diff-friendly output.

The ``*_bytes`` functions do the formatting; ``write_*`` just save them to a
path. The web dashboard uses the ``*_bytes`` forms directly.
"""

from __future__ import annotations

import json
import os

import pandas as pd


def csv_bytes(df: pd.DataFrame) -> bytes:
    out = df.copy()
    out["tags"] = out["tags"].apply(lambda t: "; ".join(t) if isinstance(t, list) else (t or ""))
    return out.to_csv(index=False).encode("utf-8")


def json_bytes(df: pd.DataFrame) -> bytes:
    # pandas stores missing values as NaN; json.dump would emit invalid `NaN`.
    safe = df.astype(object).where(pd.notna(df), None)
    records = safe.to_dict(orient="records")
    for row in records:
        if not isinstance(row.get("tags"), list):
            row["tags"] = [] if row.get("tags") in (None, "") else [row["tags"]]
    return json.dumps(records, indent=2, ensure_ascii=False).encode("utf-8")


def write_csv(df: pd.DataFrame, path: str) -> str:
    _ensure_parent(path)
    with open(path, "wb") as fh:
        fh.write(csv_bytes(df))
    return path


def write_json(df: pd.DataFrame, path: str) -> str:
    _ensure_parent(path)
    with open(path, "wb") as fh:
        fh.write(json_bytes(df))
    return path


def _ensure_parent(path: str) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
