"""Step 02: Valkoll's duplicate definition, applied to synthetic reports."""

import pandas as pd
import pytest

T = pd.Timestamp("2026-09-13 19:00")


@pytest.fixture
def dedup(step):
    return step("02_clean_dedup")


def reports(*rows: tuple) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["kommun", "plats", "incident", "beskrivning"])


@pytest.mark.parametrize("text, lower, expected", [
    ("Valsedlar saknades!", False, "Valsedlar saknades"),
    ("  Två   mellanslag,\n ny rad. ", False, "Två mellanslag ny rad"),
    ("Valsedlar SAKNADES", True, "valsedlar saknades"),
    (None, False, None),
    (float("nan"), False, None),
])
def test_normalise(dedup, text, lower, expected):
    assert dedup.normalise(text, lower) == expected


def test_keeps_first_and_flags_later_copies(dedup):
    df = reports(("Munkfors", "Lokal 1", T, "a"), ("Munkfors", "Lokal 1", T, "a"),
                 ("Munkfors", "Lokal 1", T, "a"))
    assert dedup.duplicate_mask(df).tolist() == [False, True, True]


def test_punctuation_and_spacing_do_not_separate_duplicates(dedup):
    df = reports(("Munkfors", "Lokal 1", T, "Valsedlar saknades."), ("Munkfors", "Lokal 1", T, "Valsedlar  saknades"))
    assert dedup.duplicate_mask(df).tolist() == [False, True]


@pytest.mark.parametrize("other", [
    ("Hagfors", "Lokal 1", T, "a"),
    ("Munkfors", "Lokal 2", T, "a"),
    ("Munkfors", "Lokal 1", T + pd.Timedelta(minutes=1), "a"),
    ("Munkfors", "Lokal 1", T, "b"),
])
def test_any_differing_key_field_means_not_duplicate(dedup, other):
    df = reports(("Munkfors", "Lokal 1", T, "a"), other)
    assert not dedup.duplicate_mask(df).any()


def test_reports_without_text_are_never_duplicates(dedup):
    df = reports(("Munkfors", "Lokal 1", T, None), ("Munkfors", "Lokal 1", T, None))
    assert not dedup.duplicate_mask(df).any()


def test_case_counts_unless_lower_is_set(dedup):
    df = reports(("Munkfors", "Lokal 1", T, "Valsedlar saknades"), ("Munkfors", "Lokal 1", T, "valsedlar saknades"))
    assert dedup.duplicate_mask(df).tolist() == [False, False]
    assert dedup.duplicate_mask(df, lower=True).tolist() == [False, True]


def test_missing_place_and_time_still_match(dedup):
    df = reports(("Munkfors", None, None, "a"), ("Munkfors", None, None, "a"))
    assert dedup.duplicate_mask(df).tolist() == [False, True]


def test_mask_aligns_with_input_index(dedup):
    df = reports(("Munkfors", "Lokal 1", T, None), ("Munkfors", "Lokal 1", T, "a"),
                 ("Munkfors", "Lokal 1", T, "a")).set_axis([10, 20, 30])
    mask = dedup.duplicate_mask(df)
    assert mask.index.tolist() == [10, 20, 30]
    assert mask.tolist() == [False, False, True]
