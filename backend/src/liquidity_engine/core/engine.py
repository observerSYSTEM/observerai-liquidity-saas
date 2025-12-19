from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from liquidity_engine.core.liquidity import (
    LiquidityCluster,
    detect_eqh_eql,
    nearest_liquidity_above,
    nearest_liquidity_below,
)
from liquidity_engine.models.signal import Direction, LiquidityType, RiskLabel, Signal


@dataclass(frozen=True)
class EngineConfig:
    # Liquidity detection
    tolerance: float = 0.15              # price units (convert pips before if needed)
    min_bars_between: int = 5
    min_points: int = 2

    # Trade construction
    entry_buffer: float = 0.20           # price units around liquidity level
    sl_buffer: float = 0.50              # price units beyond level

    # Filters
    min_target: float = 1.00             # min distance to target (price units)
    min_rr: float = 1.2                  # minimum RR

    # Output
    timeframe: str = "M15"
    risk_label: RiskLabel = RiskLabel.MEDIUM
    confidence_default: int = 70


def _mid(entry_zone: Tuple[float, float]) -> float:
    return (entry_zone[0] + entry_zone[1]) / 2.0


def _build_sell_from_eqh(
    symbol: str,
    timeframe: str,
    eqh: LiquidityCluster,
    eql_clusters: Sequence[LiquidityCluster],
    cfg: EngineConfig,
) -> Optional[Signal]:
    entry_zone = (eqh.level - cfg.entry_buffer, eqh.level + cfg.entry_buffer)
    sl = eqh.level + cfg.sl_buffer

    target = nearest_liquidity_below(eqh.level, eql_clusters)
    if not target:
        return None

    entry = _mid(entry_zone)
    tp1 = target.level

    risk = sl - entry
    reward = entry - tp1

    if risk <= 0 or reward <= 0:
        return None

    rr = reward / risk
    dist_to_target = reward

    # Filters
    if dist_to_target < cfg.min_target:
        return None
    if rr < cfg.min_rr:
        return None

    return Signal(
        symbol=symbol,
        timeframe=timeframe,
        direction=Direction.SELL,
        entry_zone=entry_zone,
        stop_loss=sl,
        targets=[tp1],
        rr=round(rr, 4),
        liquidity_type=LiquidityType.EQH_TO_EQL,
        confidence=cfg.confidence_default,
        risk=cfg.risk_label,
        level=eqh.level,
    )


def _build_buy_from_eql(
    symbol: str,
    timeframe: str,
    eql: LiquidityCluster,
    eqh_clusters: Sequence[LiquidityCluster],
    cfg: EngineConfig,
) -> Optional[Signal]:
    entry_zone = (eql.level - cfg.entry_buffer, eql.level + cfg.entry_buffer)
    sl = eql.level - cfg.sl_buffer

    target = nearest_liquidity_above(eql.level, eqh_clusters)
    if not target:
        return None

    entry = _mid(entry_zone)
    tp1 = target.level

    risk = entry - sl
    reward = tp1 - entry

    if risk <= 0 or reward <= 0:
        return None

    rr = reward / risk
    dist_to_target = reward

    # Filters
    if dist_to_target < cfg.min_target:
        return None
    if rr < cfg.min_rr:
        return None

    return Signal(
        symbol=symbol,
        timeframe=timeframe,
        direction=Direction.BUY,
        entry_zone=entry_zone,
        stop_loss=sl,
        targets=[tp1],
        rr=round(rr, 4),
        liquidity_type=LiquidityType.EQL_TO_EQH,
        confidence=cfg.confidence_default,
        risk=cfg.risk_label,
        level=eql.level,
    )


def scan_signals(
    symbol: str,
    highs: Sequence[float],
    lows: Sequence[float],
    cfg: Optional[EngineConfig] = None,
    timeframe: str = "M15",
) -> List[Signal]:
    """
    Main API for v1:
    Given highs/lows arrays, detect EQH/EQL and generate Signals.

    Returns a list of validated Signal objects.
    """
    cfg = cfg or EngineConfig()
    eqh_clusters, eql_clusters = detect_eqh_eql(
        highs=highs,
        lows=lows,
        tolerance=cfg.tolerance,
        min_bars_between=cfg.min_bars_between,
        min_points=cfg.min_points,
    )

    signals: List[Signal] = []

    # SELL candidates from EQH -> nearest EQL
    for eqh in eqh_clusters:
        s = _build_sell_from_eqh(symbol, timeframe, eqh, eql_clusters, cfg)
        if s:
            signals.append(s)

    # BUY candidates from EQL -> nearest EQH
    for eql in eql_clusters:
        s = _build_buy_from_eql(symbol, timeframe, eql, eqh_clusters, cfg)
        if s:
            signals.append(s)

    # Sort by confidence desc, then RR desc (simple ordering for now)
    signals.sort(key=lambda x: (x.confidence, x.rr), reverse=True)
    return signals
