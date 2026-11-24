"""Reporting-rate analysis per kommun.

Asks whether the spread in reports per 10 000 eligible voters across kommuner
is larger than chance would give under one common national rate, and replaces
the raw rates with shrinkage estimates that account for small denominators.

Steps:
    1. Reproduce Valkoll's published kommun figures and write a diff.
    2. Poisson homogeneity test (Pearson dispersion statistic).
    3. Funnel plot with exact Poisson control limits around the national rate.
    4. Negative binomial models with log(eligible voters) as offset; the second
       adds log(eligible voters) as a covariate to test whether rate depends on size.
    5. Empirical Bayes gamma-Poisson shrinkage per kommun.

Usage:
    python pipeline/08_reporting_rate_model.py
"""

import argparse
import math
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import statsmodels.api as sm  # noqa: E402
from scipy import stats  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from valkoll.config import load_config, resolve  # noqa: E402


def reproduce(df: pd.DataFrame, pub: dict, per: int) -> pd.DataFrame:
    """Recompute every published kommun-level figure and compare."""
    rate = df.rapporter / df.rostberattigade * per
    large = df[df.rostberattigade >= pub["large_kommun_min_voters"]]
    large_rate = large.rapporter / large.rostberattigade * per
    top = df.loc[rate.idxmax()]
    low = large.loc[large_rate.idxmin()]

    rows = [
        ("Reports with kommun", pub["kommun_reports_total"], int(df.rapporter.sum())),
        ("Eligible voters", pub["eligible_voters_total"], int(df.rostberattigade.sum())),
        ("National rate per 10k", pub["national_rate_per_10k"],
         round(df.rapporter.sum() / df.rostberattigade.sum() * per, 2)),
        ("Kommuner without report", pub["kommuner_without_report"], int((df.rapporter == 0).sum())),
        (f"Highest rate ({pub['highest_rate']['name']})", pub["highest_rate"]["rate"],
         f"{top.namn} {round(rate.max(), 2)}"),
        (f"Lowest large ({pub['lowest_large_rate']['name']})", pub["lowest_large_rate"]["rate"],
         f"{low.namn} {round(large_rate.min(), 2)}"),
    ]
    lower = 0.0
    for upper, expected in pub["rate_bins"].items():
        hi = math.inf if upper == "inf" else float(upper)
        n = int(((rate > 0) & (rate >= lower) & (rate < hi)).sum())
        rows.append((f"Kommuner with rate in [{lower:g}, {hi:g})", expected, n))
        lower = hi
    out = pd.DataFrame(rows, columns=["figure", "published", "reproduced"])
    out["match"] = [str(p) in str(r) or p == r for p, r in zip(out.published, out.reproduced)]
    return out


def poisson_limits(expected: np.ndarray, coverage: float) -> tuple[np.ndarray, np.ndarray]:
    """Exact Poisson control limits on counts for given expected counts."""
    tail = (1 - coverage) / 2
    lo = stats.poisson.ppf(tail, expected)
    hi = stats.poisson.ppf(1 - tail, expected)
    return lo, hi


def funnel(df: pd.DataFrame, national: float, limits: list[float], per: int, path: Path) -> dict:
    """Draw the funnel plot and count kommuner outside each limit."""
    expected = df.rostberattigade.to_numpy() * national
    counts = {}
    for cov in limits:
        lo, hi = poisson_limits(expected, cov)
        y = df.rapporter.to_numpy()
        counts[cov] = {
            "above": int((y > hi).sum()),
            "below": int((y < lo).sum()),
            "expected_outside_by_chance": round(len(df) * (1 - cov), 1),
        }

    grid = np.logspace(np.log10(df.rostberattigade.min() * 0.9),
                       np.log10(df.rostberattigade.max() * 1.1), 400)
    fig, ax = plt.subplots(figsize=(9, 6))
    rate = df.rapporter / df.rostberattigade * per
    ax.scatter(df.rostberattigade, rate, s=12, color="#333", alpha=0.7, zorder=3)
    for cov, style in zip(limits, ["--", ":"]):
        lo, hi = poisson_limits(grid * national, cov)
        ax.plot(grid, lo / grid * per, style, color="#c0392b", lw=1)
        ax.plot(grid, hi / grid * per, style, color="#c0392b", lw=1,
                label=f"{cov * 100:.1f} %-gräns (Poisson)".replace(".", ","))
    ax.axhline(national * per, color="#2c3e50", lw=1,
               label=f"Riket {national * per:.2f}".replace(".", ","))
    for _, r in df.assign(rate=rate).nlargest(5, "rate").iterrows():
        ax.annotate(r.namn, (r.rostberattigade, r.rate), fontsize=7, xytext=(3, 3),
                    textcoords="offset points")
    lowest = df.assign(rate=rate).query("rostberattigade >= 100000").nsmallest(3, "rate")
    # Stagger offsets so neighbouring low labels (Norrköping, Västerås) do not overlap
    for offset, (_, r) in zip([(3, -9), (3, -18), (3, -9)], lowest.iterrows()):
        ax.annotate(r.namn, (r.rostberattigade, r.rate), fontsize=7, xytext=offset,
                    textcoords="offset points")
    ax.set_xscale("log")
    ax.set_xlabel("Röstberättigade (log)")
    ax.set_ylabel("Rapporter per 10 000 röstberättigade")
    ax.set_title("Rapporteringstakt per kommun mot kommunens storlek")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return counts


