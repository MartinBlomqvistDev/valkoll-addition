"""Draw a simplified reporting-rate figure for publication, in Valkoll's light and dark styles.

Same data as step 08, drawn for a general reader: one shaded band instead of two sets of
control limits, plain tick labels, a headline that states the finding and a source line.
Colours and typeface follow Valkoll's stylesheet (Inter, its light and dark tokens).

Usage:
    python pipeline/12_publication_figure.py
"""

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.ticker import FixedLocator, FuncFormatter, NullLocator  # noqa: E402
from scipy.stats import poisson  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from valkoll.config import load_config, resolve  # noqa: E402

THEMES = {
    "ljus": {"bg": "#f7f6f2", "fg": "#171717", "muted": "#61656d", "grid": "#e9e7e0",
             "band": "#3b6ea5", "out": "#3b6ea5", "ref": "#9a6b00", "band_alpha": 0.16},
    "mork": {"bg": "#0b0d12", "fg": "#eceef2", "muted": "#8f97a7", "grid": "#1c212b",
             "band": "#4a86c2", "out": "#4a86c2", "ref": "#b88a22", "band_alpha": 0.30},
}
# name -> text position in data coordinates (x, y), placed in empty space with a leader line
LABELLED = {"Munkfors": None, "Västerås": (160_000, 18), "Göteborg": (520_000, 18)}
TICKS = [2_000, 5_000, 10_000, 20_000, 50_000, 100_000, 200_000, 500_000]


def exact_limits(expected: np.ndarray, cov: float) -> tuple[np.ndarray, np.ndarray]:
    """Exact Poisson limits, as in step 08; used to colour the dots.

    Args:
        expected: Expected report counts under the national rate.
        cov: Coverage, e.g. 0.95.

    Returns:
        Lower and upper count limits.
    """
    a = (1 - cov) / 2
    return poisson.ppf(a, expected), poisson.ppf(1 - a, expected)


def smooth_quantile(q: float, expected: np.ndarray) -> np.ndarray:
    """Poisson quantile made continuous by interpolating the CDF between whole counts.

    Gives a smooth band that crosses each step of the exact limits, so no kommun ends up
    on the other side of the band from its colour (checked: same 149 kommuner outside).

    Args:
        q: Quantile, e.g. 0.025.
        expected: Expected report counts.

    Returns:
        Continuous quantile per expected value.
    """
    out = np.empty_like(expected, dtype=float)
    for i, m in enumerate(expected):
        k = np.arange(0, int(m * 1.5) + 50)
        c = poisson.cdf(k, m)
        j = int(np.searchsorted(c, q))
        c0 = c[j - 1] if j > 0 else 0.0
        out[i] = (k[j] - 1) + (q - c0) / (c[j] - c0)
    return np.clip(out, 0, None)


def thousands(x: float, _pos: int) -> str:
    """Format an axis value with a Swedish thousands separator."""
    return f"{int(x):,}".replace(",", " ")


