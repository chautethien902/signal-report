"""
alt_filter.py
Lọc coin không đáng phân tích.
"""

from alt_scanner import CoinData
from config import (
    MIN_MARKET_CAP, MAX_MARKET_CAP,
    MIN_VOLUME_24H, MAX_PUMP_7D_PCT,
    MAX_FDV_MC_RATIO, BLACKLIST_SYMBOLS,
)


def filter_coins(coins: list) -> tuple:
    passed  = []
    reasons = {
        "blacklist":        0,
        "market_cap_small": 0,
        "market_cap_large": 0,
        "volume_low":       0,
        "pump_too_much":    0,
        "tokenomics_bad":   0,
        "price_zero":       0,
    }

    for coin in coins:
        if coin.symbol in BLACKLIST_SYMBOLS:
            reasons["blacklist"] += 1; continue
        if coin.price <= 0:
            reasons["price_zero"] += 1; continue
        if coin.market_cap < MIN_MARKET_CAP:
            reasons["market_cap_small"] += 1; continue
        if coin.market_cap > MAX_MARKET_CAP:
            reasons["market_cap_large"] += 1; continue
        if coin.volume_24h < MIN_VOLUME_24H:
            reasons["volume_low"] += 1; continue
        if coin.change_7d > MAX_PUMP_7D_PCT:
            reasons["pump_too_much"] += 1; continue
        if coin.fdv > 0 and coin.fdv_mc_ratio > MAX_FDV_MC_RATIO:
            reasons["tokenomics_bad"] += 1; continue
        passed.append(coin)

    return passed, reasons


def print_filter_stats(total: int, passed: list, reasons: dict):
    print(f"\n[Filter] {total} coin → {len(passed)} coin pass")
    for k, v in reasons.items():
        if v > 0:
            print(f"  Loại {k}: {v}")
