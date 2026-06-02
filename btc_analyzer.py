"""
analyzer.py
Tính toán tất cả chỉ số để đánh giá BTC:
  - MA50W, MA200W, khoảng cách giá / MA
  - Market structure (HH/HL)
  - MVRV proxy (dùng ATH distance)
  - Dominance trend
  - Macro score (DXY + Fear&Greed)
  - BUY RECOMMENDATION với logic rõ ràng
"""

import pandas as pd
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class BTCAnalysis:
    # ── Raw numbers ──────────────────────────────────────────
    price:              float = 0.0
    market_cap:         float = 0.0
    volume_24h:         float = 0.0
    change_24h:         float = 0.0
    change_7d:          float = 0.0
    change_30d:         float = 0.0
    ath_usd:            float = 0.0
    ath_change_pct:     float = 0.0   # âm = bao nhiêu % dưới ATH

    # ── Moving Averages ──────────────────────────────────────
    ma50w:              float = 0.0
    ma200w:             float = 0.0
    price_vs_ma50w_pct: float = 0.0   # % giá so với MA50W
    price_vs_ma200w_pct:float = 0.0   # % giá so với MA200W

    # ── Market Structure ─────────────────────────────────────
    trend_structure:    str   = "UNKNOWN"   # UPTREND / DOWNTREND / SIDEWAYS
    structure_detail:   str   = ""

    # ── On-chain Proxy ───────────────────────────────────────
    cycle_phase:        str   = "UNKNOWN"   # EARLY / MID / LATE / PEAK / BEAR
    cycle_detail:       str   = ""
    mvrv_proxy_score:   int   = 0           # 0-100, cao = đắt

    # ── Dominance ────────────────────────────────────────────
    dominance:          float = 0.0
    dominance_signal:   str   = ""   # RISING / FALLING / STABLE
    altseason_signal:   str   = ""

    # ── Macro ────────────────────────────────────────────────
    dxy:                Optional[float] = None
    dxy_change_5d:      Optional[float] = None
    dxy_signal:         str   = ""
    fear_greed:         int   = 0
    fear_greed_label:   str   = ""
    fear_greed_signal:  str   = ""

    # ── Composite Scores ─────────────────────────────────────
    technical_score:    int   = 0    # 0-100
    macro_score:        int   = 0    # 0-100
    cycle_score:        int   = 0    # 0-100
    overall_score:      int   = 0    # 0-100

    # ── BUY RECOMMENDATION ───────────────────────────────────
    recommendation:     str   = ""   # STRONG BUY / BUY / WATCH / AVOID / DANGER
    recommendation_emoji: str = ""
    buy_reasoning:      list  = field(default_factory=list)   # lý do nên mua
    risk_reasoning:     list  = field(default_factory=list)   # lý do rủi ro
    dca_zone_low:       float = 0.0
    dca_zone_high:      float = 0.0
    invalidation_price: float = 0.0


def calculate_moving_averages(weekly_df: pd.DataFrame, current_price: float) -> dict:
    """Tính MA50W và MA200W từ dữ liệu nến weekly."""
    if weekly_df.empty or len(weekly_df) < 50:
        return {"ma50w": 0, "ma200w": 0, "vs_ma50w": 0, "vs_ma200w": 0}

    closes = weekly_df["close"]
    ma50w  = closes.rolling(50).mean().iloc[-1]
    ma200w = closes.rolling(200).mean().iloc[-1] if len(weekly_df) >= 200 else closes.rolling(len(weekly_df)).mean().iloc[-1]

    vs_ma50w  = ((current_price - ma50w)  / ma50w)  * 100
    vs_ma200w = ((current_price - ma200w) / ma200w) * 100

    return {
        "ma50w":      round(float(ma50w),  0),
        "ma200w":     round(float(ma200w), 0),
        "vs_ma50w":   round(float(vs_ma50w),  1),
        "vs_ma200w":  round(float(vs_ma200w), 1),
    }


