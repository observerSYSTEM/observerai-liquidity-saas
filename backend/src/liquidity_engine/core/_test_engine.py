from liquidity_engine.core.engine import EngineConfig, scan_signals

# Fake data with repeated highs/lows
highs = [10, 12, 11, 12.1, 11.2, 12.05, 11.0, 13, 12.9]
lows  = [ 9,  8,  9,  8.1,  9.1,  8.05,  9.2,  9,  9.1]

cfg = EngineConfig(
    tolerance=0.15,
    min_bars_between=1,
    min_points=2,
    entry_buffer=0.05,
    sl_buffer=0.20,
    min_target=0.30,
    min_rr=1.0,
)

signals = scan_signals("XAUUSD", highs=highs, lows=lows, cfg=cfg, timeframe="M15")

print("Signals:", len(signals))
for s in signals:
    print("-", s.summary())
