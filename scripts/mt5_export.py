from liquidity_engine.data.feeds.mt5_feed import MT5Config, connect, shutdown, export_rates_csv

def main():
    # If your MT5 terminal is already logged in, you can leave login/password/server as None.
    cfg = MT5Config(
        login=None,
        password=None,
        server=None,
        path=None,  # optional: r"C:\Program Files\MetaTrader 5\terminal64.exe"
    )

    connect(cfg)
    try:
        export_rates_csv("XAUUSD", "M15", 5000, "data_samples/XAUUSD_M15_mt5.csv")
        export_rates_csv("GBPJPY", "M15", 5000, "data_samples/GBPJPY_M15_mt5.csv")
        export_rates_csv("BTCUSD", "M15", 5000, "data_samples/BTCUSD_M15_mt5.csv")
        export_rates_csv("USDJPY", "M15", 5000, "data_samples/USDJPY_M15_mt5.csv")
        print("✅ Export done: data_samples/*_M15_mt5.csv")
    finally:
        shutdown()


if __name__ == "__main__":
    main()
