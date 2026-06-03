"""
alt_reporter.py
Module 5: Format kết quả phân tích và gửi Telegram.
"""

import time
import requests
from alt_scorer import ScoredCoin
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID


def fmt_price(n: float) -> str:
    if n >= 1000: return f"${n:,.2f}"
    if n >= 1:    return f"${n:,.3f}"
    if n >= 0.01: return f"${n:,.4f}"
    return f"${n:,.6f}"

def fmt_mc(n: float) -> str:
    if n >= 1e9: return f"${n/1e9:.2f}B"
    return f"${n/1e6:.0f}M"

def fmt_pct(n: float) -> str:
    arrow = "📈" if n >= 0 else "📉"
    return f"{arrow}{n:+.1f}%"

def action_emoji(action: str) -> str:
    return {
        "ACCUMULATE":     "🟢",
        "WAIT_FOR_LEVEL": "⏳",
        "WATCH":          "🟡",
        "AVOID":          "🔴",
    }.get(action, "⚪")

def score_bar(score: int) -> str:
    filled = round(score / 10)
    bar    = "█" * filled + "░" * (10 - filled)
    color  = "🟢" if score >= 70 else "🟡" if score >= 50 else "🔴"
    return f"{color} {bar} {score}/100"


def build_summary_message(results: list, timestamp: str, total_scanned: int) -> str:
    lines = [
        f"🔍 <b>ALT SCANNER REPORT</b>",
        f"🕐 {timestamp}",
        f"📊 Quét: {total_scanned} coin → {len(results)} coin đáng chú ý",
        "━━━━━━━━━━━━━━━━━━━━",
    ]
    for i, r in enumerate(results, 1):
        sc     = r["scored_coin"]
        an     = r["analysis"]
        action = an.get("action", "WATCH")
        coin   = sc.coin
        t1     = an.get("_target_1", sc.target_1)
        t1_str = f" → T1: {fmt_price(t1)}" if t1 > 0 else ""
        lines.append(
            f"{i}. {action_emoji(action)} <b>{coin.symbol}</b>"
            f" — {sc.total_score}/100"
            f" — {fmt_pct(coin.change_7d)} 7D"
            f"{t1_str}"
            f" — <i>{action}</i>"
        )
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("Chi tiết từng coin ↓")
    return "\n".join(lines)


