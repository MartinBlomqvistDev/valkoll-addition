"""Exact binomial tests on the favoured/disadvantaged counts Valkoll publishes per party.

Tests each party's share of "favoured" among its favoured plus disadvantaged reports against
0.5, with a two-sided p-value and a Clopper-Pearson interval. Runs on the published counts;
report-level tests need Valkoll's classification.

Usage:
    python pipeline/05_tests_published.py
"""

import sys
from pathlib import Path

from scipy.stats import binomtest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from valkoll.config import load_config, resolve  # noqa: E402


def main() -> None:
    """Run the tests and write a Markdown table."""
    cfg = load_config()
    lines = [
        "# 05 Binomialtester på Valkolls publicerade tal",
        "",
        "Andel rapporter där partiet gynnats, av alla där det gynnats eller drabbats, prövat mot 0,5.",
        "",
        "| Parti | Gynnat | Drabbat | Andel gynnat | 95 % KI (Clopper-Pearson) | p (tvåsidigt) |",
        "|---|---|---|---|---|---|",
    ]
    for party, (fav, dis) in cfg["published"]["party_favoured_disadvantaged"].items():
        r = binomtest(fav, fav + dis, 0.5)
        ci = r.proportion_ci(method="exact")
        lines.append(f"| {party} | {fav} | {dis} | {fav / (fav + dis):.3f} | {ci.low:.3f} till {ci.high:.3f} | {r.pvalue:.2g} |")
    out = resolve(cfg["paths"]["output_dir"]) / "05_tests_published.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(out.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