def analyze_market_structure(weekly_df: pd.DataFrame) -> tuple[str, str]:
    """
    Phân tích cấu trúc thị trường dựa trên HH/HL (higher high / higher low).
    Nhìn 8 cây nến gần nhất (8 tuần).
    """
    if weekly_df.empty or len(weekly_df) < 10:
        return "UNKNOWN", "Không đủ dữ liệu"

    recent = weekly_df.tail(10)
    highs  = recent["high"].tolist()
    lows   = recent["low"].tolist()

    # So sánh nửa trước và nửa sau
    mid = len(highs) // 2
    higher_highs = highs[-1] > highs[mid]
    higher_lows  = lows[-1]  > lows[mid]
    lower_highs  = highs[-1] < highs[mid]
    lower_lows   = lows[-1]  < lows[mid]

    if higher_highs and higher_lows:
        return "UPTREND", "HH + HL xác nhận — trend tăng rõ ràng"
    elif lower_highs and lower_lows:
        return "DOWNTREND", "LH + LL xác nhận — trend giảm"
    elif higher_highs and not higher_lows:
        return "UPTREND", "Higher High nhưng HL chưa rõ — uptrend yếu, cần theo dõi"
    else:
        return "SIDEWAYS", "Không có HH/HL rõ ràng — đang tích lũy hoặc sideway"


def analyze_cycle_phase(price: float, ma200w: float, ath: float, ath_change_pct: float) -> tuple[str, str, int]:
    """
    Ước tính phase chu kỳ BTC bằng proxy đơn giản:
    - Khoảng cách so với MA200W
    - Khoảng cách so với ATH

    Trả về: (phase, detail, mvrv_proxy_score 0-100)
    """
    # % dưới ATH (ath_change_pct là âm, ví dụ -30 = còn -30% dưới ATH)
    pct_below_ath = abs(ath_change_pct)   # dương hóa

    # % trên MA200W
    pct_above_ma200 = ((price - ma200w) / ma200w) * 100 if ma200w > 0 else 0

    # MVRV proxy: kết hợp 2 metric trên → 0 (rẻ) đến 100 (đắt)
    # Giá gần ATH + xa MA200W nhiều → score cao → nguy hiểm
    ath_score  = max(0, min(100, 100 - pct_below_ath * 1.5))   # 0% dưới ATH = 100đ
    ma_score   = max(0, min(100, pct_above_ma200 * 1.2))        # 80% trên MA200W = 100đ
    mvrv_proxy = int((ath_score * 0.6 + ma_score * 0.4))

    # Phase
    if pct_below_ath > 60:
        phase  = "BEAR"
        detail = f"Giá còn {pct_below_ath:.0f}% dưới ATH — vùng bear market sâu"
    elif pct_below_ath > 35:
        phase  = "EARLY_BULL"
        detail = f"Giá còn {pct_below_ath:.0f}% dưới ATH — early bull, accumulation zone"
    elif pct_below_ath > 15:
        phase  = "MID_BULL"
        detail = f"Giá còn {pct_below_ath:.0f}% dưới ATH — mid bull cycle, còn dư địa"
    elif pct_below_ath > 5:
        phase  = "LATE_BULL"
        detail = f"Giá chỉ còn {pct_below_ath:.0f}% dưới ATH — late bull, cẩn thận rủi ro"
    else:
        phase  = "PEAK_ZONE"
        detail = f"Giá gần ATH ({pct_below_ath:.0f}% dưới ATH) — vùng đỉnh, rủi ro cao"

    return phase, detail, mvrv_proxy


def analyze_dominance(dominance: float) -> tuple[str, str]:
    """
    Đánh giá BTC dominance và implication với altcoin.
    Không có historical data nên dùng ngưỡng tuyệt đối.
    """
    if dominance > 58:
        signal = "RISING_STRONG"
        alt    = "Dòng tiền đang vào BTC mạnh — altcoin yếu, chưa phải lúc rotate"
    elif dominance > 52:
        signal = "RISING"
        alt    = "BTC đang chiếm ưu thế — altseason chưa đến"
    elif dominance > 46:
        signal = "STABLE"
        alt    = "Dominance trung tính — altcoin và BTC đang cân bằng"
    elif dominance > 40:
        signal = "FALLING"
        alt    = "Dominance đang giảm — dòng tiền rotate sang alt, altseason có thể đến"
    else:
        signal = "FALLING_STRONG"
        alt    = "Dominance rất thấp — altseason mạnh đang diễn ra"

    return signal, alt