def negbin_models(df: pd.DataFrame) -> dict:
    """Fit Poisson and NB2 models with log(eligible voters) as offset."""
    y = df.rapporter.to_numpy()
    offset = np.log(df.rostberattigade.to_numpy())
    x0 = np.ones((len(df), 1))
    log_size = np.log(df.rostberattigade.to_numpy() / 10_000)
    x1 = sm.add_constant(log_size - log_size.mean())

    pois0 = sm.GLM(y, x0, family=sm.families.Poisson(), offset=offset).fit()
    nb0 = sm.NegativeBinomial(y, x0, offset=offset, loglike_method="nb2").fit(disp=0)
    nb1 = sm.NegativeBinomial(y, x1, offset=offset, loglike_method="nb2").fit(disp=0)

    lr = 2 * (nb0.llf - pois0.llf)
    # alpha = 0 lies on the boundary, so the LR statistic is a 50:50 mixture of chi2(0) and chi2(1).
    p_alpha = 0.5 * stats.chi2.sf(lr, 1)
    beta = nb1.params[1]
    ci = nb1.conf_int()[1]
    return {
        "pearson_dispersion": float(pois0.pearson_chi2 / pois0.df_resid),
        "pearson_chi2": float(pois0.pearson_chi2),
        "df": int(pois0.df_resid),
        "pearson_p": float(stats.chi2.sf(pois0.pearson_chi2, pois0.df_resid)),
        "nb0_alpha": float(nb0.params[-1]),
        "nb0_alpha_ci": tuple(float(v) for v in nb0.conf_int()[-1]),
        "lr_nb_vs_poisson": float(lr),
        "lr_p": float(p_alpha),
        "nb0_rate_per_10k": float(np.exp(nb0.params[0]) * 10_000),
        "nb1_size_elasticity": float(beta),
        "nb1_size_elasticity_ci": (float(ci[0]), float(ci[1])),
        "nb1_size_p": float(nb1.pvalues[1]),
        "nb1_alpha": float(nb1.params[-1]),
        "aic_nb0": float(nb0.aic),
        "aic_nb1": float(nb1.aic),
        "nb0": nb0,
    }


def shrink(df: pd.DataFrame, rate: float, alpha: float, per: int) -> pd.DataFrame:
    """Gamma-Poisson empirical Bayes estimates of each kommun's reporting rate.

    The NB2 fit implies kommun rates theta_i ~ Gamma(shape=1/alpha, mean=rate).
    With y_i ~ Poisson(theta_i * N_i) the posterior is
    Gamma(shape=1/alpha + y_i, rate=1/(alpha*rate) + N_i).
    """
    shape0 = 1 / alpha
    rate0 = shape0 / rate
    post_shape = shape0 + df.rapporter
    post_rate = rate0 + df.rostberattigade
    out = df[["kod", "namn", "rapporter", "rostberattigade"]].copy()
    out["raw_per_10k"] = df.rapporter / df.rostberattigade * per
    out["eb_per_10k"] = post_shape / post_rate * per
    out["eb_lo95"] = stats.gamma.ppf(0.025, post_shape, scale=1 / post_rate) * per
    out["eb_hi95"] = stats.gamma.ppf(0.975, post_shape, scale=1 / post_rate) * per
    out["raw_rank"] = out.raw_per_10k.rank(ascending=False, method="min").astype(int)
    out["eb_rank"] = out.eb_per_10k.rank(ascending=False, method="min").astype(int)
    return out.sort_values("eb_per_10k", ascending=False)


