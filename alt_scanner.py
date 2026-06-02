"""
scanner.py
Module 1: Thu thập dữ liệu thị trường cho top 300 coin.
Nguồn:
  - CoinGecko  → market data chính + categories/narrative
  - CMC        → cross-check giá, volume, market cap (tiết kiệm credit)
  - Binance    → OHLCV chart để tính momentum kỹ thuật
"""

import requests
import pandas as pd
import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CoinData:
    """Dữ liệu thô của 1 coin sau khi fetch."""
    symbol:            str   = ""
    name:              str   = ""
    coingecko_id:      str   = ""
    market_cap:        float = 0.0
    volume_24h:        float = 0.0
    price:             float = 0.0
    change_1h:         float = 0.0
    change_24h:        float = 0.0
    change_7d:         float = 0.0
    change_30d:        float = 0.0
    fdv:               float = 0.0
    fdv_mc_ratio:      float = 1.0
    categories:        list  = field(default_factory=list)
    # OHLCV weekly (từ Binance)
    weekly_closes:     list  = field(default_factory=list)
    weekly_volumes:    list  = field(default_factory=list)
    volume_spike:      float = 1.0
    # CMC cross-check fields
    cmc_price:         float = 0.0
    cmc_market_cap:    float = 0.0
    cmc_volume_24h:    float = 0.0
    cmc_rank:          int   = 0
    price_diff_pct:    float = 0.0
    mc_diff_pct:       float = 0.0
    vol_diff_pct:      float = 0.0
    has_discrepancy:   bool  = False
    discrepancy_notes: list  = field(default_factory=list)


# ── CoinGecko ────────────────────────────────────────────────

def fetch_market_list(page: int = 1, per_page: int = 100) -> list:
    """
    Lấy 1 trang market data từ CoinGecko.
    """
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {
        "vs_currency":             "usd",
        "order":                   "market_cap_desc",
        "per_page":                per_page,
        "page":                    page,
        "sparkline":               "false",
        "price_change_percentage": "1h,24h,7d,30d",
    }
    try:
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[CoinGecko Markets page={page}] Lỗi: {e}")
        return []


def fetch_all_coins(total: int = 300) -> list:
    """
    Lấy top N coin từ CoinGecko.
    Rate limit free tier: ~30 req/min → sleep giữa các page.
    """
    coins    = []
    per_page = 100
    pages    = (total + per_page - 1) // per_page

    print(f"[Scanner] Lấy top {total} coin từ CoinGecko ({pages} pages)...")

    for page in range(1, pages + 1):
        raw = fetch_market_list(page=page, per_page=per_page)
        for item in raw:
            c              = CoinData()
            c.symbol       = (item.get("symbol") or "").upper()
            c.name         = item.get("name", "")
            c.coingecko_id = item.get("id", "")
            c.market_cap   = item.get("market_cap") or 0
            c.volume_24h   = item.get("total_volume") or 0
            c.price        = item.get("current_price") or 0
            c.change_1h    = item.get("price_change_percentage_1h_in_currency") or 0
            c.change_24h   = item.get("price_change_percentage_24h") or 0
            c.change_7d    = item.get("price_change_percentage_7d_in_currency") or 0
            c.change_30d   = item.get("price_change_percentage_30d_in_currency") or 0
            fdv            = item.get("fully_diluted_valuation") or 0
            mc             = c.market_cap
            c.fdv          = fdv
            c.fdv_mc_ratio = (fdv / mc) if (mc > 0 and fdv > 0) else 1.0
            coins.append(c)

        print(f"  Page {page}/{pages}: {len(raw)} coin")
        if page < pages:
            time.sleep(2)

    print(f"[Scanner] Tổng: {len(coins)} coin từ CoinGecko")
    return coins


def fetch_coin_categories(coingecko_id: str, retries: int = 3) -> list:
    """
    Lấy categories của 1 coin. Có retry + exponential backoff khi bị 429.
    """
    url = f"https://api.coingecko.com/api/v3/coins/{coingecko_id}"
    params = {
        "localization":   "false",
        "tickers":        "false",
        "market_data":    "false",
        "community_data": "false",
        "developer_data": "false",
    }
    for attempt in range(retries):
        try:
            r = requests.get(url, params=params, timeout=10)
            if r.status_code == 429:
                wait = 12 * (attempt + 1)   # 12s, 24s, 36s
                print(f"[CoinGecko] Rate limited — chờ {wait}s rồi thử lại...")
                time.sleep(wait)
                continue
            r.raise_for_status()
            return r.json().get("categories", [])
        except requests.exceptions.HTTPError:
            raise
        except Exception as e:
            print(f"[CoinGecko Categories {coingecko_id}] Lỗi: {e}")
            return []
    return []