def analyze_macro(dxy: Optional[float], dxy_change: Optional[float],
                  fg_value: int, fg_label: str) -> tuple[str, str, int]:
    """
    Đánh giá macro: DXY + Fear&Greed.
    Trả về: (dxy_signal, fg_signal, macro_score 0-100)
    """
    # DXY signal
    if dxy_change is None:
        dxy_signal = "N/A"
        dxy_score  = 50
    elif dxy_change < -1.5:
        dxy_signal = "Dollar yếu rõ rệt → tốt cho BTC ✅"
        dxy_score  = 80
    elif dxy_change < 0:
        dxy_signal = "Dollar nhẹ yếu → trung tính tốt cho BTC"
        dxy_score  = 60
    elif dxy_change < 1.5:
        dxy_signal = "Dollar tăng nhẹ → trung tính"
        dxy_score  = 45
    else:
        dxy_signal = "Dollar mạnh → áp lực lên BTC ⚠️"
        dxy_score  = 20

    # Fear & Greed signal
    if fg_value is None:
        fg_signal = "N/A"
        fg_score  = 50
    elif fg_value <= 20:
        fg_signal = "Extreme Fear → đây thường là vùng mua tốt ✅"
        fg_score  = 90
    elif fg_value <= 40:
        fg_signal = "Fear → thị trường đang sợ, cơ hội DCA ✅"
        fg_score  = 75
    elif fg_value <= 60:
        fg_signal = "Neutral → không tham không sợ"
        fg_score  = 55
    elif fg_value <= 80:
        fg_signal = "Greed → cẩn thận, đám đông đang tham"
        fg_score  = 35
    else:
        fg_signal = "Extreme Greed → rủi ro cao, có thể sắp điều chỉnh ⚠️"
        fg_score  = 15

    macro_score = int(dxy_score * 0.4 + fg_score * 0.6)
    return dxy_signal, fg_signal, macro_score


