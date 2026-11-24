"""Ingest eligible voters per kommun from Valmyndigheten and check Valkoll's table against them.

Reads the per-kommun turnout sheet of Valmyndigheten's final-count file for the
riksdag election 2026, verifies the file hash, validates every row with Pydantic
and compares eligible voters with the figures Valkoll publishes (step 00).
Differences are written to a report, not raised, so they stay documented.

Usage:
    python pipeline/01_ingest_eligible_voters.py [--xlsx path/to/file.xlsx]
"""

import argparse
import hashlib
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from valkoll.config import load_config, resolve  # noqa: E402
from valkoll.contracts import EligibleVotersKommun  # noqa: E402


def sha256(path: Path) -> str:
    """Return the hex SHA-256 digest of a file.

    Args:
        path: File to hash.

    Returns:
        The digest as a hex string.
    """
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_eligible_voters(path: Path, sheet: str) -> pd.DataFrame:
    """Read and validate eligible voters per kommun.

    Args:
        path: Valmyndigheten's final-count Excel file.
        sheet: Name of the per-kommun turnout sheet.

    Returns:
        One validated row per kommun.

    Raises:
        ValueError: If the sheet does not hold exactly 290 unique kommuner.
    """
    raw = pd.read_excel(path, sheet_name=sheet, dtype={"Kommunkod": str})
    records = [
        EligibleVotersKommun(
            kod=row.Kommunkod,
            namn=row.Kommunnamn,
            rostberattigade=int(row.Röstberättigade),
            roster=int(row.Röster),
        )
        for row in raw.itertuples(index=False)
    ]
    df = pd.DataFrame([r.model_dump() for r in records])
    if len(df) != 290 or df["kod"].duplicated().any():
        raise ValueError(f"expected 290 unique kommuner, got {len(df)}")
    return df


def compare(valkoll: pd.DataFrame, valmyndigheten: pd.DataFrame) -> pd.DataFrame:
    """Join Valkoll's and Valmyndigheten's eligible voters on kommun code.

    Args:
        valkoll: Output of step 00.
        valmyndigheten: Output of read_eligible_voters.

    Returns:
        One row per kommun present in either source, with the difference.
    """
    merged = valkoll[["kod", "namn", "rostberattigade"]].merge(
        valmyndigheten[["kod", "namn", "rostberattigade"]],
        on="kod", how="outer", suffixes=("_valkoll", "_valmyndigheten"), indicator=True,
    )
    merged["diff"] = merged.rostberattigade_valkoll - merged.rostberattigade_valmyndigheten
    return merged


def write_report(merged: pd.DataFrame, path: Path) -> None:
    """Write the comparison as a short Markdown report.

    Args:
        merged: Output of compare.
        path: Destination file.
    """
    only_one = merged[merged["_merge"] != "both"]
    differing = merged[(merged["_merge"] == "both") & (merged["diff"] != 0)]
    lines = [
        "# 01 Röstberättigade: Valkoll mot Valmyndigheten",
        "",
        "Källa: Valmyndighetens slutliga sammanräkning, riksdagsvalet 2026, fliken Valdeltagande_kommun.",
        "",
        f"- Kommuner i båda källorna: {int((merged['_merge'] == 'both').sum())}",
        f"- Kommuner bara i en källa: {len(only_one)}",
        f"- Kommuner med avvikande antal röstberättigade: {len(differing)}",
        f"- Summa Valkoll: {int(merged.rostberattigade_valkoll.sum())}",
        f"- Summa Valmyndigheten: {int(merged.rostberattigade_valmyndigheten.sum())}",
    ]
    if len(differing) or len(only_one):
        lines += ["", pd.concat([only_one, differing]).drop(columns="_merge").to_markdown(index=False)]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    """Run the ingest and comparison."""
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--xlsx", type=Path, help="Override the file path from config.yaml.")
    args = ap.parse_args()
    cfg = load_config()
    src = cfg["sources"]["valse_riksdag_votes"]
    path = args.xlsx or resolve(src["file"])
    if not path.exists():
        raise FileNotFoundError(f"{path} missing; download it from {cfg['sources']['valse_raw_page']}")
    digest = sha256(path)
    if digest != src["sha256"]:
        raise ValueError(f"{path.name}: sha256 {digest} does not match config")

    valmyndigheten = read_eligible_voters(path, src["sheet"])
    processed = resolve(cfg["paths"]["processed_dir"])
    valmyndigheten.to_parquet(processed / "eligible_voters_kommun.parquet", index=False)

    valkoll = pd.read_parquet(processed / "kommun_report_rates.parquet")
    merged = compare(valkoll, valmyndigheten)
    report = resolve(cfg["paths"]["output_dir"]) / "01_eligible_voters_check.md"
    write_report(merged, report)
    print(report.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
