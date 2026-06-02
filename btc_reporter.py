"""
reporter.py
Format BTCAnalysis thành message đẹp và gửi qua Telegram.
Hỗ trợ:
  - Daily report (full)
  - Alert đột xuất (khi giá pump/dump mạnh)
"""

import requests
from btc_analyzer import BTCAnalysis
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID


def fmt_price(n: float) -> str:
    return f"${n:,.0f}"

def fmt_pct(n: float) -> str:
    arrow = "📈" if n > 0 else "📉"
    return f"{arrow} {n:+.2f}%"

def fmt_score(n: int) -> str:
    if n >= 70: return f"{n}/100 🟢"
    if n >= 50: return f"{n}/100 🟡"
    return f"{n}/100 🔴"


def build_daily_report(a: BTCAnalysis, timestamp: str) -> str:
    """
    Tạo full daily report — gửi 1 lần/ngày.
    """

    # ── Reasons block ──────────────────────────────────────
    buy_block  = "\n".join(f"  ✅ {r}" for r in a.buy_reasoning)  or "  (Không có tín hiệu tích cực rõ)"
    risk_block = "\n".join(f"  ⚠️ {r}" for r in a.risk_reasoning) or "  (Không có red flag lớn)"

    # ── DCA block ──────────────────────────────────────────
    if a.dca_zone_low > 0:
        dca_block = (
            f"  Vùng DCA: {fmt_price(a.dca_zone_low)} – {fmt_price(a.dca_zone_high)}\n"
            f"  Invalidation: {fmt_price(a.invalidation_price)} (mất vùng này → thesis sai)"
        )
    else:
        dca_block = "  Không đủ dữ liệu MA để tính vùng DCA"

    # ── Entry condition block (khi giá đang yếu) ───────────
    if a.wait_for_level and a.entry_condition:
        entry_block = (
            "\n━━━━━━━━━━━━━━━━━━━━"
            "\n⏳ <b>CHƯA NÊN MUA NGAY — CHỜ VÙNG NÀY:</b>"
            f"\n  📍 {a.entry_condition}"
            "\n  💡 Lý do: Thesis macro/cycle tốt nhưng price action ngắn hạn đang yếu."
            "\n     Mua ngay = bắt dao đang rơi. Chờ về vùng support + nến xác nhận mới hành động."
        )
    else:
        entry_block = ""

    # ── Altseason hint ─────────────────────────────────────
    alt_hint = f"🔄 Alt signal: {a.altseason_signal}" if a.altseason_signal else ""

    # ── DXY line ───────────────────────────────────────────
    dxy_line = (
        f"  DXY: {a.dxy} ({a.dxy_change_5d:+.2f}% 5D) → {a.dxy_signal}"
        if a.dxy is not None else "  DXY: N/A"
    )

    # ── Scenario block ────────────────────────────────────────
    scenario_block = ""
    if a.scenario_bearish or a.scenario_bullish:
        scenario_block = (
            "\n━━━━━━━━━━━━━━━━━━━━"
            "\n🎯 <b>HAI KỊCH BẢN CHÍNH</b>"
            f"\n\n🟢 <b>Kịch bản tăng:</b>\n{a.scenario_bullish}"
            f"\n\n🔴 <b>Kịch bản giảm:</b>\n{a.scenario_bearish}"
        )

    stv_block = ""
    if a.short_term_view:
        stv_block = (
            "\n━━━━━━━━━━━━━━━━━━━━"
            f"\n⚡ <b>GÓC NHÌN NGẮN HẠN</b>\n{a.short_term_view}"
        )

    opinion_block = ""
    if a.trend_opinion:
        opinion_block = (
            "\n━━━━━━━━━━━━━━━━━━━━"
            f"\n{a.trend_emoji} <b>QUAN ĐIỂM: {a.trend_opinion}</b>"
        )

        msg = f"""
📊 <b>BTC DAILY REPORT</b>
🕐 {timestamp}

━━━━━━━━━━━━━━━━━━━━
💰 <b>Giá:</b> {fmt_price(a.price)}
📅 24H: {fmt_pct(a.change_24h)}  |  7D: {fmt_pct(a.change_7d)}  |  30D: {fmt_pct(a.change_30d)}
🏔 ATH: {fmt_price(a.ath_usd)} (đang {a.ath_change_pct:.1f}% so với ATH)
📦 Market Cap: ${a.market_cap/1e9:.2f}B  |  Volume 24H: ${a.volume_24h/1e9:.2f}B

━━━━━━━━━━━━━━━━━━━━
📐 <b>KỸ THUẬT</b>
  Trend: {a.trend_structure} — {a.structure_detail}
  MA50W:  {fmt_price(a.ma50w)} (giá {a.price_vs_ma50w_pct:+.1f}%)
  MA200W: {fmt_price(a.ma200w)} (giá {a.price_vs_ma200w_pct:+.1f}%)
  Score kỹ thuật: {fmt_score(a.technical_score)}

━━━━━━━━━━━━━━━━━━━━
🔄 <b>CYCLE / ON-CHAIN PROXY</b>
  Phase: <b>{a.cycle_phase}</b>
  {a.cycle_detail}
  MVRV proxy: {a.mvrv_proxy_score}/100 {"🔥 cẩn thận" if a.mvrv_proxy_score > 70 else "✅ ổn"}
  Score chu kỳ: {fmt_score(a.cycle_score)}

━━━━━━━━━━━━━━━━━━━━
🌍 <b>MACRO</b>
{dxy_line}
  Fear & Greed: {a.fear_greed} — {a.fear_greed_label}
  → {a.fear_greed_signal}
  Score macro: {fmt_score(a.macro_score)}

━━━━━━━━━━━━━━━━━━━━
📡 <b>DOMINANCE</b>
  BTC Dominance: {a.dominance}% ({a.dominance_signal})
{alt_hint}
{scenario_block}
{stv_block}
{opinion_block}

━━━━━━━━━━━━━━━━━━━━
🧠 <b>TỔNG SCORE: {fmt_score(a.overall_score)}</b>

━━━━━━━━━━━━━━━━━━━━
{a.recommendation_emoji} <b>KHUYẾN NGHỊ: {a.recommendation}</b>
{entry_block}

<b>Lý do nên MUA / DCA:</b>
{buy_block}

<b>Rủi ro cần lưu ý:</b>
{risk_block}

<b>Vùng hành động:</b>
{dca_block}

━━━━━━━━━━━━━━━━━━━━
⚠️ <i>Đây là phân tích tham khảo, không phải lời khuyên đầu tư. Tự chịu trách nhiệm với quyết định của mình.</i>
""".strip()

    return msg