def size_bands(df: pd.DataFrame, per: int) -> pd.DataFrame:
    """Pooled rate per size quintile of eligible voters."""
    q = pd.qcut(df.rostberattigade, 5)
    g = df.groupby(q, observed=True).agg(
        kommuner=("namn", "size"),
        rapporter=("rapporter", "sum"),
        rostberattigade=("rostberattigade", "sum"),
        utan_rapport=("rapporter", lambda s: int((s == 0).sum())),
    )
    g["per_10k"] = (g.rapporter / g.rostberattigade * per).round(2)
    g.index = [f"{int(i.left):,}–{int(i.right):,}".replace(",", " ") for i in g.index]
    return g


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.parse_args()
    cfg = load_config()
    per = cfg["reporting_rate"]["per"]
    out_dir = resolve(cfg["paths"]["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    df = pd.read_parquet(resolve(cfg["paths"]["processed_dir"]) / "kommun_report_rates.parquet")

    national = df.rapporter.sum() / df.rostberattigade.sum()
    repro = reproduce(df, cfg["published"], per)
    fun = funnel(df, national, cfg["reporting_rate"]["funnel_limits"], per,
                 out_dir / "08_funnel.png")
    nb = negbin_models(df)
    eb = shrink(df, national, nb["nb0_alpha"], per)
    eb_excl = eb[(eb.eb_lo95 > national * per) | (eb.eb_hi95 < national * per)]
    bands = size_bands(df, per)
    eb.to_csv(out_dir / "08_kommun_shrinkage.csv", index=False, float_format="%.3f")

    lines = ["# 08 Rapporteringstakt per kommun", ""]
    lines += ["Källa: Valkolls publicerade kommuntabell (290 kommuner), hämtad "
              "från valkoll.com/incidentrapporter.", ""]
    lines += ["## 1. Reproduktion av publicerade tal", "", repro.to_markdown(index=False), ""]
    lines += ["## 2. Är spridningen större än slumpen?", ""]
    lines += [f"- Pearson-dispersion under gemensam rikstakt: {nb['pearson_dispersion']:.2f} "
              f"(1 vid ren Poisson), chi2 = {nb['pearson_chi2']:.0f} på {nb['df']} fg, "
              f"p = {nb['pearson_p']:.1e}."]
    for cov, c in fun.items():
        lines.append(f"- Utanför {cov:.1%}-gränsen: {c['above']} över, {c['below']} under "
                     f"(väntat av slumpen: cirka {c['expected_outside_by_chance']}).")
    lines += [f"- Negativ binomial, alfa = {nb['nb0_alpha']:.3f} "
              f"(95 % KI {nb['nb0_alpha_ci'][0]:.3f} till {nb['nb0_alpha_ci'][1]:.3f}); "
              f"LR mot Poisson = {nb['lr_nb_vs_poisson']:.0f}, p = {nb['lr_p']:.1e}.",
              f"- Det motsvarar en variationskoefficient mellan kommuner på cirka "
              f"{math.sqrt(nb['nb0_alpha']):.0%} i den underliggande takten.", ""]
    lines += ["## 3. Beror takten på kommunens storlek?", ""]
    lo, hi = nb["nb1_size_elasticity_ci"]
    lines += [f"- Elasticitet för takt mot röstberättigade: {nb['nb1_size_elasticity']:.3f} "
              f"(95 % KI {lo:.3f} till {hi:.3f}, p = {nb['nb1_size_p']:.1e}). "
              f"Negativt värde: större kommuner rapporterar färre per röstberättigad.",
              f"- AIC utan storlek {nb['aic_nb0']:.1f}, med storlek {nb['aic_nb1']:.1f}.",
              "", bands.to_markdown(), ""]
    lines += ["## 4. Shrinkage-skattningar (empirisk Bayes, gamma-Poisson)", ""]
    lines += [f"- {len(eb_excl)} av 290 kommuner har ett 95 %-intervall som inte omfattar "
              f"rikstakten {national * per:.2f}.", ""]
    cols = ["namn", "rapporter", "rostberattigade", "raw_per_10k", "raw_rank",
            "eb_per_10k", "eb_lo95", "eb_hi95", "eb_rank"]
    lines += ["Högst efter shrinkage:", "", eb[cols].head(10).round(2).to_markdown(index=False), ""]
    lines += ["Lägst efter shrinkage:", "", eb[cols].tail(10).round(2).to_markdown(index=False), ""]
    zero = eb[eb.rapporter == 0].sort_values("rostberattigade", ascending=False)
    lines += ["Största kommunerna utan rapport:", "",
              zero[cols].head(8).round(2).to_markdown(index=False), ""]

    report = out_dir / "08_reporting_rate.md"
    report.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
