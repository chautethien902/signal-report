# 🤖 Crypto Bot — BTC + Alt Scanner

Phân tích BTC và tìm coin spot tiềm năng tự động, gửi report qua Telegram.

---

## Cấu trúc

```
crypto_bot/
├── config.py          ← ⭐ CHỈ CẦN ĐIỀN FILE NÀY
├── main.py            ← Entry point duy nhất
│
├── btc_fetcher.py     ← Lấy data BTC (CoinGecko, Binance, yfinance)
├── btc_analyzer.py    ← Phân tích cycle, MA, macro, recommendation
├── btc_reporter.py    ← Format + gửi BTC report Telegram
│
├── alt_scanner.py     ← Lấy top 300 coin (CoinGecko + CMC + Binance)
├── alt_filter.py      ← Lọc coin rác
├── alt_scorer.py      ← Chấm điểm 5 nhóm (Narrative/Momentum/Volume/Tokenomics/Sentiment)
├── alt_analyst.py     ← GPT viết deep analysis
└── alt_reporter.py    ← Format + gửi Alt report Telegram
```

---

## Setup (5 phút)

### 1. Cài thư viện
```bash
pip install requests pandas yfinance openai schedule python-telegram-bot
```

### 2. Lấy API keys

| Key | Lấy ở đâu | Bắt buộc? |
|-----|-----------|-----------|
| Telegram Bot Token | Chat với @BotFather → /newbot | ✅ |
| Telegram Chat ID | Chat với @userinfobot | ✅ |
| OpenAI API Key | platform.openai.com | ✅ (GPT analysis) |
| CMC API Key | pro.coinmarketcap.com/signup | ❌ optional |

### 3. Điền config.py
```python
OPENAI_API_KEY     = "sk-..."
CMC_API_KEY        = "..."        # optional, để "YOUR_CMC_API_KEY" nếu không dùng
TELEGRAM_BOT_TOKEN = "..."
TELEGRAM_CHAT_ID   = "..."
```

---

## Cách chạy

```bash
# Test 1 lần (không gửi Telegram, in ra console)
python main.py --dry-run

# Chạy thật 1 lần
python main.py

# Chỉ BTC
python main.py --btc-only

# Chỉ Alt scanner
python main.py --alt-only

# Chạy tự động (để terminal mở)
python main.py --schedule
```

---

## Lịch tự động (--schedule)

| Task | Tần suất |
|------|----------|
| BTC full report | Mỗi 24h |
| BTC alert check (pump/dump) | Mỗi 1h |
| Alt coin scan | Mỗi 6h |

---

## Telegram output

**BTC Daily Report:**
```
📊 BTC DAILY REPORT
💰 Giá: $97,200
📈 7D: +5.2% | 30D: +18%
...
🟢🟢 KHUYẾN NGHỊ: STRONG BUY
✅ Cycle còn early-mid bull
✅ Trend UPTREND (HH+HL)
✅ Fear & Greed = 32 (Fear)
```

**Alt Scanner Report:**
```
🔍 ALT SCANNER REPORT
1. 🟢 FET   — 82/100 — +25% 7D — ACCUMULATE
2. 🟡 RNDR  — 74/100 — +15% 7D — WATCH
3. 🟡 NEAR  — 71/100 — +18% 7D — WATCH

--- Chi tiết từng coin ---
🟢 Fetch.ai (FET) — ACCUMULATE
🔎 Cross-check: ✅ CMC khớp
⭐ Score: 🟢 ████████░░ 82/100
🧠 Thesis: ...
🎯 Upside: x1.5 conservative, x3 bull case
⚠️ Rủi ro: ...
```

---

## Lưu ý

- Bot **không tự mua** — chỉ phân tích và đưa ra khuyến nghị
- Đây là công cụ tham khảo, **không phải lời khuyên đầu tư**
- Tự chịu trách nhiệm với mọi quyết định giao dịch
