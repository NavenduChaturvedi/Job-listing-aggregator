"""CSV and JSON writers.

CSV is for spreadsheets (tags flattened to a "; "-joined string); JSON keeps
``tags`` as a real list and is pretty-printed for diff-friendly output.
"""

from __future__ import annotations

import json
import os

import pandas as pd


def write_csv(df: pd.DataFrame, path: str) -> str:
    out = df.copy()
    out["tags"] = out["tags"].apply(
        lambda t: "; ".join(t) if isinstance(t, list) else (t or "")
    )
    _ensure_parent(path)
    out.to_csv(path, index=False)
    return path


def write_json(df: pd.DataFrame, path: str) -> str:
    # pandas stores missing values as NaN; json.dump would emit invalid `NaN`.
    safe = df.astype(object).where(pd.notna(df), None)
    records = safe.to_dict(orient="records")
    for row in records:
        if not isinstance(row.get("tags"), list):
            row["tags"] = [] if row.get("tags") in (None, "") else [row["tags"]]
    _ensure_parent(path)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(records, fh, indent=2, ensure_ascii=False)
    return path


def _ensure_parent(path: str) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
