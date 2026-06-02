"""
data_fetcher.py
Thu thập tất cả dữ liệu cần thiết cho BTC module.
Nguồn: CoinGecko (free) + Binance (free) + yfinance (DXY) + CoinGlass (ETF flow scrape)
"""

import requests
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta


# ── 1. CoinGecko ────────────────────────────────────────────

def get_btc_market_data() -> dict:
    """
    Lấy giá, volume, market cap, dominance, % change từ CoinGecko.
    """
    url = "https://api.coingecko.com/api/v3/coins/bitcoin"
    params = {
        "localization": "false",
        "tickers": "false",
        "market_data": "true",
        "community_data": "false",
        "developer_data": "false",
    }
    try:
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        d = r.json()["market_data"]
        return {
            "price_usd":        d["current_price"]["usd"],
            "market_cap_usd":   d["market_cap"]["usd"],
            "volume_24h_usd":   d["total_volume"]["usd"],
            "change_24h_pct":   d["price_change_percentage_24h"],
            "change_7d_pct":    d["price_change_percentage_7d"],
            "change_30d_pct":   d["price_change_percentage_30d"],
            "ath_usd":          d["ath"]["usd"],
            "ath_change_pct":   d["ath_change_percentage"]["usd"],  # âm = % dưới ATH
        }
    except Exception as e:
        print(f"[CoinGecko BTC] Lỗi: {e}")
        return {}


def get_btc_dominance() -> float:
    """
    BTC dominance (%) từ CoinGecko global endpoint.
    """
    url = "https://api.coingecko.com/api/v3/global"
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        pct = r.json()["data"]["market_cap_percentage"]["btc"]
        return round(pct, 2)
    except Exception as e:
        print(f"[CoinGecko Dominance] Lỗi: {e}")
        return 0.0


# ── 2. Binance — OHLCV weekly để tính MA ───────────────────

def get_btc_weekly_ohlcv(limit: int = 100) -> pd.DataFrame:
    """
    Lấy nến weekly BTC/USDT từ Binance, trả về DataFrame.
    Dùng để tính MA50W, MA200W và phân tích cấu trúc HH/HL.
    """
    url = "https://api.binance.com/api/v3/klines"
    params = {
        "symbol":   "BTCUSDT",
        "interval": "1w",
        "limit":    limit,
    }
    try:
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        raw = r.json()
        df = pd.DataFrame(raw, columns=[
            "open_time","open","high","low","close","volume",
            "close_time","quote_volume","trades",
            "taker_buy_base","taker_buy_quote","ignore"
        ])
        df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
        for col in ["open","high","low","close","volume"]:
            df[col] = df[col].astype(float)
        df = df[["open_time","open","high","low","close","volume"]].copy()
        df.set_index("open_time", inplace=True)
        return df
    except Exception as e:
        print(f"[Binance OHLCV] Lỗi: {e}")
        return pd.DataFrame()


def get_btc_daily_ohlcv(limit: int = 30) -> pd.DataFrame:
    """
    Nến ngày — dùng để check ETF flow context và short-term momentum.
    """
    url = "https://api.binance.com/api/v3/klines"
    params = {"symbol": "BTCUSDT", "interval": "1d", "limit": limit}
    try:
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        raw = r.json()
        df = pd.DataFrame(raw, columns=[
            "open_time","open","high","low","close","volume",
            "close_time","quote_volume","trades",
            "taker_buy_base","taker_buy_quote","ignore"
        ])
        df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
        for col in ["open","high","low","close","volume"]:
            df[col] = df[col].astype(float)
        df = df[["open_time","open","high","low","close","volume"]].copy()
        df.set_index("open_time", inplace=True)
        return df
    except Exception as e:
        print(f"[Binance Daily] Lỗi: {e}")
        return pd.DataFrame()


# ── 3. yfinance — DXY (Dollar Index) ────────────────────────

def get_dxy() -> dict:
    """
    Dollar Index từ Yahoo Finance.
    DXY tăng → BTC thường bị áp lực. DXY giảm → risk-on, tốt cho BTC.
    """
    try:
        ticker = yf.Ticker("DX-Y.NYB")
        hist = ticker.history(period="5d")
        if hist.empty:
            return {"dxy": None, "dxy_change_5d_pct": None}
        latest = hist["Close"].iloc[-1]
        prev   = hist["Close"].iloc[0]
        change = ((latest - prev) / prev) * 100
        return {
            "dxy":               round(float(latest), 2),
            "dxy_change_5d_pct": round(float(change), 2),
        }
    except Exception as e:
        print(f"[DXY yfinance] Lỗi: {e}")
        return {"dxy": None, "dxy_change_5d_pct": None}


# ── 4. CoinGlass — Fear & Greed Index ───────────────────────

def get_fear_greed() -> dict:
    """
    Fear & Greed Index từ alternative.me (free, không cần API key).
    0-24: Extreme Fear | 25-49: Fear | 50-74: Greed | 75-100: Extreme Greed
    """
    url = "https://api.alternative.me/fng/?limit=2"
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()["data"]
        today = data[0]
        yest  = data[1] if len(data) > 1 else data[0]
        return {
            "fg_value":           int(today["value"]),
            "fg_label":           today["value_classification"],
            "fg_value_yesterday": int(yest["value"]),
        }
    except Exception as e:
        print(f"[Fear&Greed] Lỗi: {e}")
        return {"fg_value": None, "fg_label": "N/A", "fg_value_yesterday": None}


# ── 5. Tổng hợp tất cả ──────────────────────────────────────

def fetch_all_btc_data() -> dict:
    """
    Entry point chính — gọi hàm này để lấy toàn bộ data cho BTC module.
    """
    print("[BTC Fetcher] Đang lấy dữ liệu...")

    market   = get_btc_market_data()
    dominance = get_btc_dominance()
    weekly_df = get_btc_weekly_ohlcv(limit=210)  # ~200 tuần để có MA200W
    daily_df  = get_btc_daily_ohlcv(limit=30)
    dxy       = get_dxy()
    fg        = get_fear_greed()

    print("[BTC Fetcher] Xong.")

    return {
        "timestamp":  datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "market":     market,
        "dominance":  dominance,
        "weekly_df":  weekly_df,
        "daily_df":   daily_df,
        "dxy":        dxy,
        "fear_greed": fg,
    }


if __name__ == "__main__":
    data = fetch_all_btc_data()
    print("\n=== BTC Market Data ===")
    print(data["market"])
    print(f"\nDominance: {data['dominance']}%")
    print(f"DXY: {data['dxy']}")
    print(f"Fear & Greed: {data['fear_greed']}")
    print(f"\nWeekly candles: {len(data['weekly_df'])} rows")
