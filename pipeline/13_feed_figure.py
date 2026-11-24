"""Draw the reporting-rate figure as a plain portrait chart for a social media feed.

Same data and band as step 12. Kommuner above the band and below it get separate colours,
since reporting more and reporting less than expected are different findings. 1080 x 1350 px.

Usage:
    python pipeline/13_feed_figure.py
"""

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.ticker import FixedLocator, FuncFormatter, NullLocator  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from valkoll.config import load_config, resolve  # noqa: E402
from valkoll.funnel import exact_limits, smooth_quantile, thousands  # noqa: E402

FONT = "Arial"
C = {"bg": "#ffffff", "fg": "#1a1a1a", "muted": "#666666", "grid": "#ececec", "band": "#e8e8e8",
     "inside": "#b0b0b0", "above": "#c8102e", "below": "#0b4f8a", "ref": "#1a1a1a"}
TICKS = [2_000, 5_000, 20_000, 100_000, 500_000]
PER = 10_000


def draw(df: pd.DataFrame, national: float, out: Path) -> None:
    """Draw and save the feed figure.

    Args:
        df: Valkoll's kommun table (step 00).
        national: National reports per eligible voter.
        out: Output PNG path.
    """
    rate = df.rapporter / df.rostberattigade * PER
    expected = df.rostberattigade.to_numpy() * national
    lo, hi = exact_limits(expected, 0.95)
    above, below = df.rapporter > hi, df.rapporter < lo
    grid = np.logspace(np.log10(df.rostberattigade.min() * 0.95), np.log10(df.rostberattigade.max() * 1.05), 2000)
    blo, bhi = smooth_quantile(0.025, grid * national), smooth_quantile(0.975, grid * national) + 1

    plt.rcParams.update({"font.family": FONT, "font.size": 12, "text.color": C["fg"],
                         "xtick.color": C["muted"], "ytick.color": C["muted"], "axes.labelcolor": C["muted"]})
    fig = plt.figure(figsize=(7.2, 9), dpi=150, facecolor=C["bg"])
    ax = fig.add_axes((0.11, 0.115, 0.85, 0.79), facecolor=C["bg"])

    ax.fill_between(grid, blo / grid * PER, bhi / grid * PER, color=C["band"], lw=0, zorder=1)
    ax.axhline(national * PER, color=C["ref"], lw=1, ls=(0, (4, 3)), zorder=2)
    inside = ~(above | below)
    ax.scatter(df.rostberattigade[inside], rate[inside], s=20, color=C["inside"], lw=0, zorder=3)
    ax.scatter(df.rostberattigade[above], rate[above], s=30, color=C["above"], lw=0, zorder=4)
    ax.scatter(df.rostberattigade[below], rate[below], s=30, color=C["below"], lw=0, zorder=4)

    def point(name: str) -> tuple[float, float]:
        r = df[df.namn == name].iloc[0]
        return r.rostberattigade, r.rapporter / r.rostberattigade * PER

    vas = df[df.namn == "Västerås"].iloc[0]
    ax.annotate("Munkfors", point("Munkfors"), xytext=(7, -4), textcoords="offset points", fontsize=11, va="top")
    ax.annotate(f"Västerås: {vas.rapporter} rapporter,\nväntat ungefär {round(vas.rostberattigade * national)}",
                point("Västerås"), xytext=(320_000, 17), ha="center", fontsize=11,
                arrowprops={"arrowstyle": "-", "color": C["muted"], "lw": 0.8, "shrinkB": 4})
    ax.annotate(f"Hela landet {national * PER:.1f}".replace(".", ","), (700_000, national * PER),
                xytext=(0, 6), textcoords="offset points", ha="right", fontsize=10.5)
    n_exp = int(len(df) * 0.05 + 0.5)
    ax.text(700_000, 77, f"{int(above.sum())} kommuner över det grå fältet", color=C["above"], ha="right",
            fontsize=12, weight="bold")
    ax.text(700_000, 73.2, f"{int(below.sum())} under det", color=C["below"], ha="right", fontsize=12, weight="bold")
    ax.text(700_000, 69.6, f"Av ren slump hade det blivit omkring {n_exp}", color=C["muted"], ha="right", fontsize=11)

    ax.set_xscale("log")
    ax.xaxis.set_major_locator(FixedLocator(TICKS))
    ax.xaxis.set_minor_locator(NullLocator())
    ax.xaxis.set_major_formatter(FuncFormatter(thousands))
    ax.set_xlim(grid[0], grid[-1])
    ax.set_ylim(-2, max(rate) * 1.06)
    ax.set_xlabel("Röstberättigade i kommunen", fontsize=11, labelpad=8)
    ax.set_ylabel("Incidentrapporter per 10 000 röstberättigade", fontsize=11, labelpad=8)
    ax.grid(axis="y", color=C["grid"], lw=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(C["muted"])
    ax.tick_params(length=0, labelsize=10.5)

    fig.text(0.04, 0.955, "Incidentrapporter per kommun, valen 2026", fontsize=19, weight="bold", va="center")
    fig.text(0.04, 0.02, "Data: Valkoll och Valmyndigheten. Grått fält: 95 % av utfallen om alla kommuner "
             "rapporterat i samma takt.\nMartin Blomqvist, github.com/MartinBlomqvistDev/valkoll-addition",
             fontsize=8.5, color=C["muted"], linespacing=1.5)
    fig.savefig(out, facecolor=C["bg"])
    plt.close(fig)


def main() -> None:
    """Draw the feed figure."""
    cfg = load_config()
    df = pd.read_parquet(resolve(cfg["paths"]["processed_dir"]) / "kommun_report_rates.parquet")
    national = df.rapporter.sum() / df.rostberattigade.sum()
    out = resolve(cfg["paths"]["output_dir"]) / "13_rapporteringstakt_flode.png"
    draw(df, national, out)
    print(out)


if __name__ == "__main__":
    main()
