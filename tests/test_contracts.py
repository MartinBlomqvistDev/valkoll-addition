"""Data contracts fail loudly on rows that cannot be right."""

from datetime import datetime

import pytest
from pydantic import ValidationError

from valkoll.contracts import EligibleVotersKommun, IncidentReport, KommunReportRate


def kommun(**overrides) -> dict:
    row = {"kod": "1780", "namn": "Karlstad", "rapporter": 50, "rostberattigade": 70_000,
           "per_10k_published": 7.14}
    return row | overrides


def test_kommun_rate_accepts_consistent_row():
    assert KommunReportRate(**kommun()).per_10k_published == 7.14


def test_kommun_rate_rejects_rate_that_does_not_follow_from_counts():
    with pytest.raises(ValidationError, match="recomputed"):
        KommunReportRate(**kommun(per_10k_published=7.20))


def test_kommun_rate_tolerates_rounding_to_two_decimals():
    # 1 / 3 * 10 000 = 3333.33..., printed as 3333.33
    KommunReportRate(**kommun(rapporter=1, rostberattigade=3, per_10k_published=3333.33))


def test_kommun_rate_allows_zero_reports():
    KommunReportRate(**kommun(rapporter=0, per_10k_published=0.0))


@pytest.mark.parametrize("kod", ["178", "17800", "17a0", ""])
def test_kommun_rate_rejects_malformed_code(kod):
    with pytest.raises(ValidationError):
        KommunReportRate(**kommun(kod=kod))


def test_kommun_rate_rejects_zero_electorate():
    with pytest.raises(ValidationError):
        KommunReportRate(**kommun(rostberattigade=0))


def test_kommun_rate_rejects_unknown_field():
    with pytest.raises(ValidationError):
        KommunReportRate(**kommun(extra=1))


def test_kommun_rate_is_immutable():
    row = KommunReportRate(**kommun())
    with pytest.raises(ValidationError):
        row.rapporter = 51


def test_eligible_voters_rejects_more_votes_than_voters():
    with pytest.raises(ValidationError, match="eligible"):
        EligibleVotersKommun(kod="0114", namn="Upplands Väsby", rostberattigade=100, roster=101)


def test_eligible_voters_accepts_full_turnout():
    EligibleVotersKommun(kod="0114", namn="Upplands Väsby", rostberattigade=100, roster=100)


def report(**overrides) -> dict:
    row = {"rad": 4, "inkommen": datetime(2026, 9, 13, 20, 5), "incident": None,
           "representerar": "Valkansli", "lan": None, "kommun": None, "plats": None,
           "kategori": None, "underkategori": None, "lansstyrelse": None,
           "beskrivning": None, "sekretess": False}
    return row | overrides


def test_incident_report_accepts_minimal_row():
    assert IncidentReport(**report()).rad == 4


def test_incident_report_rejects_unknown_reporter():
    with pytest.raises(ValidationError):
        IncidentReport(**report(representerar="Väljare"))


def test_incident_report_rejects_row_above_first_data_row():
    with pytest.raises(ValidationError):
        IncidentReport(**report(rad=3))
