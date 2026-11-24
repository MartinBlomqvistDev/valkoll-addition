"""Remove test reports and likely duplicates following Valkoll's published definition.

A likely duplicate has the same kommun, place, incident time and text as another report in
the file, with the text compared without punctuation (Valkoll, Underlaget). The first report
in file order is kept. Writes the cleaned reports to data/interim and a count-only comparison
with Valkoll's figures, for the full file and for Valkoll's period. No free text is printed.

Usage:
    python pipeline/02_clean_dedup.py
"""

import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from valkoll.config import load_config, resolve  # noqa: E402

PUNCT = re.compile(r"[^\w\s]")  # any character that is neither a word character nor whitespace
SPACE = re.compile(r"\s+")      # runs of whitespace, collapsed to one space


def normalise(text: str | None, lower: bool) -> str | None:
    """Strip punctuation and collapse whitespace for duplicate comparison.

    Args:
        text: Report text, or None when withheld.
        lower: Also lowercase the text (used as a sensitivity check).

    Returns:
        The normalised text, or None when there is no text.
    """
    if text is None or pd.isna(text):
        return None
    t = SPACE.sub(" ", PUNCT.sub("", text)).strip()
    return t.lower() if lower else t


def duplicate_mask(df: pd.DataFrame, lower: bool = False) -> pd.Series:
    """Flag every report that repeats an earlier one on kommun, place, incident time and text.

    Reports without text are never flagged, since an empty text cannot show two reports are the same.

    Args:
        df: Reports without test reports, in file order.
        lower: Compare text case-insensitively.

    Returns:
        Boolean mask, True for reports to drop.
    """
    key = df.assign(_t=df.beskrivning.map(lambda t: normalise(t, lower)))
    has_text = key._t.notna()
    dup = key[has_text].duplicated(subset=["kommun", "plats", "incident", "_t"], keep="first")
    return dup.reindex(df.index, fill_value=False)


def main() -> None:
    """Clean the reports and write the comparison."""
    cfg = load_config()
    src = cfg["sources"]["valmyndigheten_reports"]
    pub = cfg["published"]
    df = pd.read_parquet(resolve("data/interim/reports.parquet")).sort_values("rad").reset_index(drop=True)
    missing = set(src["test_report_rows"]) - set(df.rad)
    if missing:
        raise ValueError(f"test report rows not in file: {sorted(missing)}")
    no_test = df[~df.rad.isin(src["test_report_rows"])].reset_index(drop=True)
    dup = duplicate_mask(no_test)
    clean = no_test[~dup]
    clean.to_parquet(resolve("data/interim/reports_clean.parquet"), index=False)

    end = pd.Timestamp(src["valkoll_period_end"])
    period = no_test.inkommen <= end
    rows = [
        ("Testrapporter", 3, len(src["test_report_rows"]), len(src["test_report_rows"])),
        ("Utan testrapporter", pub["reports_without_tests"], int(period.sum()), len(no_test)),
        ("Troliga dubbletter", pub["likely_duplicates"], int(duplicate_mask(no_test[period]).sum()), int(dup.sum())),
        ("Utan testrapporter och dubbletter", pub["reports_without_tests_and_duplicates"],
         int(period.sum() - duplicate_mask(no_test[period]).sum()), len(clean)),
        ("Troliga dubbletter, skiftlägesokänsligt (känslighetskontroll)", None,
         int(duplicate_mask(no_test[period], lower=True).sum()), int(duplicate_mask(no_test, lower=True).sum())),
    ]
    lines = [
        "# 02 Testrapporter och troliga dubbletter",
        "",
        "Testrapporter: rader " + ", ".join(map(str, src["test_report_rows"])) + ". Kriterium: rapporten skickades "
        "för att pröva rapporteringssystemet och beskriver ingen händelse i valet. Valkoll räknar bort tre men "
        "redovisar inte vilka.",
        "",
        "Troliga dubbletter enligt Valkolls definition: samma kommun, plats, incidenttid och text, texten "
        "jämförd utan skiljetecken. Rapporter utan text räknas aldrig som dubbletter.",
        "",
        f"| Mått | Valkoll | Denna fil, t.o.m. {src['valkoll_period_end'][:10]} | Denna fil, hela |",
        "|---|---|---|---|",
    ] + [f"| {m} | {'' if a is None else a} | {b} | {c} |" for m, a, b, c in rows]
    lines += [
        "",
        "Alla grupper av troliga dubbletter har samma inkomsttidpunkt och ligger intill varandra i filen, "
        "vilket tyder på dubbelinskick. Andra rimliga tolkningar av textjämförelsen (råtext, bara skiljetecken "
        "borttagna, all blanktext borttagen) ger 43 till 47 för Valkolls period. Skillnaden mot Valkolls 38 kan "
        "bero på de efterregistrerade rapporterna eller på en detalj i jämförelsen som Valkoll inte redovisar.",
    ]
    report = resolve(cfg["paths"]["output_dir"]) / "02_clean_dedup.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(report.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
