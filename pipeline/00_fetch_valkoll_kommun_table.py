"""Fetch Valkoll's published per-kommun table and store it as validated parquet.

The page prints, for every kommun, the number of reports (excluding test reports
and likely duplicates), eligible voters and the rate per 10 000. This is the only
input step 08 needs, so the reporting-rate analysis can run before the
Valmyndigheten Excel file is available.

Usage:
    python pipeline/00_fetch_valkoll_kommun_table.py [--html data/raw/x.html]
"""

import argparse
import sys
from datetime import date
from html.parser import HTMLParser
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from valkoll.config import load_config, resolve  # noqa: E402
from valkoll.contracts import KommunReportRate  # noqa: E402


class KommunTableParser(HTMLParser):
    """Collect rows of the form <tr data-k="NNNN"><th>name</th><td>..</td>...</tr>."""

    def __init__(self) -> None:
        super().__init__()
        self.rows: list[dict] = []
        self._current: dict | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = dict(attrs)
        if tag == "tr" and attr.get("data-k"):
            self._current = {"kod": attr["data-k"], "cells": []}
        elif self._current is not None and tag in ("th", "td"):
            self._cell = []

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self._current is None:
            return
        if tag in ("th", "td") and self._cell is not None:
            self._current["cells"].append("".join(self._cell).strip())
            self._cell = None
        elif tag == "tr":
            self.rows.append(self._current)
            self._current = None


def to_number(text: str) -> float:
    """Parse Swedish number formatting ("8\xa0051", "78,33")."""
    return float(text.replace("\xa0", "").replace(" ", "").replace(",", "."))


def parse(html: str) -> list[KommunReportRate]:
    """Parse and validate every kommun row in the page."""
    parser = KommunTableParser()
    parser.feed(html)
    records = []
    for row in parser.rows:
        namn, rapporter, rostberattigade, rate = row["cells"]
        records.append(
            KommunReportRate(
                kod=row["kod"],
                namn=namn,
                rapporter=int(to_number(rapporter)),
                rostberattigade=int(to_number(rostberattigade)),
                per_10k_published=to_number(rate),
            )
        )
    return records


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--html", type=Path, help="Parse a saved snapshot instead of fetching.")
    args = ap.parse_args()
    cfg = load_config()
    raw_dir = resolve(cfg["paths"]["raw_dir"])
    raw_dir.mkdir(parents=True, exist_ok=True)

    if args.html:
        html = args.html.read_text(encoding="utf-8")
    else:
        resp = requests.get(cfg["sources"]["valkoll_incident_page"], timeout=30)
        resp.raise_for_status()
        resp.encoding = "utf-8"
        html = resp.text
        snapshot = raw_dir / f"valkoll_incidentrapporter_{date.today().isoformat()}.html"
        snapshot.write_text(html, encoding="utf-8")
        print(f"snapshot: {snapshot}")

    records = parse(html)
    df = pd.DataFrame([r.model_dump() for r in records])
    if df["kod"].duplicated().any():
        raise ValueError("duplicate kommun codes in table")
    if len(df) != 290:
        raise ValueError(f"expected 290 kommuner, parsed {len(df)}")

    out = resolve(cfg["paths"]["processed_dir"]) / "kommun_report_rates.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, index=False)
    print(f"{len(df)} kommuner, {df.rapporter.sum()} reports, "
          f"{df.rostberattigade.sum()} eligible voters -> {out}")


if __name__ == "__main__":
    main()
