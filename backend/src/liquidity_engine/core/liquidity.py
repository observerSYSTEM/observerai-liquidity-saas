from __future__ import annotations

from dataclasses import dataclass
from typing import List, Literal, Optional, Sequence, Tuple


Side = Literal["HIGH", "LOW"]


@dataclass(frozen=True)
class SwingPoint:
    index: int
    price: float
    side: Side  # "HIGH" or "LOW"


@dataclass(frozen=True)
class LiquidityCluster:
    """
    Represents an EQH or EQL cluster.
    - level: representative price level (mean of points)
    - points: underlying swing points used for this cluster
    """
    side: Side
    level: float
    points: Tuple[SwingPoint, ...]


# ---------------------------
# Swing detection (3-bar fractal)
# ---------------------------

def detect_swings(
    highs: Sequence[float],
    lows: Sequence[float],
) -> List[SwingPoint]:
    """
    3-bar fractal:
      swing high at i if high[i] > high[i-1] and high[i] > high[i+1]
      swing low  at i if low[i]  < low[i-1]  and low[i]  < low[i+1]
    """
    if len(highs) != len(lows):
        raise ValueError("highs and lows must have same length")
    n = len(highs)
    if n < 3:
        return []

    swings: List[SwingPoint] = []
    for i in range(1, n - 1):
        h0, h1, h2 = highs[i - 1], highs[i], highs[i + 1]
        l0, l1, l2 = lows[i - 1], lows[i], lows[i + 1]

        if h1 > h0 and h1 > h2:
            swings.append(SwingPoint(index=i, price=float(h1), side="HIGH"))
        if l1 < l0 and l1 < l2:
            swings.append(SwingPoint(index=i, price=float(l1), side="LOW"))

    # Keep chronological order
    swings.sort(key=lambda s: s.index)
    return swings


# ---------------------------
# Clustering (EQH/EQL)
# ---------------------------

def cluster_equal_levels(
    swings: Sequence[SwingPoint],
    side: Side,
    tolerance: float,
    min_bars_between: int = 5,
    min_points: int = 2,
) -> List[LiquidityCluster]:
    """
    Groups swing highs into EQH clusters or swing lows into EQL clusters based on:
    - same side (HIGH for EQH, LOW for EQL)
    - |price - cluster_level| <= tolerance
    - consecutive points must be separated by min_bars_between

    Note: tolerance is in the same units as price (points). If you use pips,
    convert first at the caller level.
    """
    if tolerance <= 0:
        raise ValueError("tolerance must be > 0")
    if min_bars_between < 0:
        raise ValueError("min_bars_between must be >= 0")
    if min_points < 2:
        raise ValueError("min_points must be >= 2")

    pts = [s for s in swings if s.side == side]
    if not pts:
        return []

    clusters: List[List[SwingPoint]] = []

    for p in pts:
        placed = False

        # Try place into existing cluster if within tolerance AND bar distance ok
        for c in clusters:
            last = c[-1]
            # enforce spacing
            if (p.index - last.index) < min_bars_between:
                continue

            # cluster level based on current points mean
            level = sum(x.price for x in c) / len(c)
            if abs(p.price - level) <= tolerance:
                c.append(p)
                placed = True
                break

        if not placed:
            clusters.append([p])

    # Build LiquidityCluster objects; keep only those with >= min_points
    out: List[LiquidityCluster] = []
    for c in clusters:
        if len(c) >= min_points:
            level = sum(x.price for x in c) / len(c)
            out.append(LiquidityCluster(side=side, level=float(level), points=tuple(c)))

    # Sort by level for easier target selection (LOW ascending, HIGH ascending)
    out.sort(key=lambda cl: cl.level)
    return out


def detect_eqh_eql(
    highs: Sequence[float],
    lows: Sequence[float],
    tolerance: float,
    min_bars_between: int = 5,
    min_points: int = 2,
) -> Tuple[List[LiquidityCluster], List[LiquidityCluster]]:
    """
    Returns (eqh_clusters, eql_clusters)
    """
    swings = detect_swings(highs, lows)
    eqh = cluster_equal_levels(swings, side="HIGH", tolerance=tolerance,
                              min_bars_between=min_bars_between, min_points=min_points)
    eql = cluster_equal_levels(swings, side="LOW", tolerance=tolerance,
                              min_bars_between=min_bars_between, min_points=min_points)
    return eqh, eql


# ---------------------------
# Target selection helpers
# ---------------------------

def nearest_liquidity_below(
    level: float,
    clusters: Sequence[LiquidityCluster],
) -> Optional[LiquidityCluster]:
    """Nearest cluster with level < given level."""
    below = [c for c in clusters if c.level < level]
    if not below:
        return None
    return max(below, key=lambda c: c.level)


def nearest_liquidity_above(
    level: float,
    clusters: Sequence[LiquidityCluster],
) -> Optional[LiquidityCluster]:
    """Nearest cluster with level > given level."""
    above = [c for c in clusters if c.level > level]
    if not above:
        return None
    return min(above, key=lambda c: c.level)
