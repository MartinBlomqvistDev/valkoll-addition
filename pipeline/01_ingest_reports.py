"""Ingest Valmyndigheten's incident report file and compare its counts with Valkoll's.

Verifies the file hash, validates every row with Pydantic, writes the reports to
data/interim (never versioned, since the free text stays local) and writes a count-only
comparison with the figures Valkoll publishes. No free text is printed or written to outputs.

Usage:
    python pipeline/01_ingest_reports.py
"""

import hashlib
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from valkoll.config import load_config, resolve  # noqa: E402
from valkoll.contracts import IncidentReport  # noqa: E402

COLUMNS = {
    "Datum inkommen rapport": "inkommen", "Datum incident": "incident",
    "Representerar": "representerar", "Län": "lan", "Kommun/utlandsmyndighet": "kommun",
    "Plats": "plats", "Kategori": "kategori", "Underkategori": "underkategori",
    "Länsstyrelse": "lansstyrelse", "Beskrivning": "beskrivning", "Sekretess": "sekretess",
}


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


def none_if_nan(value: object) -> object:
    """Map pandas missing values to None."""
    return None if pd.isna(value) else value


def read_reports(path: Path, header_row: int) -> pd.DataFrame:
    """Read and validate every report.

    Args:
        path: Valmyndigheten's Excel file.
        header_row: Zero-based index of the header row.

    Returns:
        One validated row per report.

    Raises:
        ValueError: If the columns differ from the expected schema.
    """
    raw = pd.read_excel(path, header=header_row)
    if list(raw.columns) != list(COLUMNS):
        raise ValueError(f"unexpected columns: {list(raw.columns)}")
    raw = raw.rename(columns=COLUMNS)
    first_excel_row = header_row + 2  # header is Excel row header_row+1, first report the row after
    records = []
    for i, row in enumerate(raw.itertuples(index=False)):
        r = {k: none_if_nan(v) for k, v in row._asdict().items()}
        r["inkommen"] = pd.Timestamp(r["inkommen"]).to_pydatetime()
        r["incident"] = pd.Timestamp(r["incident"]).to_pydatetime() if r["incident"] is not None else None
        r["sekretess"] = r["sekretess"] is not None
        for k in ("lan", "kommun", "plats", "kategori", "underkategori", "lansstyrelse", "beskrivning"):
            r[k] = str(r[k]) if r[k] is not None else None
        records.append(IncidentReport(rad=first_excel_row + i, **r))
    return pd.DataFrame([r.model_dump() for r in records])


def compare(df: pd.DataFrame, published: dict, period_end: str) -> str:
    """Build a count-only comparison with Valkoll's published figures.

    Args:
        df: Validated reports.
        published: The published section of the config.
        period_end: Last receipt time covered by Valkoll's version of the file.

    Returns:
        The comparison as Markdown.
    """
    s = df[df.inkommen <= pd.Timestamp(period_end)]
    rows = [("Rapporter totalt (inkl. testrapporter)", published["reports_total"], len(s))]
    for k, v in published["reports_by_reporter"].items():
        rows.append((f"Rapportör: {k} (Valkoll utan testrapporter)", v, int((s.representerar == k).sum())))
    for k, v in published["reports_by_category"].items():
        rows.append((f"Kategori: {k} (Valkoll utan testrapporter)", v, int((s.kategori == k).sum())))
    rows.append(("Sekretessbelagda utan text", published["reports_secret"], int(s.sekretess.sum())))
    lines = [
        "# 01 Incidentrapporter: Valmyndighetens fil mot Valkolls tal",
        "",
        f"Filen innehåller {len(df)} rapporter, inkomna {df.inkommen.min():%Y-%m-%d} till {df.inkommen.max():%Y-%m-%d}. "
        f"Jämförelsen avser rapporter inkomna till och med {period_end[:10]}, samma period som Valkolls version.",
        "",
        "| Mått | Valkoll | Denna fil | Skillnad |",
        "|---|---|---|---|",
    ] + [f"| {m} | {a} | {b} | {b - a:+d} |" for m, a, b in rows]
    return "\n".join(lines) + "\n"


def main() -> None:
    """Run the ingest and the comparison."""
    cfg = load_config()
    src = cfg["sources"]["valmyndigheten_reports"]
    path = resolve(src["file"])
    if sha256(path) != src["sha256"]:
        raise ValueError(f"{path.name}: sha256 does not match config")
    df = read_reports(path, src["header_row"])
    interim = resolve("data/interim")
    interim.mkdir(parents=True, exist_ok=True)
    df.to_parquet(interim / "reports.parquet", index=False)
    report = resolve(cfg["paths"]["output_dir"]) / "01_reports_check.md"
    report.write_text(compare(df, cfg["published"], src["valkoll_period_end"]), encoding="utf-8")
    print(report.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
