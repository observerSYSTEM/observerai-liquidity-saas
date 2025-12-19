from liquidity_engine.core.liquidity import (
    detect_eqh_eql,
    nearest_liquidity_above,
    nearest_liquidity_below,
)

# Toy data with repeated highs/lows to form EQH/EQL
highs = [10, 12, 11, 12.1, 11.2, 12.05, 11.0, 13, 12.9]
lows  = [ 9,  8,  9,  8.1,  9.1,  8.05,  9.2,  9,  9.1]

eqh, eql = detect_eqh_eql(highs, lows, tolerance=0.15, min_bars_between=1, min_points=2)

print("EQH clusters:", [(c.level, len(c.points)) for c in eqh])
print("EQL clusters:", [(c.level, len(c.points)) for c in eql])

if eqh:
    lvl = eqh[0].level
    print("Nearest below (to EQH lvl):", nearest_liquidity_below(lvl, eql))
if eql:
    lvl = eql[0].level
    print("Nearest above (to EQL lvl):", nearest_liquidity_above(lvl, eqh))