def generate_recommendation(analysis: BTCAnalysis) -> tuple[str, str, list, list, float, float, float]:
    """
    Tổng hợp tất cả signal để đưa ra lời khuyên mua/không mua.
    
    Logic:
    - STRONG BUY: score cao + cycle early/mid + macro tốt
    - BUY:        score khá + không có red flag lớn
    - WATCH:      mixed signal, nên chờ thêm
    - AVOID:      cycle late/peak hoặc macro xấu
    - DANGER:     multiple red flags
    
    Trả về: (recommendation, emoji, buy_reasons, risk_reasons, dca_low, dca_high, invalidation)
    """
    buy_reasons  = []
    risk_reasons = []

    score = analysis.overall_score
    phase = analysis.cycle_phase
    trend = analysis.trend_structure
    fg    = analysis.fear_greed
    price = analysis.price

    # ── Tích điểm tín hiệu dương ──────────────────────────
    if phase in ("EARLY_BULL", "BEAR"):
        buy_reasons.append("Chu kỳ còn sớm — nhiều dư địa tăng trước ATH")
    if phase == "MID_BULL":
        buy_reasons.append("Mid bull cycle — thường là giai đoạn tăng tốt nhất")
    if trend == "UPTREND":
        buy_reasons.append("Market structure uptrend (HH+HL) xác nhận")
    if analysis.price_vs_ma200w_pct > 0:
        buy_reasons.append(f"Giá trên MA200W ({analysis.price_vs_ma200w_pct:+.1f}%) — bull market còn nguyên")
    if fg is not None and fg <= 40:
        buy_reasons.append(f"Fear & Greed = {fg} ({analysis.fear_greed_label}) — thị trường đang sợ, lịch sử thường là cơ hội")
    if analysis.dxy_change_5d is not None and analysis.dxy_change_5d < 0:
        buy_reasons.append("Dollar đang yếu — tốt cho tài sản rủi ro như BTC")
    if analysis.change_7d > 5:
        buy_reasons.append(f"Momentum 7D tốt (+{analysis.change_7d:.1f}%)")
    if analysis.dominance_signal in ("FALLING", "FALLING_STRONG"):
        buy_reasons.append("BTC dominance giảm → dấu hiệu sắp có altseason")

    # ── Tích điểm tín hiệu âm ─────────────────────────────
    if phase in ("LATE_BULL", "PEAK_ZONE"):
        risk_reasons.append("Chu kỳ muộn — rủi ro điều chỉnh sâu tăng")
    if phase == "PEAK_ZONE":
        risk_reasons.append("Giá gần ATH — lịch sử thường xảy ra pullback mạnh")
    if trend == "DOWNTREND":
        risk_reasons.append("Market structure downtrend — không nên bắt đáy")
    if fg is not None and fg >= 75:
        risk_reasons.append(f"Extreme Greed ({fg}) — đám đông đang tham, cẩn thận")
    if analysis.dxy_change_5d is not None and analysis.dxy_change_5d > 1.5:
        risk_reasons.append("Dollar mạnh — áp lực lên BTC")
    if analysis.change_24h < -5:
        risk_reasons.append(f"Dump mạnh 24h ({analysis.change_24h:.1f}%) — cần xác nhận thêm")
    if analysis.mvrv_proxy_score > 75:
        risk_reasons.append(f"MVRV proxy cao ({analysis.mvrv_proxy_score}/100) — BTC đang đắt so với lịch sử")

    # ── DCA Zone: dựa trên MA50W và MA200W ────────────────
    if analysis.ma50w > 0 and analysis.ma200w > 0:
        dca_low  = round(analysis.ma50w  * 0.95, 0)   # 5% dưới MA50W
        dca_high = round(analysis.ma50w  * 1.02, 0)   # 2% trên MA50W
        invalidation = round(analysis.ma200w * 0.97, 0)  # 3% dưới MA200W
    else:
        dca_low  = round(price * 0.90, 0)
        dca_high = round(price * 0.97, 0)
        invalidation = round(price * 0.80, 0)

    # ── Short-term weakness check ──────────────────────────
    # Giá đang yếu ngắn hạn: giảm 24h + chưa có trend rõ
    short_term_weak = (
        analysis.change_24h < -2.0 or
        analysis.trend_structure in ("DOWNTREND", "SIDEWAYS") or
        analysis.price_vs_ma50w_pct < -5.0   # giá dưới MA50W khá xa
    )

    # ── Tính entry zone thực tế ────────────────────────────
    # Nếu giá đang yếu → entry zone = vùng support quan trọng phía dưới
    if short_term_weak and analysis.ma50w > 0:
        # Entry zone: quanh MA50W ± 3%
        entry_low  = round(analysis.ma50w * 0.97, -2)
        entry_high = round(analysis.ma50w * 1.01, -2)
    elif short_term_weak:
        entry_low  = round(price * 0.93, -2)
        entry_high = round(price * 0.97, -2)
    else:
        entry_low  = dca_low
        entry_high = dca_high

    # ── Quyết định cuối ────────────────────────────────────
    red_flags   = len(risk_reasons)
    green_flags = len(buy_reasons)

    if phase == "DANGER" or (red_flags >= 4):
        rec            = "DANGER"
        emoji          = "🚨"
        wait_for_level = False
    elif phase in ("PEAK_ZONE", "LATE_BULL") and red_flags >= 3:
        rec            = "AVOID"
        emoji          = "🔴"
        wait_for_level = False
    elif score >= 72 and green_flags >= 4 and red_flags <= 1 and not short_term_weak:
        rec            = "STRONG BUY"
        emoji          = "🟢🟢"
        wait_for_level = False
    elif score >= 60 and green_flags >= 3 and red_flags <= 2 and not short_term_weak:
        rec            = "BUY"
        emoji          = "🟢"
        wait_for_level = False
    elif score >= 60 and short_term_weak:
        # Thesis tốt nhưng giá đang yếu → WAIT_FOR_LEVEL
        rec            = "WAIT_FOR_LEVEL"
        emoji          = "⏳"
        wait_for_level = True
    elif score >= 45 or (green_flags >= 2 and red_flags <= 2):
        rec            = "WATCH"
        emoji          = "🟡"
        wait_for_level = False
    else:
        rec            = "AVOID"
        emoji          = "🔴"
        wait_for_level = False

    return rec, emoji, buy_reasons, risk_reasons, dca_low, dca_high, invalidation, wait_for_level, entry_low, entry_high


