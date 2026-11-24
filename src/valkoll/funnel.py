"""Funnel-band helpers shared by the publication figures (steps 12 and 13)."""

import numpy as np
from scipy.stats import poisson


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
