# ================================================================
#  CRYPTO BOT — CONFIG
#  Chỉ cần điền vào file này, không cần đụng file nào khác
# ================================================================

# ── API Keys ─────────────────────────────────────────────────────
OPENAI_API_KEY  = "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"              # GPT phân tích alt coin
CMC_API_KEY     = "8375ae0384b74740a3868ae711046b91"   # CoinMarketCap cross-check
TELEGRAM_BOT_TOKEN = "8852564017:AAHMpFxDww61E-lmARzHf7U9QRhpGP8mQG8"  # từ @BotFather
TELEGRAM_CHAT_ID   = "1482564970"    # chat_id của bạn

# Tự động bật CMC nếu có key
CMC_ENABLED = CMC_API_KEY != "8375ae0384b74740a3868ae711046b91"

# CryptoPanic API key (tin tức crypto)
# Đăng ký free tại: https://cryptopanic.com/developers/api/
CRYPTOPANIC_API_KEY = "YOUR_CRYPTOPANIC_KEY"

# ── BTC Module ───────────────────────────────────────────────────
BTC_REPORT_INTERVAL_HOURS = 24   # gửi full report mỗi 24h
BTC_ALERT_CHECK_HOURS     = 1    # check pump/dump mỗi 1h
BTC_DROP_ALERT_PCT        = -5.0 # alert khi BTC giảm > 5% trong 24h
BTC_PUMP_ALERT_PCT        = 7.0  # alert khi BTC tăng > 7% trong 24h

# ── Alt Scanner ──────────────────────────────────────────────────
ALT_SCAN_INTERVAL_HOURS = 6      # quét alt mỗi 6h
ALT_SCAN_TOP_N_COINS    = 300    # quét top N coin
ALT_SCORE_THRESHOLD     = 65     # chỉ analyze coin >= điểm này
ALT_MAX_ANALYZE         = 10     # tối đa bao nhiêu coin gọi GPT

# ── Filter settings ──────────────────────────────────────────────
MIN_MARKET_CAP   = 100_000_000
MAX_MARKET_CAP   = 15_000_000_000
MIN_VOLUME_24H   = 5_000_000
MAX_PUMP_7D_PCT  = 80.0
MAX_FDV_MC_RATIO = 8.0

BLACKLIST_SYMBOLS = {
    "USDT","USDC","BUSD","DAI","TUSD","USDP","USDD","FRAX",
    "STETH","WBTC","WETH","WBNB",
    "BTC","ETH","BNB",
    "LEO","HT","OKB",
}

# ── Narrative scores ─────────────────────────────────────────────
NARRATIVE_SCORES = {
    "artificial-intelligence":          25,
    "ai-agents":                        25,
    "depin":                            22,
    "real-world-assets-rwa":            22,
    "layer-2":                          20,
    "modular-blockchain":               20,
    "restaking":                        20,
    "btc-layer-2":                      18,
    "layer-1":                          18,
    "solana-ecosystem":                 20,
    "base-ecosystem":                   18,
    "decentralized-exchange-dex-token": 16,
    "decentralized-finance-defi":       15,
    "gaming":                           14,
    "infrastructure":                   15,
    "meme-token":                       13,
    "nft":                              10,
    "metaverse":                        8,
    "play-to-earn":                     8,
    "move-to-earn":                     5,
    "fan-token":                        4,
}
DEFAULT_NARRATIVE_SCORE = 10