def run_analysis(raw_data: dict) -> BTCAnalysis:
    """
    Entry point chính — nhận raw data từ data_fetcher, trả về BTCAnalysis đầy đủ.
    """
    a = BTCAnalysis()

    market    = raw_data.get("market", {})
    weekly_df = raw_data.get("weekly_df", pd.DataFrame())
    dxy_data  = raw_data.get("dxy", {})
    fg_data   = raw_data.get("fear_greed", {})
    dominance = raw_data.get("dominance", 0.0)

    # ── Gán raw numbers ───────────────────────────────────
    a.price          = market.get("price_usd", 0)
    a.market_cap     = market.get("market_cap_usd", 0)
    a.volume_24h     = market.get("volume_24h_usd", 0)
    a.change_24h     = market.get("change_24h_pct", 0)
    a.change_7d      = market.get("change_7d_pct", 0)
    a.change_30d     = market.get("change_30d_pct", 0)
    a.ath_usd        = market.get("ath_usd", 0)
    a.ath_change_pct = market.get("ath_change_pct", 0)
    a.dominance      = dominance

    # ── Moving Averages ───────────────────────────────────
    ma = calculate_moving_averages(weekly_df, a.price)
    a.ma50w              = ma["ma50w"]
    a.ma200w             = ma["ma200w"]
    a.price_vs_ma50w_pct  = ma["vs_ma50w"]
    a.price_vs_ma200w_pct = ma["vs_ma200w"]

    # ── Market Structure ──────────────────────────────────
    a.trend_structure, a.structure_detail = analyze_market_structure(weekly_df)

    # ── Cycle Phase ───────────────────────────────────────
    a.cycle_phase, a.cycle_detail, a.mvrv_proxy_score = analyze_cycle_phase(
        a.price, a.ma200w, a.ath_usd, a.ath_change_pct
    )

    # ── Dominance ─────────────────────────────────────────
    a.dominance_signal, a.altseason_signal = analyze_dominance(dominance)

    # ── Macro ─────────────────────────────────────────────
    a.dxy            = dxy_data.get("dxy")
    a.dxy_change_5d  = dxy_data.get("dxy_change_5d_pct")
    a.fear_greed     = fg_data.get("fg_value", 0) or 0
    a.fear_greed_label = fg_data.get("fg_label", "N/A")

    dxy_sig, fg_sig, macro_score = analyze_macro(
        a.dxy, a.dxy_change_5d, a.fear_greed, a.fear_greed_label
    )
    a.dxy_signal        = dxy_sig
    a.fear_greed_signal = fg_sig
    a.macro_score       = macro_score

    # ── Technical Score (0-100) ───────────────────────────
    tech = 50  # base
    if a.trend_structure == "UPTREND":   tech += 20
    elif a.trend_structure == "DOWNTREND": tech -= 20
    if a.price_vs_ma50w_pct > 0:   tech += 10
    if a.price_vs_ma200w_pct > 0:  tech += 15
    if a.change_7d > 5:            tech += 5
    elif a.change_7d < -10:        tech -= 10
    a.technical_score = max(0, min(100, tech))

    # ── Cycle Score (0-100) ───────────────────────────────
    cycle_map = {
        "BEAR":       85,   # rẻ nhất, mua tốt nhất nếu hold dài
        "EARLY_BULL": 80,
        "MID_BULL":   65,
        "LATE_BULL":  35,
        "PEAK_ZONE":  10,
        "UNKNOWN":    50,
    }
    a.cycle_score = cycle_map.get(a.cycle_phase, 50)
    # Điều chỉnh thêm bằng MVRV proxy
    a.cycle_score = int(a.cycle_score * (1 - a.mvrv_proxy_score / 200))

    # ── Overall Score ─────────────────────────────────────
    a.overall_score = int(
        a.technical_score * 0.35 +
        a.cycle_score     * 0.40 +
        a.macro_score     * 0.25
    )

    # ── BUY RECOMMENDATION ────────────────────────────────
    (a.recommendation,
     a.recommendation_emoji,
     a.buy_reasoning,
     a.risk_reasoning,
     a.dca_zone_low,
     a.dca_zone_high,
     a.invalidation_price,
     a.wait_for_level,
     a.entry_zone_low,
     a.entry_zone_high) = generate_recommendation(a)

    # Build entry condition text
    if a.wait_for_level and a.entry_zone_low > 0:
        a.entry_condition = (
            f"Chờ giá về vùng ${a.entry_zone_low:,.0f}–${a.entry_zone_high:,.0f} "
            f"và có nến xác nhận mới xem xét mua"
        )

    return a