def build_coin_detail_message(result: dict) -> str:
    sc     = result["scored_coin"]
    an     = result["analysis"]
    coin   = sc.coin
    action = an.get("action", "WATCH")

    # Score breakdown
    bd     = sc.score_breakdown
    bd_str = (
        f"Narrative {bd.get('Narrative',0)} | "
        f"Momentum {bd.get('Momentum',0)} | "
        f"Volume {bd.get('Volume',0)} | "
        f"Tokenomics {bd.get('Tokenomics',0)} | "
        f"Sentiment {bd.get('Sentiment',0)} | "
        f"Bonus {bd.get('Bonus',0)}"
    )

    # CMC cross-check
    cmc_block = ""
    if hasattr(coin, "cmc_price") and coin.cmc_price > 0:
        if coin.has_discrepancy:
            cmc_block = "\n🔎 Cross-check: ⚠️ <b>Lệch data CMC</b>"
            for note in coin.discrepancy_notes:
                cmc_block += f"\n  • {note}"
        else:
            cmc_block = "\n🔎 Cross-check: ✅ CMC khớp"

    # Social block
    social_lines = []
    if an.get("_is_cg_trending"):
        social_lines.append(f"🔥 Top #{an.get('_cg_trending_rank',0)} CoinGecko Trending")
    if an.get("_reddit_mentions", 0) > 0:
        social_lines.append(f"💬 Reddit 24h: {an['_reddit_mentions']} mentions")
    if an.get("_social_sentiment"):
        em = {"positive":"🟢","neutral":"🟡","negative":"🔴"}.get(an["_social_sentiment"],"⚪")
        social_lines.append(f"{em} Social: {an['_social_sentiment'].upper()} ({an.get('_social_score',0):+d}/100)")
    if an.get("social_highlight"):
        social_lines.append(f"📌 {an['social_highlight']}")
    social_block = ("\n\n🌐 <b>Social & News:</b>\n" + "\n".join(social_lines)) if social_lines else ""

    # Targets từ scorer (fallback) hoặc GPT override
    t1  = an.get("_target_1", sc.target_1)
    t2  = an.get("_target_2", sc.target_2)
    t3  = an.get("_target_3", sc.target_3)
    sup = an.get("_support",  sc.support_zone)
    res = an.get("_resistance", sc.resistance_zone)

    # Format target với % upside
    def _fmt_target(price_val, pct_val, label):
        if price_val <= 0: return f"  🎯 {label}: N/A"
        return f"  🎯 {label}: {fmt_price(price_val)} (+{pct_val:.0f}%)"

    targets_block = (
        _fmt_target(t1, sc.target_1_pct, "T1 conservative") + "\n" +
        _fmt_target(t2, sc.target_2_pct, "T2 mid target  ") + "\n" +
        _fmt_target(t3, sc.target_3_pct, "T3 bull case   ") + "\n" +
        f"  🛡 Stop loss: {fmt_price(sup)} (mất vùng này → cắt lỗ)"
    )

    # GPT targets override nếu có
    gpt_targets = an.get("targets", {})
    if gpt_targets and gpt_targets.get("t1"):
        targets_block = (
            f"  🎯 T1: {gpt_targets.get('t1', fmt_price(t1))}\n"
            f"  🎯 T2: {gpt_targets.get('t2', fmt_price(t2))}\n"
            f"  🎯 T3: {gpt_targets.get('t3', fmt_price(t3))}\n"
            f"  🛡 Stop: {gpt_targets.get('stop_loss', fmt_price(sup))}"
        )

    # Entry / Wait block
    entry_condition = an.get("entry_condition", sc.entry_condition)
    if action == "WAIT_FOR_LEVEL":
        entry_block = (
            f"\n━━━━━━━━━━━━━━━━━━━━"
            f"\n⏳ <b>CHƯA MUA NGAY — CHỜ VÙNG NÀY:</b>"
            f"\n  📍 {entry_condition}"
            f"\n  💡 Thesis dài hạn tốt nhưng price action đang yếu."
            f"\n     Chờ giá về vùng support + nến xác nhận mới vào."
        )
    else:
        entry_block = (
            f"\n📍 <b>Entry:</b> {entry_condition}"
        )

    # Kịch bản
    sc_bull = an.get("scenario_bullish", "")
    sc_bear = an.get("scenario_bearish", "")
    scenario_block = ""
    if sc_bull or sc_bear:
        scenario_block = (
            f"\n━━━━━━━━━━━━━━━━━━━━"
            f"\n🎯 <b>HAI KỊCH BẢN</b>"
            + (f"\n🟢 {sc_bull}" if sc_bull else "")
            + (f"\n🔴 {sc_bear}" if sc_bear else "")
        )

    # Short term view
    stv = an.get("short_term_view", "")
    stv_block = f"\n━━━━━━━━━━━━━━━━━━━━\n⚡ <b>GÓC NHÌN NGẮN HẠN</b>\n{stv}" if stv else ""

    # Catalysts + risks
    catalysts  = an.get("catalyst", [])
    risks      = an.get("risks", [])
    cat_str    = "\n".join(f"  ⚡ {c}" for c in catalysts)
    risk_str   = "\n".join(f"  ⚠️ {r}" for r in risks)

    msg = f"""
{action_emoji(action)} <b>{coin.name} ({coin.symbol})</b> — {action}

💰 Giá: {fmt_price(coin.price)}
📦 MC: {fmt_mc(coin.market_cap)} | Vol: {fmt_mc(coin.volume_24h)}
📈 1H: {fmt_pct(coin.change_1h)} | 24H: {fmt_pct(coin.change_24h)} | 7D: {fmt_pct(coin.change_7d)} | 30D: {fmt_pct(coin.change_30d)}
🔥 Vol spike: {coin.volume_spike:.1f}x | FDV/MC: {coin.fdv_mc_ratio:.1f}x
🏷 Narrative: {sc.narrative_label}{cmc_block}{social_block}

⭐ Score: {score_bar(sc.total_score)}
<i>{bd_str}</i>

━━━━━━━━━━━━━━━━━━━━
🧠 <b>Thesis:</b>
{an.get("thesis", "N/A")}

⚡ <b>Catalyst:</b>
{cat_str}

━━━━━━━━━━━━━━━━━━━━
🎯 <b>TARGET GIÁ CỤ THỂ:</b>
{targets_block}

⚠️ <b>Rủi ro:</b>
{risk_str}
{scenario_block}
{stv_block}

━━━━━━━━━━━━━━━━━━━━
{action_emoji(action)} <b>Action: {action}</b>
{an.get("action_reason", "")}
{entry_block}

━━━━━━━━━━━━━━━━━━━━
⚠️ <i>Phân tích tham khảo, không phải lời khuyên đầu tư.</i>
""".strip()

    return msg


def send_telegram(message: str, silent: bool = False) -> bool:
    if TELEGRAM_BOT_TOKEN == "YOUR_BOT_TOKEN":
        print("\n[Telegram] In console:")
        print("─" * 60)
        print(message)
        print("─" * 60)
        return True
    url  = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {
        "chat_id":              TELEGRAM_CHAT_ID,
        "text":                 message,
        "parse_mode":           "HTML",
        "disable_notification": silent,
    }
    try:
        r = requests.post(url, data=data, timeout=15)
        r.raise_for_status()
        return True
    except Exception as e:
        print(f"[Telegram] Lỗi: {e}")
        return False


def send_full_report(results: list, timestamp: str, total_scanned: int):
    if not results:
        send_telegram(
            f"🔍 <b>ALT SCANNER</b> — {timestamp}\n"
            f"Không tìm thấy coin nào vượt ngưỡng trong đợt scan này."
        )
        return
    summary = build_summary_message(results, timestamp, total_scanned)
    send_telegram(summary)
    for r in results:
        detail = build_coin_detail_message(r)
        send_telegram(detail)
        time.sleep(0.5)
    print(f"[Reporter] Đã gửi {1 + len(results)} messages.")