def draw(df: pd.DataFrame, national: float, theme: dict, out: Path) -> None:
    """Draw and save one themed figure.

    Args:
        df: Kommun table with rapporter and rostberattigade.
        national: National reports per eligible voter.
        theme: Colour tokens.
        out: Output PNG path.
    """
    per = 10_000
    rate = df.rapporter / df.rostberattigade * per
    lo, hi = exact_limits(df.rostberattigade.to_numpy() * national, 0.95)
    outside = (df.rapporter < lo) | (df.rapporter > hi)
    grid = np.logspace(np.log10(df.rostberattigade.min() * 0.95), np.log10(df.rostberattigade.max() * 1.05), 2000)
    blo, bhi = smooth_quantile(0.025, grid * national), smooth_quantile(0.975, grid * national) + 1

    plt.rcParams.update({"font.family": "Inter", "font.size": 11, "text.color": theme["fg"],
                         "axes.labelcolor": theme["muted"], "xtick.color": theme["muted"],
                         "ytick.color": theme["muted"]})
    fig, ax = plt.subplots(figsize=(9, 6.2), dpi=200)
    fig.patch.set_facecolor(theme["bg"])
    ax.set_facecolor(theme["bg"])
    ax.fill_between(grid, blo / grid * per, bhi / grid * per, color=theme["band"], alpha=theme["band_alpha"], lw=0, zorder=1)
    ax.axhline(national * per, color=theme["ref"], lw=1.5, zorder=2)
    ax.scatter(df.rostberattigade[~outside], rate[~outside], s=22, color=theme["muted"], alpha=0.55,
               lw=0, zorder=3)
    ax.scatter(df.rostberattigade[outside], rate[outside], s=26, color=theme["out"], lw=0.8,
               edgecolor=theme["bg"], zorder=4)

    for name, pos in LABELLED.items():
        r = df[df.namn == name].iloc[0]
        xy = (r.rostberattigade, r.rapporter / r.rostberattigade * per)
        if pos is None:
            ax.annotate(name, xy, xytext=(6, 4), textcoords="offset points", fontsize=9.5, color=theme["fg"])
        else:
            ax.annotate(name, xy, xytext=pos, ha="center", fontsize=9.5, color=theme["fg"],
                        arrowprops={"arrowstyle": "-", "color": theme["muted"], "lw": 0.6, "shrinkB": 3})
    ax.annotate(f"Hela landet: {national * per:.1f}".replace(".", ","), (260_000, national * per),
                xytext=(0, 6), textcoords="offset points", ha="center", fontsize=9.5, color=theme["ref"])
    x_note = 2_300
    y_band = bhi[np.searchsorted(grid, x_note)] / x_note * per
    ax.annotate("Inom det skuggade fältet\nkan skillnaden vara slump", (x_note, y_band * 0.9), xytext=(x_note, 64),
                ha="left", fontsize=9.5, color=theme["band"],
                arrowprops={"arrowstyle": "-", "color": theme["band"], "lw": 0.8})

    ax.set_xscale("log")
    ax.xaxis.set_major_locator(FixedLocator(TICKS))
    ax.xaxis.set_minor_locator(NullLocator())
    ax.xaxis.set_major_formatter(FuncFormatter(thousands))
    ax.set_xlim(grid[0], grid[-1])
    ax.set_ylim(-2, max(rate) * 1.08)
    ax.set_xlabel("Antal röstberättigade i kommunen")
    ax.set_ylabel("Rapporter per 10 000 röstberättigade")
    ax.grid(axis="y", color=theme["grid"], lw=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(theme["grid"])
    ax.tick_params(length=0)

    n_out = int(outside.sum())
    fig.text(0.06, 0.965, "Kommunerna rapporterade i mycket olika takt", fontsize=15, weight="bold",
             color=theme["fg"], va="top")
    fig.text(0.06, 0.915, f"Varje prick är en kommun. {n_out} av {len(df)} ligger utanför det skuggade fältet "
             f"(blå). Om skillnaderna\nbara vore slump skulle det vara omkring {int(len(df) * 0.05 + 0.5)}.",
             fontsize=10.5, color=theme["muted"], va="top")
    fig.text(0.06, 0.02, "Källa: Valmyndighetens incidentrapporter och slutliga sammanräkning, valen 2026. "
             "Fältet är 95 % av utfallen vid samma takt i hela landet.", fontsize=8.5, color=theme["muted"])
    fig.subplots_adjust(left=0.09, right=0.97, top=0.82, bottom=0.13)
    fig.savefig(out, facecolor=theme["bg"])
    plt.close(fig)


def main() -> None:
    """Draw the light and dark versions."""
    cfg = load_config()
    df = pd.read_parquet(resolve(cfg["paths"]["processed_dir"]) / "kommun_report_rates.parquet")
    national = df.rapporter.sum() / df.rostberattigade.sum()
    for name, theme in THEMES.items():
        out = resolve(cfg["paths"]["output_dir"]) / f"12_rapporteringstakt_{name}.png"
        draw(df, national, theme, out)
        print(out)


if __name__ == "__main__":
    main()