# ════════════════════════════════════════════════════════════
#  GPT SCENARIO GENERATOR
# ════════════════════════════════════════════════════════════

def generate_scenario_analysis(a: BTCAnalysis, openai_api_key: str = "") -> BTCAnalysis:
    """
    Gọi GPT để generate:
      - Kịch bản tăng / giảm ngắn hạn
      - Góc nhìn ngắn hạn
      - Quan điểm xu hướng (1 câu)

    Chỉ gọi nếu có OPENAI_API_KEY. Nếu không có → dùng fallback logic.
    """
    import os, json

    # ── Fallback nếu không có key ─────────────────────────────
    if not openai_api_key or not openai_api_key.startswith("sk-"):
        openai_api_key = os.environ.get("OPENAI_API_KEY", "")

    if not openai_api_key.startswith("sk-"):
        return _fallback_scenario(a)

    # ── Build prompt ─────────────────────────────────────────
    price_action = "giảm" if a.change_24h < 0 else "tăng"
    vs_ma50  = "trên" if a.price_vs_ma50w_pct > 0 else "dưới"
    vs_ma200 = "trên" if a.price_vs_ma200w_pct > 0 else "dưới"

    prompt = f"""
Bạn là trader phân tích BTC ngắn hạn, viết theo phong cách thực chiến, ngắn gọn, không hype.

Dữ liệu BTC hiện tại:
- Giá: ${a.price:,.0f}
- 24H: {a.change_24h:+.2f}% ({price_action})
- 7D:  {a.change_7d:+.2f}%
- Trend weekly: {a.trend_structure} — {a.structure_detail}
- MA50W:  ${a.ma50w:,.0f} (giá đang {vs_ma50} {abs(a.price_vs_ma50w_pct):.1f}%)
- MA200W: ${a.ma200w:,.0f} (giá đang {vs_ma200} {abs(a.price_vs_ma200w_pct):.1f}%)
- Cycle phase: {a.cycle_phase} — {a.cycle_detail}
- Fear & Greed: {a.fear_greed} ({a.fear_greed_label})
- BTC Dominance: {a.dominance}%
- DXY: {a.dxy} ({a.dxy_change_5d:+.2f}% 5D)
- Overall score: {a.overall_score}/100
- Recommendation: {a.recommendation}

Viết report JSON (KHÔNG thêm gì ngoài JSON):
{{
  "scenario_bearish": "Mô tả kịch bản giảm — điều gì xảy ra nếu phe bán thắng (2-3 câu, nêu vùng giá cụ thể)",
  "scenario_bullish": "Mô tả kịch bản tăng — điều gì xảy ra nếu phe mua quay lại (2-3 câu, nêu vùng giá cụ thể)",
  "short_term_view": "Góc nhìn ngắn hạn 1-3 ngày: nên làm gì, chờ gì, tránh gì (3-4 câu thực tế)",
  "trend_opinion": "Quan điểm 1 câu: Xu hướng Tăng / Giảm / Sideway + lý do ngắn gọn",
  "trend_direction": "UP hoặc DOWN hoặc SIDE"
}}

Phong cách: thực tế, nêu vùng giá cụ thể ($), không nói chung chung.
""".strip()

    try:
        from openai import OpenAI
        client   = OpenAI(api_key=openai_api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
            max_tokens=600,
        )
        raw = response.choices[0].message.content.strip()
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0].strip()

        data = json.loads(raw)
        a.scenario_bearish = data.get("scenario_bearish", "")
        a.scenario_bullish = data.get("scenario_bullish", "")
        a.short_term_view  = data.get("short_term_view", "")
        a.trend_opinion    = data.get("trend_opinion", "")
        direction          = data.get("trend_direction", "SIDE")
        a.trend_emoji      = "📈" if direction == "UP" else "📉" if direction == "DOWN" else "➡️"
        # Ghi đè entry_condition nếu GPT có output tốt hơn
        gpt_entry = data.get("entry_condition", "")
        if gpt_entry:
            a.entry_condition = gpt_entry
        print("[BTC Scenario] GPT generate OK")

    except Exception as e:
        print(f"[BTC Scenario] GPT lỗi: {e} — dùng fallback")
        return _fallback_scenario(a)

    return a


