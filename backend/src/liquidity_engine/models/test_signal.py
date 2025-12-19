from liquidity_engine.models.signal import Signal, Direction, LiquidityType, RiskLabel

s = Signal(
    symbol="XAUUSD",
    timeframe="M15",
    direction=Direction.SELL,
    entry_zone=(4332.0, 4336.0),
    stop_loss=4370.0,
    targets=[4310.0, 4285.0],
    rr=2.8,
    liquidity_type=LiquidityType.EQH_TO_EQL,
    confidence=81,
    risk=RiskLabel.MEDIUM,
)

print(s.summary())
print(s.model_dump())