def build_alert_message(a: BTCAnalysis, alert_type: str, timestamp: str) -> str:
    """
    Alert đột xuất khi giá thay đổi mạnh.
    alert_type: "DUMP" hoặc "PUMP"
    """
    if alert_type == "DUMP":
        header = f"🚨 <b>BTC DUMP ALERT</b> — {fmt_pct(a.change_24h)} trong 24H"
        note   = "Giá giảm mạnh. Đây có thể là cơ hội DCA nếu thesis còn nguyên."
    else:
        header = f"🚀 <b>BTC PUMP ALERT</b> — {fmt_pct(a.change_24h)} trong 24H"
        note   = "Giá tăng mạnh. Cẩn thận FOMO — xem lại cycle phase và MVRV proxy."

    msg = f"""
{header}
🕐 {timestamp}

💰 Giá hiện tại: {fmt_price(a.price)}
📐 Trend: {a.trend_structure}
🔄 Cycle: {a.cycle_phase} | MVRV proxy: {a.mvrv_proxy_score}/100
😨 Fear & Greed: {a.fear_greed} ({a.fear_greed_label})

{a.recommendation_emoji} Khuyến nghị hiện tại: <b>{a.recommendation}</b>

📌 {note}
""".strip()

    return msg


def send_telegram(message: str) -> bool:
    """
    Gửi message tới Telegram. Trả về True nếu thành công.
    """
    if TELEGRAM_BOT_TOKEN == "YOUR_BOT_TOKEN":
        print("\n[Telegram] Chưa cấu hình token — in ra console thay thế:")
        print("=" * 60)
        print(message)
        print("=" * 60)
        return True

    url  = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {
        "chat_id":    TELEGRAM_CHAT_ID,
        "text":       message,
        "parse_mode": "HTML",
    }
    try:
        r = requests.post(url, data=data, timeout=15)
        r.raise_for_status()
        print("[Telegram] Gửi thành công ✅")
        return True
    except Exception as e:
        print(f"[Telegram] Lỗi: {e}")
        return False
