"""The config holds what the pipeline steps assume about it."""

import string

from valkoll.config import load_config


def test_hashes_are_full_sha256():
    sources = load_config()["sources"]
    for key in ("valse_riksdag_votes", "valmyndigheten_reports"):
        digest = sources[key]["sha256"]
        assert len(digest) == 64 and set(digest) <= set(string.hexdigits.lower())


def test_test_report_rows_are_unique_data_rows():
    rows = load_config()["sources"]["valmyndigheten_reports"]["test_report_rows"]
    assert len(rows) == len(set(rows)) and min(rows) >= 4


def test_published_bins_add_up_to_290_kommuner():
    pub = load_config()["published"]
    with_reports = sum(pub["rate_bins"].values())
    assert with_reports == 263 and with_reports + pub["kommuner_without_report"] == 290