# Keyword map để tự suy ra narrative từ name/id mà không cần gọi API
_KEYWORD_NARRATIVE_MAP = {
    # AI
    "ai": "artificial-intelligence",
    "artificial": "artificial-intelligence",
    "intelligence": "artificial-intelligence",
    "agent": "ai-agents",
    "fetch": "artificial-intelligence",
    "singularity": "artificial-intelligence",
    "ocean": "artificial-intelligence",
    # DePIN
    "depin": "depin",
    "render": "depin",
    "helium": "depin",
    "hivemapper": "depin",
    "akash": "depin",
    # RWA
    "rwa": "real-world-assets-rwa",
    "ondo": "real-world-assets-rwa",
    "centrifuge": "real-world-assets-rwa",
    # L2
    "arbitrum": "layer-2",
    "optimism": "layer-2",
    "polygon": "layer-2",
    "zksync": "layer-2",
    "starknet": "layer-2",
    "mantle": "layer-2",
    "scroll": "layer-2",
    "linea": "layer-2",
    # L1
    "solana": "solana-ecosystem",
    "avalanche": "layer-1",
    "near": "layer-1",
    "sui": "layer-1",
    "aptos": "layer-1",
    "sei": "layer-1",
    "injective": "layer-1",
    "cosmos": "layer-1",
    "ton": "layer-1",
    # DeFi
    "uniswap": "decentralized-exchange-dex-token",
    "curve": "decentralized-exchange-dex-token",
    "aave": "decentralized-finance-defi",
    "compound": "decentralized-finance-defi",
    "lido": "restaking",
    "eigen": "restaking",
    "etherfi": "restaking",
    # Gaming
    "game": "gaming",
    "gala": "gaming",
    "illuvium": "gaming",
    "axie": "gaming",
    # Meme
    "doge": "meme-token",
    "shib": "meme-token",
    "pepe": "meme-token",
    "floki": "meme-token",
    "bonk": "meme-token",
    "wif": "meme-token",
    "meme": "meme-token",
}


def infer_categories_from_name(symbol: str, name: str, coingecko_id: str) -> list:
    """
    Tự suy ra narrative từ symbol/name/id mà không cần gọi API.
    Dùng làm fallback khi bị rate limit.
    """
    text = f"{symbol} {name} {coingecko_id}".lower()
    found = []
    for keyword, category in _KEYWORD_NARRATIVE_MAP.items():
        if keyword in text and category not in found:
            found.append(category)
    return found if found else []


def fetch_categories_bulk(coins: list, max_api_calls: int = 30) -> list:
    """
    Lấy categories cho list coin một cách thông minh:
    - Bước 1: Tự suy ra từ keyword (0 API call)
    - Bước 2: Chỉ gọi API cho coin chưa suy ra được, tối đa max_api_calls
    - Sleep đủ dài giữa các request để tránh 429
    """
    no_category = [c for c in coins if not c.categories]
    if not no_category:
        return coins

    print(f"[Categories] Xử lý {len(no_category)} coin...")

    # Bước 1: infer từ keyword
    inferred = 0
    need_api = []
    for coin in no_category:
        cats = infer_categories_from_name(coin.symbol, coin.name, coin.coingecko_id)
        if cats:
            coin.categories = cats
            inferred += 1
        else:
            need_api.append(coin)

    print(f"[Categories] Inferred: {inferred} | Cần API: {len(need_api)} | Giới hạn API: {max_api_calls}")

    # Bước 2: gọi API cho coin thật sự không suy ra được, có rate-limit control
    api_called = 0
    for coin in need_api[:max_api_calls]:
        cats = fetch_coin_categories(coin.coingecko_id)
        if cats:
            coin.categories = cats
        api_called += 1
        # Sleep dài hơn: 2.5s/request → ~24 req/min, an toàn với free tier
        time.sleep(2.5)

    print(f"[Categories] Xong. API calls dùng: {api_called}")
    return coins


# ── CMC cross-check ──────────────────────────────────────────

