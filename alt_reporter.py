"""
reporter.py
Module 5: Format kết quả phân tích và gửi Telegram.
Gửi:
  - Summary report: top coin của đợt scan
  - Individual report: chi tiết từng coin
"""

import requests
from alt_scorer import ScoredCoin
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID


def fmt_price(n: float) -> str:
    if n >= 1:
        return f"${n:,.3f}"
    elif n >= 0.01:
        return f"${n:,.4f}"
    else:
        return f"${n:,.6f}"

def fmt_mc(n: float) -> str:
    if n >= 1e9:
        return f"${n/1e9:.2f}B"
    return f"${n/1e6:.0f}M"

def fmt_pct(n: float) -> str:
    arrow = "📈" if n >= 0 else "📉"
    return f"{arrow}{n:+.1f}%"

def action_emoji(action: str) -> str:
    return {"ACCUMULATE": "🟢", "WATCH": "🟡", "AVOID": "🔴"}.get(action, "⚪")

def score_bar(score: int) -> str:
    """Hiển thị score dạng visual bar."""
    filled = round(score / 10)
    bar    = "█" * filled + "░" * (10 - filled)
    color  = "🟢" if score >= 70 else "🟡" if score >= 50 else "🔴"
    return f"{color} {bar} {score}/100"


def build_summary_message(results: list[dict], timestamp: str, total_scanned: int) -> str:
    """
    Summary ngắn gọn: danh sách top coin đợt scan này.
    Gửi trước, sau đó gửi chi tiết từng coin.
    """
    lines = [
        f"🔍 <b>ALT SCANNER REPORT</b>",
        f"🕐 {timestamp}",
        f"📊 Đã quét: {total_scanned} coin → {len(results)} coin đáng chú ý",
        "━━━━━━━━━━━━━━━━━━━━",
    ]

    for i, r in enumerate(results, 1):
        sc       = r["scored_coin"]
        analysis = r["analysis"]
        action   = analysis.get("action", "WATCH")
        coin     = sc.coin

        lines.append(
            f"{i}. {action_emoji(action)} <b>{coin.symbol}</b> "
            f"— {sc.total_score}/100 — {fmt_pct(coin.change_7d)} 7D "
            f"— <i>{action}</i>"
        )

    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("Chi tiết từng coin sẽ gửi tiếp theo ↓")

    return "\n".join(lines)


def build_coin_detail_message(result: dict) -> str:
    """
    Chi tiết đầy đủ cho 1 coin.
    """
    sc       = result["scored_coin"]
    analysis = result["analysis"]
    coin     = sc.coin
    action   = analysis.get("action", "WATCH")

    # Score breakdown
    bd = sc.score_breakdown
    bd_str = (
        f"Narrative {bd.get('Narrative',0)} | "
        f"Momentum {bd.get('Momentum',0)} | "
        f"Volume {bd.get('Volume',0)} | "
        f"Tokenomics {bd.get('Tokenomics',0)} | "
        f"Sentiment {bd.get('Sentiment',0)} | "
        f"Bonus {bd.get('Bonus',0)}"
    )

    # Catalyst list
    catalysts = analysis.get("catalyst", [])
    catalyst_str = "\n".join(f"  ⚡ {c}" for c in catalysts)

    # Risks list
    risks = analysis.get("risks", [])
    risk_str = "\n".join(f"  ⚠️ {r}" for r in risks)

    # Upside
    upside = analysis.get("upside", {})
    upside_str = (
        f"  Conservative: {upside.get('conservative','?')}\n"
        f"  Bull case:    {upside.get('bull_case','?')}\n"
        f"  Condition:    {upside.get('condition','?')}"
    )

    # CMC cross-check block
    if coin.cmc_price > 0:
        cmc_status = "⚠️ <b>Lệch data CMC</b>" if coin.has_discrepancy else "✅ CMC khớp"
        cmc_block = f"\n🔎 Cross-check: {cmc_status}"
        if coin.has_discrepancy:
            for note in coin.discrepancy_notes:
                cmc_block += f"\n  • {note}"
    else:
        cmc_block = "\n🔎 Cross-check: CMC không có data"

    msg = f"""
{action_emoji(action)} <b>{coin.name} ({coin.symbol})</b> — {action}

💰 Giá: {fmt_price(coin.price)}
📦 Market Cap: {fmt_mc(coin.market_cap)} | Volume: {fmt_mc(coin.volume_24h)}
📈 24H: {fmt_pct(coin.change_24h)} | 7D: {fmt_pct(coin.change_7d)} | 30D: {fmt_pct(coin.change_30d)}
🔥 Volume spike: {coin.volume_spike:.1f}x | FDV/MC: {coin.fdv_mc_ratio:.1f}x
🏷 Narrative: {sc.narrative_label}{cmc_block}

⭐ Score: {score_bar(sc.total_score)}
<i>{bd_str}</i>

━━━━━━━━━━━━━━━━━━━━
🧠 <b>Thesis:</b>
{analysis.get("thesis", "N/A")}

⚡ <b>Catalyst:</b>
{catalyst_str}

🎯 <b>Upside target:</b>
{upside_str}

⚠️ <b>Rủi ro:</b>
{risk_str}

❌ <b>Invalidation:</b>
{analysis.get("invalidation", "N/A")}

━━━━━━━━━━━━━━━━━━━━
{action_emoji(action)} <b>Action: {action}</b>
{analysis.get("action_reason", "")}

📌 <b>DCA note:</b>
{analysis.get("dca_note", "N/A")}
""".strip()

    return msg


def send_telegram(message: str, silent: bool = False) -> bool:
    """Gửi message lên Telegram."""
    if TELEGRAM_BOT_TOKEN == "YOUR_BOT_TOKEN":
        print("\n[Telegram] Chưa cấu hình — in console:")
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


def send_full_report(results: list[dict], timestamp: str, total_scanned: int):
    """
    Gửi toàn bộ report:
    1. Summary message
    2. Chi tiết từng coin (gửi từng message riêng)
    """
    if not results:
        send_telegram(
            f"🔍 <b>ALT SCANNER</b> — {timestamp}\n"
            f"Không tìm thấy coin nào vượt ngưỡng trong đợt scan này."
        )
        return

    # Gửi summary
    summary = build_summary_message(results, timestamp, total_scanned)
    send_telegram(summary)

    # Gửi chi tiết từng coin
    import time
    for r in results:
        detail = build_coin_detail_message(r)
        send_telegram(detail)
        time.sleep(0.5)  # tránh flood Telegram

    print(f"[Reporter] Đã gửi {1 + len(results)} messages lên Telegram.")
