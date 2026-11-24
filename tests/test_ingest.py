"""Steps 00 and 01: parsing Valkoll's table, hash checks and reading Valmyndigheten's files.

Every input here is synthetic. The real incident file holds free text and is never used in tests.
"""

import hashlib

import pandas as pd
import pytest
from pydantic import ValidationError

ROW = '<tr data-k="{kod}"><th>{namn}</th><td>{n}</td><td>{voters}</td><td>{rate}</td></tr>'


def table(*rows: str) -> str:
    header = "<tr><th>Kommun</th><th>Rapporter</th><th>Röstberättigade</th><th>Per 10 000</th></tr>"
    return f"<html><body><table>{header}{''.join(rows)}</table></body></html>"


@pytest.mark.parametrize("text, value", [
    ("8\xa0051\xa0355", 8_051_355), ("78,33", 78.33), ("0,25", 0.25), ("12 345", 12_345), ("0", 0),
])
def test_to_number_reads_swedish_formatting(step, text, value):
    assert step("00_fetch_valkoll_kommun_table").to_number(text) == value


def test_parse_reads_rows_with_kommun_code_only(step):
    html = table(
        ROW.format(kod="1762", namn="Munkfors", n="21", voters="2\xa0681", rate="78,33"),
        ROW.format(kod="1980", namn="Västerås", n="3", voters="121\xa0802", rate="0,25"),
    )
    rows = step("00_fetch_valkoll_kommun_table").parse(html)
    assert [(r.kod, r.namn, r.rapporter, r.rostberattigade) for r in rows] == [
        ("1762", "Munkfors", 21, 2681), ("1980", "Västerås", 3, 121_802)]


def test_parse_fails_on_inconsistent_published_rate(step):
    html = table(ROW.format(kod="1762", namn="Munkfors", n="21", voters="2\xa0681", rate="80,00"))
    with pytest.raises(ValidationError):
        step("00_fetch_valkoll_kommun_table").parse(html)


@pytest.mark.parametrize("module", ["01_ingest_reports", "01_ingest_eligible_voters"])
def test_sha256_matches_hashlib(step, tmp_path, module):
    path = tmp_path / "file.bin"
    data = b"x" * (3 << 20)  # larger than one read chunk
    path.write_bytes(data)
    assert step(module).sha256(path) == hashlib.sha256(data).hexdigest()


def test_read_reports_numbers_rows_as_excel_does(step, tmp_path):
    mod = step("01_ingest_reports")
    path = tmp_path / "reports.xlsx"
    pd.DataFrame(columns=list(mod.COLUMNS), data=[
        {"Datum inkommen rapport": "2026-09-13 20:05", "Representerar": "Valkansli",
         "Kommun/utlandsmyndighet": "Munkfors", "Beskrivning": "syntetisk text"},
        {"Datum inkommen rapport": "2026-09-14 08:00", "Datum incident": "2026-09-13 19:00",
         "Representerar": "Röstmottagning", "Sekretess": "Ja"},
    ]).to_excel(path, index=False, startrow=2)
    df = mod.read_reports(path, header_row=2)
    assert df.rad.tolist() == [4, 5]
    assert df.sekretess.tolist() == [False, True]
    assert pd.isna(df.kommun.iloc[1]) and pd.isna(df.incident.iloc[0])


def test_read_reports_rejects_changed_schema(step, tmp_path):
    path = tmp_path / "reports.xlsx"
    pd.DataFrame({"Datum": ["2026-09-13"]}).to_excel(path, index=False, startrow=2)
    with pytest.raises(ValueError, match="unexpected columns"):
        step("01_ingest_reports").read_reports(path, header_row=2)


def test_read_eligible_voters_requires_all_290_kommuner(step, tmp_path):
    path = tmp_path / "votes.xlsx"
    pd.DataFrame({"Kommunkod": ["0114", "0115"], "Kommunnamn": ["Upplands Väsby", "Vallentuna"],
                  "Röstberättigade": [35_000, 25_000], "Röster": [30_000, 22_000]}).to_excel(
        path, sheet_name="Valdeltagande_kommun", index=False)
    with pytest.raises(ValueError, match="290"):
        step("01_ingest_eligible_voters").read_eligible_voters(path, "Valdeltagande_kommun")


def test_compare_eligible_voters_flags_differences_and_missing(step):
    valkoll = pd.DataFrame({"kod": ["0114", "0115"], "namn": ["A", "B"], "rostberattigade": [100, 200]})
    valmyndigheten = pd.DataFrame({"kod": ["0114", "0117"], "namn": ["A", "C"], "rostberattigade": [101, 300]})
    merged = step("01_ingest_eligible_voters").compare(valkoll, valmyndigheten).set_index("kod")
    assert merged.loc["0114", "diff"] == -1
    assert merged.loc["0115", "_merge"] == "left_only"
    assert merged.loc["0117", "_merge"] == "right_only"
