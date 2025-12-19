from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional

import MetaTrader5 as mt5
import pandas as pd


@dataclass(frozen=True)
class MT5Config:
    login: Optional[int] = None
    password: Optional[str] = None
    server: Optional[str] = None
    path: Optional[str] = None  # terminal64.exe path if needed


def connect(cfg: MT5Config) -> None:
    """
    Connect to MT5 in read-only mode.
    IMPORTANT: Never pass None for path/login/server/password.
    """
    # Build kwargs only with real values
    kwargs = {}

    if cfg.path is not None and str(cfg.path).strip() != "":
        kwargs["path"] = str(cfg.path)

    # Only pass credentials if ALL are provided
    if cfg.login is not None or cfg.password is not None or cfg.server is not None:
        if cfg.login is None or cfg.password is None or cfg.server is None:
            raise ValueError("Provide login, password, and server together (or none of them).")
        kwargs["login"] = int(cfg.login)
        kwargs["password"] = str(cfg.password)
        kwargs["server"] = str(cfg.server)

    ok = mt5.initialize(**kwargs)
    if not ok:
        raise RuntimeError(f"MT5 initialize failed: {mt5.last_error()}")





def shutdown() -> None:
    mt5.shutdown()


def resolve_symbol(requested: str) -> str:
    """
    Tries to resolve broker-specific symbol names.
    Examples:
      XAUUSD -> XAUUSDm, XAUUSD.a, GOLD, GOLDm
      BTCUSD -> BTCUSD, BTCUSDm, BTCUSD.a, BTCUSDT
    """
    requested = requested.strip().upper()

    # Exact match first
    info = mt5.symbol_info(requested)
    if info is not None:
        return requested

    # Search by contains rules
    all_syms = mt5.symbols_get()
    names = [s.name for s in all_syms]

    # Priority candidate patterns per requested
    patterns = []
    if requested == "XAUUSD":
        patterns = ["XAUUSD", "GOLD", "XAU"]
    elif requested == "BTCUSD":
        patterns = ["BTCUSD", "BTCUSDT", "BTC"]
    else:
        # fallback: use requested tokens
        patterns = [requested]

    candidates = []
    for n in names:
        nu = n.upper()
        if any(p in nu for p in patterns):
            candidates.append(n)

    if not candidates:
        raise RuntimeError(f"Symbol not found in MT5 (requested={requested}). No candidates matched {patterns}.")

    # Prefer shortest name (usually the clean base symbol), otherwise first
    candidates.sort(key=lambda x: len(x))
    return candidates[0]


def ensure_symbol(symbol: str) -> str:
    resolved = resolve_symbol(symbol)

    info = mt5.symbol_info(resolved)
    if info is None:
        raise RuntimeError(f"Symbol not found in MT5: {symbol} (resolved={resolved})")

    if not info.visible:
        if not mt5.symbol_select(resolved, True):
            raise RuntimeError(f"Failed to select symbol: {resolved}")

    return resolved



def fetch_rates(
    symbol: str,
    timeframe: str = "M15",
    count: int = 3000,
) -> pd.DataFrame:
    tf_map = {
        "M1": mt5.TIMEFRAME_M1,
        "M5": mt5.TIMEFRAME_M5,
        "M15": mt5.TIMEFRAME_M15,
        "M30": mt5.TIMEFRAME_M30,
        "H1": mt5.TIMEFRAME_H1,
        "H4": mt5.TIMEFRAME_H4,
        "D1": mt5.TIMEFRAME_D1,
    }
    tf = tf_map.get(timeframe.upper())
    if tf is None:
        raise ValueError(f"Unsupported timeframe: {timeframe}")

    symbol_resolved = ensure_symbol(symbol)

    rates = mt5.copy_rates_from_pos(symbol_resolved, tf, 0, count)

    if rates is None:
        raise RuntimeError(f"copy_rates_from_pos returned None: {mt5.last_error()}")
    if len(rates) == 0:
        raise RuntimeError("No rates returned. Check chart subscription / symbol / timeframe.")

    df = pd.DataFrame(rates)
    # MT5 returns 'time' as unix seconds
    df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
    df.rename(columns={"tick_volume": "volume"}, inplace=True)
    return df[["time", "open", "high", "low", "close", "volume"]]


def export_rates_csv(
    symbol: str,
    timeframe: str,
    count: int,
    out_path: str,
) -> str:
    df = fetch_rates(symbol, timeframe=timeframe, count=count)
    df.to_csv(out_path, index=False)
    return out_path
