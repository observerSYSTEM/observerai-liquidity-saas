from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional, Tuple

from pydantic import BaseModel, Field, field_validator, model_validator


# ---------- Enums ----------

class Direction(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class RiskLabel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class LiquidityType(str, Enum):
    EQH_TO_EQL = "EQH→EQL"
    EQL_TO_EQH = "EQL→EQH"


# ---------- Models ----------

class Signal(BaseModel):
    """
    Core Signal contract used across:
    - engine output
    - API responses
    - Telegram alerts
    - storage/db

    v1 focuses on objective liquidity-only signals.
    """

    # Identity / metadata
    symbol: str = Field(..., examples=["XAUUSD", "GBPJPY", "BTCUSD", "USDJPY"])
    timeframe: str = Field(..., examples=["M15"])
    direction: Direction

    # Trade levels
    entry_zone: Tuple[float, float] = Field(..., description="Entry zone as [low, high].")
    stop_loss: float = Field(..., description="Stop-loss price.")
    targets: List[float] = Field(..., min_length=1, description="Take-profit targets (tp1, tp2...).")

    # Analytics
    rr: float = Field(..., gt=0, description="Risk:Reward estimate.")
    liquidity_type: LiquidityType
    confidence: int = Field(..., ge=0, le=100, description="0–100 confidence score.")
    risk: RiskLabel = Field(..., description="Risk label derived from volatility/spread rules.")

    # Extra traceability (optional but useful)
    setup_id: Optional[str] = Field(default=None, description="Optional unique id for dedupe/tracking.")
    session: Optional[str] = Field(default=None, examples=["London", "NY", "Asia", "24/7"])
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Optional fields for debugging / explainability
    level: Optional[float] = Field(default=None, description="Liquidity level price (EQH/EQL level).")
    tolerance_pips: Optional[float] = Field(default=None, ge=0)
    min_target_pips: Optional[float] = Field(default=None, ge=0)

    # ---------- Field validators ----------

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, v: str) -> str:
        v = (v or "").strip().upper()
        if not v:
            raise ValueError("symbol cannot be empty")
        return v

    @field_validator("timeframe")
    @classmethod
    def normalize_timeframe(cls, v: str) -> str:
        v = (v or "").strip().upper()
        if v not in {"M5", "M15", "M30", "H1", "H4", "D1"}:
            raise ValueError(f"unsupported timeframe: {v}")
        return v

    @field_validator("entry_zone")
    @classmethod
    def validate_entry_zone(cls, v: Tuple[float, float]) -> Tuple[float, float]:
        low, high = float(v[0]), float(v[1])
        if low <= 0 or high <= 0:
            raise ValueError("entry_zone prices must be > 0")
        if low >= high:
            raise ValueError("entry_zone must be [low, high] with low < high")
        return (low, high)

    @field_validator("targets")
    @classmethod
    def validate_targets(cls, v: List[float]) -> List[float]:
        vals = [float(x) for x in v]
        if any(x <= 0 for x in vals):
            raise ValueError("targets must be > 0")
        # ensure monotonic targets (not strict, but consistent with direction checked later)
        return vals

    @field_validator("created_at")
    @classmethod
    def ensure_timezone(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc)

    # ---------- Cross-field validation ----------

    @model_validator(mode="after")
    def validate_levels_vs_direction(self) -> "Signal":
        low, high = self.entry_zone
        entry_mid = (low + high) / 2.0

        # Stop-loss should be placed logically vs direction:
        if self.direction == Direction.BUY:
            if not (self.stop_loss < low):
                raise ValueError("For BUY, stop_loss must be below entry_zone.")
            # targets must be above entry
            if not all(t > entry_mid for t in self.targets):
                raise ValueError("For BUY, all targets must be above entry.")
            if self.liquidity_type != LiquidityType.EQL_TO_EQH:
                raise ValueError("For BUY, liquidity_type must be 'EQL→EQH'.")
        else:  # SELL
            if not (self.stop_loss > high):
                raise ValueError("For SELL, stop_loss must be above entry_zone.")
            # targets must be below entry
            if not all(t < entry_mid for t in self.targets):
                raise ValueError("For SELL, all targets must be below entry.")
            if self.liquidity_type != LiquidityType.EQH_TO_EQL:
                raise ValueError("For SELL, liquidity_type must be 'EQH→EQL'.")

        # RR sanity check
        if self.rr <= 0:
            raise ValueError("rr must be > 0")

        return self

    # Convenience: human-readable summary
    def summary(self) -> str:
        low, high = self.entry_zone
        return (
            f"{self.symbol} {self.timeframe} {self.direction} | "
            f"Entry {low:.2f}-{high:.2f} | SL {self.stop_loss:.2f} | "
            f"TP {', '.join(f'{t:.2f}' for t in self.targets)} | "
            f"RR {self.rr:.2f} | Conf {self.confidence}% | Risk {self.risk}"
        )
