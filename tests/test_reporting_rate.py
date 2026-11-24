"""Step 08: the reporting-rate model on synthetic data, and the published figures on the committed table."""

import numpy as np
import pandas as pd
import pytest
from scipy.stats import binomtest

from valkoll.config import load_config, resolve


@pytest.fixture(scope="module")
def rr():
    from conftest import load_step
    return load_step("08_reporting_rate_model")


@pytest.fixture(scope="module")
def cfg():
    return load_config()


@pytest.fixture(scope="module")
def kommuner(cfg):
    return pd.read_parquet(resolve(cfg["paths"]["processed_dir"]) / "kommun_report_rates.parquet")


def synthetic(rate_per_voter: np.ndarray, voters: np.ndarray, seed: int = 0) -> pd.DataFrame:
    y = np.random.default_rng(seed).poisson(rate_per_voter * voters)
    return pd.DataFrame({"kod": [f"{i:04d}" for i in range(len(voters))],
                         "namn": [f"K{i}" for i in range(len(voters))],
                         "rapporter": y, "rostberattigade": voters})


def test_poisson_limits_widen_with_coverage(rr):
    expected = np.array([5.0, 50.0, 500.0])
    lo95, hi95 = rr.poisson_limits(expected, 0.95)
    lo998, hi998 = rr.poisson_limits(expected, 0.998)
    assert (lo998 <= lo95).all() and (hi998 >= hi95).all()
    assert (lo95 <= expected).all() and (hi95 >= expected).all()


# With no extra variation the NB dispersion sits at its boundary (alpha = 0), where the optimiser warns.
@pytest.mark.filterwarnings("ignore::statsmodels.tools.sm_exceptions.ConvergenceWarning")
def test_dispersion_near_one_when_every_kommun_shares_the_rate(rr):
    voters = np.random.default_rng(1).integers(3_000, 300_000, 290)
    nb = rr.negbin_models(synthetic(np.full(290, 6e-4), voters))
    assert 0.8 < nb["pearson_dispersion"] < 1.25
    lo, hi = nb["nb1_size_elasticity_ci"]
    assert lo < 0 < hi


def test_model_recovers_a_built_in_size_effect(rr):
    rng = np.random.default_rng(2)
    voters = rng.integers(3_000, 300_000, 290)
    rate = 6e-4 * (voters / voters.mean()) ** -0.3 * rng.gamma(20, 1 / 20, 290)
    nb = rr.negbin_models(synthetic(rate, voters, seed=3))
    lo, hi = nb["nb1_size_elasticity_ci"]
    assert lo < -0.3 < hi


def test_shrinkage_pulls_small_kommuner_hardest(rr):
    df = pd.DataFrame({"kod": ["0001", "0002", "0003"], "namn": ["liten", "stor", "noll"],
                       "rapporter": [10, 1_000, 0], "rostberattigade": [2_000, 200_000, 5_000]})
    national = 6e-4
    eb = rr.shrink(df, national, alpha=0.5, per=10_000).set_index("namn")
    # Both raw rates are 50 per 10k; the small kommun moves much further towards 6.
    assert eb.loc["liten", "raw_per_10k"] == pytest.approx(eb.loc["stor", "raw_per_10k"])
    assert 6 < eb.loc["liten", "eb_per_10k"] < eb.loc["stor", "eb_per_10k"] < 50
    # A kommun with no reports gets a positive estimate, not zero.
    assert 0 < eb.loc["noll", "eb_per_10k"] < 6
    assert (eb.eb_lo95 < eb.eb_per_10k).all() and (eb.eb_per_10k < eb.eb_hi95).all()


def test_committed_table_reproduces_every_published_figure(rr, cfg, kommuner):
    repro = rr.reproduce(kommuner, cfg["published"], cfg["reporting_rate"]["per"])
    assert repro.match.all(), repro[~repro.match]


def test_readme_figures_follow_from_the_committed_table(rr, cfg, kommuner, tmp_path):
    national = kommuner.rapporter.sum() / kommuner.rostberattigade.sum()
    outside = rr.funnel(kommuner, national, [0.95], 10_000, tmp_path / "funnel.png")[0.95]
    assert outside["above"] + outside["below"] == 149
    assert outside["expected_outside_by_chance"] == pytest.approx(14.5)

    nb = rr.negbin_models(kommuner)
    assert round(nb["pearson_dispersion"], 2) == 22.96
    lo, hi = nb["nb1_size_elasticity_ci"]
    assert (round(nb["nb1_size_elasticity"], 2), round(lo, 2), round(hi, 2)) == (-0.24, -0.35, -0.12)

    vasteras = kommuner.set_index("namn").loc["Västerås"]
    assert vasteras.rapporter == 3
    assert round(vasteras.rostberattigade * national) == 77


@pytest.mark.parametrize("party, share, ci, p", [
    ("V", 0.29, (0.23, 0.35), "4e-12"), ("SD", 0.54, (0.49, 0.58), "0.12")])
def test_readme_binomial_tests_follow_from_published_counts(cfg, party, share, ci, p):
    fav, dis = cfg["published"]["party_favoured_disadvantaged"][party]
    r = binomtest(fav, fav + dis, 0.5)
    low_high = r.proportion_ci(method="exact")
    assert round(fav / (fav + dis), 2) == share
    assert (round(low_high.low, 2), round(low_high.high, 2)) == ci
    assert f"{r.pvalue:.2g}" == p


def test_smooth_band_puts_every_kommun_on_the_same_side_as_the_exact_limits(kommuner):
    from valkoll.funnel import exact_limits, smooth_quantile
    national = kommuner.rapporter.sum() / kommuner.rostberattigade.sum()
    expected = kommuner.rostberattigade.to_numpy() * national
    lo, hi = exact_limits(expected, 0.95)
    exact_outside = (kommuner.rapporter < lo) | (kommuner.rapporter > hi)
    y = kommuner.rapporter.to_numpy()
    band_outside = (y < smooth_quantile(0.025, expected)) | (y > smooth_quantile(0.975, expected) + 1)
    assert (exact_outside.to_numpy() == band_outside).all()
    assert int(exact_outside.sum()) == 149