def _fallback_scenario(a: BTCAnalysis) -> BTCAnalysis:
    """Tự generate scenario từ data khi không có GPT."""
    price     = a.price
    ma50w     = a.ma50w or price * 0.85
    ma200w    = a.ma200w or price * 0.70
    support   = round(min(price * 0.95, ma50w), -2)
    resist    = round(price * 1.06, -2)
    breakdown = round(ma200w * 0.97, -2)

    is_down = a.change_24h < -1 or a.trend_structure == "DOWNTREND"

    if is_down:
        a.trend_emoji     = "📉"
        a.trend_opinion   = f"Xu Hướng Giảm — giá dưới MA50W và đang yếu, ưu tiên chờ xác nhận"
        a.scenario_bearish = (
            f"Nếu giá mất vùng ${support:,.0f}, phe bán sẽ tiếp tục kiểm soát. "
            f"Mục tiêu tiếp theo có thể là vùng MA200W ~${ma200w:,.0f}. "
            f"Mất ${breakdown:,.0f} thì xu hướng giảm được xác nhận rõ hơn."
        )
        a.scenario_bullish = (
            f"Nếu giá giữ được vùng ${support:,.0f} và xuất hiện nến đảo chiều, "
            f"có thể có nhịp hồi kỹ thuật lên vùng ${resist:,.0f}. "
            f"Cần volume xác nhận mới đáng tin cậy."
        )
        a.short_term_view = (
            f"BTC đang yếu trong ngắn hạn. Ưu tiên chờ phản ứng tại vùng ${support:,.0f} "
            f"thay vì bắt đáy sớm. Nếu xuất hiện nến từ chối giá rõ ràng thì mới cân nhắc. "
            f"Tránh vào lệnh khi giá đang rơi tự do."
        )
    else:
        a.trend_emoji     = "📈"
        a.trend_opinion   = f"Xu Hướng Tăng — giá trên MA50W, momentum tích cực"
        a.scenario_bullish = (
            f"Nếu giá giữ trên MA50W ~${ma50w:,.0f} và volume tiếp tục tốt, "
            f"mục tiêu tiếp theo là vùng ${resist:,.0f}. "
            f"Phá vùng này với volume → uptrend tiếp tục."
        )
        a.scenario_bearish = (
            f"Nếu giá mất vùng MA50W ~${ma50w:,.0f}, "
            f"nguy cơ pullback về ${support:,.0f}. "
            f"Cần theo dõi volume để xác định đây là điều chỉnh hay đảo chiều."
        )
        a.short_term_view = (
            f"BTC đang trong nhịp tích cực. Giữ trên MA50W là dấu hiệu tốt. "
            f"Vùng ${support:,.0f} là support gần nhất cần giữ. "
            f"Có thể DCA từng phần nếu giá pullback nhẹ về vùng này."
        )

    return a
