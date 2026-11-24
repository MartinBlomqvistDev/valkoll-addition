"""Draw the reporting-rate figure in a portrait format for a social media feed.

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

HEAD = "Franklin Gothic Heavy"
BODY = "Franklin Gothic Book"
DEMI = "Franklin Gothic Demi"
C = {"bg": "#ffffff", "fg": "#111111", "muted": "#5c5c5c", "grid": "#e6e6e6", "band": "#e9e9e9",
     "inside": "#b5b5b5", "above": "#c8102e", "below": "#0b4f8a", "ref": "#111111"}
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

    plt.rcParams.update({"font.family": BODY, "font.size": 12, "text.color": C["fg"],
                         "xtick.color": C["muted"], "ytick.color": C["muted"], "axes.labelcolor": C["muted"]})
    fig = plt.figure(figsize=(7.2, 9), dpi=150, facecolor=C["bg"])
    ax = fig.add_axes((0.1, 0.14, 0.86, 0.58), facecolor=C["bg"])

    ax.fill_between(grid, blo / grid * PER, bhi / grid * PER, color=C["band"], lw=0, zorder=1)
    ax.axhline(national * PER, color=C["ref"], lw=1.2, ls=(0, (4, 3)), zorder=2)
    inside = ~(above | below)
    ax.scatter(df.rostberattigade[inside], rate[inside], s=20, color=C["inside"], lw=0, zorder=3)
    ax.scatter(df.rostberattigade[above], rate[above], s=34, color=C["above"], lw=0.7, edgecolor="white", zorder=4)
    ax.scatter(df.rostberattigade[below], rate[below], s=34, color=C["below"], lw=0.7, edgecolor="white", zorder=4)

    def point(name: str) -> tuple[float, float]:
        r = df[df.namn == name].iloc[0]
        return r.rostberattigade, r.rapporter / r.rostberattigade * PER

    vas = df[df.namn == "Västerås"].iloc[0]
    ax.annotate("Munkfors\n78 per 10 000", point("Munkfors"), xytext=(10, -6), textcoords="offset points",
                fontsize=11, family=DEMI, va="top", color=C["above"])
    ax.annotate(f"Västerås: {vas.rapporter} rapporter.\nI rikets takt ungefär {round(vas.rostberattigade * national)}.",
                point("Västerås"), xytext=(320_000, 17), ha="center", fontsize=11, family=DEMI, color=C["below"],
                arrowprops={"arrowstyle": "-", "color": C["below"], "lw": 1, "shrinkB": 4})
    ax.annotate(f"Hela landet: {national * PER:.1f}".replace(".", ","), (700_000, national * PER),
                xytext=(0, 7), textcoords="offset points", ha="right", fontsize=10.5, color=C["fg"])

    ax.set_xscale("log")
    ax.xaxis.set_major_locator(FixedLocator(TICKS))
    ax.xaxis.set_minor_locator(NullLocator())
    ax.xaxis.set_major_formatter(FuncFormatter(thousands))
    ax.set_xlim(grid[0], grid[-1])
    ax.set_ylim(-2, max(rate) * 1.06)
    ax.set_xlabel("Röstberättigade i kommunen", fontsize=11, labelpad=8)
    ax.set_ylabel("Rapporter per 10 000 röstberättigade", fontsize=11, labelpad=8)
    ax.grid(axis="y", color=C["grid"], lw=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(C["fg"])
    ax.tick_params(length=0, labelsize=10.5)

    n_out, n_exp = int((above | below).sum()), int(len(df) * 0.05 + 0.5)
    fig.add_artist(plt.Line2D([0.06, 0.94], [0.975, 0.975], color=C["fg"], lw=3))
    fig.text(0.06, 0.955, "VALEN 2026  ·  INCIDENTRAPPORTER PER KOMMUN", family=DEMI, fontsize=10.5,
             color=C["above"], va="top")
    fig.text(0.06, 0.925, f"{n_out} av {len(df)} kommuner rapporterade\nmer eller mindre än slumpen förklarar",
             family=HEAD, fontsize=21, va="top", linespacing=1.1)
    fig.text(0.06, 0.835, f"Om alla hade rapporterat i samma takt skulle omkring {n_exp}\nhamna utanför det grå fältet.",
             fontsize=12.5, color=C["muted"], va="top", linespacing=1.3)
    for x, label, colour in ((0.06, f"Fler än väntat ({int(above.sum())})", C["above"]),
                             (0.36, f"Färre än väntat ({int(below.sum())})", C["below"]),
                             (0.66, "Inom slumpens spann", C["inside"])):
        fig.text(x, 0.755, "●", color=colour, fontsize=13, va="center")
        fig.text(x + 0.03, 0.755, label, family=DEMI, fontsize=11, va="center")

    fig.text(0.06, 0.058, "Källa: Valkolls kommuntabell, byggd på Valmyndighetens incidentrapporter, och\n"
             "Valmyndighetens slutliga sammanräkning. Fältet är 95 % av utfallen vid samma takt i hela landet.",
             fontsize=8.5, color=C["muted"], va="center", linespacing=1.35)
    fig.text(0.06, 0.012, "Martin Blomqvist", family=DEMI, fontsize=9.5, va="bottom")
    fig.text(0.94, 0.012, "github.com/MartinBlomqvistDev/valkoll-addition", fontsize=9.5, ha="right", va="bottom")
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