def enrich_with_cmc(coins: list, cmc_api_key: str) -> list:
    """
    Cross-check data CoinGecko với CMC cho danh sách coin đã pass filter.
    
    Strategy tiết kiệm credit:
      - Gọi 1 request duy nhất lấy top 300 CMC listings (1 credit)
      - Map theo symbol → không cần gọi thêm
      - Tổng: 1 credit/lần scan → 4 credit/ngày nếu scan 4 lần
    """
    if not cmc_api_key or cmc_api_key == "YOUR_CMC_API_KEY":
        print("[CMC] API key chưa cấu hình — bỏ qua cross-check")
        return coins

    print(f"[CMC] Cross-check {len(coins)} coin với CoinMarketCap...")

    # Lấy top 300 CMC listings trong 1 request
    url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest"
    headers = {"X-CMC_PRO_API_KEY": cmc_api_key, "Accept": "application/json"}
    params  = {"limit": 300, "convert": "USD", "sort": "market_cap"}

    try:
        r = requests.get(url, headers=headers, params=params, timeout=15)
        r.raise_for_status()
        cmc_data = r.json().get("data", [])
        print(f"[CMC] Lấy được {len(cmc_data)} coin (1 credit dùng)")
    except Exception as e:
        print(f"[CMC] Lỗi lấy listings: {e} — bỏ qua cross-check")
        return coins

    # Build lookup dict: symbol → CMC data
    # Lưu ý: CMC có thể có nhiều coin cùng symbol → lấy coin rank cao nhất (nhỏ nhất)
    cmc_lookup = {}
    for item in cmc_data:
        sym = item.get("symbol", "").upper()
        usd = item.get("quote", {}).get("USD", {})
        existing = cmc_lookup.get(sym)
        rank = item.get("cmc_rank", 9999)
        if existing is None or rank < existing["rank"]:
            cmc_lookup[sym] = {
                "price":      usd.get("price", 0) or 0,
                "market_cap": usd.get("market_cap", 0) or 0,
                "volume_24h": usd.get("volume_24h", 0) or 0,
                "change_24h": usd.get("percent_change_24h", 0) or 0,
                "rank":       rank,
            }

    # Cross-check từng coin
    PRICE_THRESHOLD  = 5.0    # % lệch giá → flag
    MC_THRESHOLD     = 5.0    # % lệch market cap → flag
    VOL_THRESHOLD    = 25.0   # % lệch volume → flag (volume thường lệch nhiều hơn)

    matched = 0
    flagged = 0

    for coin in coins:
        cmc = cmc_lookup.get(coin.symbol)
        if not cmc or cmc["price"] == 0:
            continue

        matched += 1
        coin.cmc_price      = cmc["price"]
        coin.cmc_market_cap = cmc["market_cap"]
        coin.cmc_volume_24h = cmc["volume_24h"]
        coin.cmc_rank       = cmc["rank"]

        # Tính % lệch (CG so với CMC)
        coin.price_diff_pct = _pct_diff(coin.price,       cmc["price"])
        coin.mc_diff_pct    = _pct_diff(coin.market_cap,  cmc["market_cap"])
        coin.vol_diff_pct   = _pct_diff(coin.volume_24h,  cmc["volume_24h"])

        # Flag nếu lệch quá threshold
        notes = []
        if abs(coin.price_diff_pct) > PRICE_THRESHOLD:
            notes.append(
                f"Giá lệch {coin.price_diff_pct:+.1f}% "
                f"(CG:${coin.price:.4f} vs CMC:${cmc['price']:.4f})"
            )
        if abs(coin.mc_diff_pct) > MC_THRESHOLD:
            notes.append(
                f"MC lệch {coin.mc_diff_pct:+.1f}% "
                f"(CG:${coin.market_cap/1e6:.0f}M vs CMC:${cmc['market_cap']/1e6:.0f}M)"
            )
        if abs(coin.vol_diff_pct) > VOL_THRESHOLD:
            notes.append(
                f"Volume lệch {coin.vol_diff_pct:+.1f}% "
                f"(CG:${coin.volume_24h/1e6:.0f}M vs CMC:${cmc['volume_24h']/1e6:.0f}M)"
            )

        if notes:
            coin.has_discrepancy   = True
            coin.discrepancy_notes = notes
            flagged += 1

    print(f"[CMC] Matched: {matched}/{len(coins)} coin | Flagged discrepancy: {flagged}")
    return coins


def _pct_diff(cg_val: float, cmc_val: float) -> float:
    """% lệch của CG so với CMC. Dương = CG cao hơn CMC."""
    if cmc_val == 0:
        return 0.0
    return round(((cg_val - cmc_val) / cmc_val) * 100, 2)


# ── Binance ──────────────────────────────────────────────────

def get_binance_symbol(symbol: str) -> Optional[str]:
    pairs = [f"{symbol}USDT", f"{symbol}USDC"]
    for pair in pairs:
        try:
            r = requests.get(
                "https://api.binance.com/api/v3/ticker/price",
                params={"symbol": pair}, timeout=5
            )
            if r.status_code == 200:
                return pair
        except:
            pass
    return None


def fetch_ohlcv_weekly(binance_symbol: str, limit: int = 14):
    url    = "https://api.binance.com/api/v3/klines"
    params = {"symbol": binance_symbol, "interval": "1w", "limit": limit}
    try:
        r   = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        raw = r.json()
        return [float(k[4]) for k in raw], [float(k[5]) for k in raw]
    except:
        return [], []


def fetch_volume_spike(binance_symbol: str) -> float:
    url    = "https://api.binance.com/api/v3/klines"
    params = {"symbol": binance_symbol, "interval": "1d", "limit": 8}
    try:
        r   = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        raw = r.json()
        if len(raw) < 2:
            return 1.0
        vols      = [float(k[5]) for k in raw]
        vol_today = vols[-1]
        vol_avg   = sum(vols[:-1]) / len(vols[:-1])
        return round(vol_today / vol_avg, 2) if vol_avg > 0 else 1.0
    except:
        return 1.0


def enrich_with_binance(coins: list) -> list:
    print(f"[Scanner] Lấy OHLCV Binance cho {len(coins)} coin...")
    for i, coin in enumerate(coins):
        pair = get_binance_symbol(coin.symbol)
        if not pair:
            continue
        coin.weekly_closes, coin.weekly_volumes = fetch_ohlcv_weekly(pair)
        coin.volume_spike = fetch_volume_spike(pair)
        if i % 10 == 9:
            time.sleep(0.5)
    print(f"[Scanner] Binance enrich xong.")
    return coins
