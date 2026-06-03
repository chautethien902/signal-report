"""
alt_analyst.py
Module 4: Gọi OpenAI GPT để viết deep analysis cho coin đạt ngưỡng score.
GPT nhận market data + social context (news, Reddit, trending) để phân tích toàn diện hơn.
"""

import os
import json
import time
from alt_scorer import ScoredCoin
from config import OPENAI_API_KEY, CRYPTOPANIC_API_KEY
from social_fetcher import SocialContext, fetch_social_batch
import llm_client


def build_prompt(sc: ScoredCoin, social: SocialContext = None) -> str:
    coin  = sc.coin
    price = coin.price
    mc_b  = coin.market_cap / 1e9
    breakdown_str = " | ".join(f"{k}: {v}" for k, v in sc.score_breakdown.items())

    # Format target prices
    t1 = f"${sc.target_1:,.4f}" if sc.target_1 > 0 else "N/A"
    t2 = f"${sc.target_2:,.4f}" if sc.target_2 > 0 else "N/A"
    t3 = f"${sc.target_3:,.4f}" if sc.target_3 > 0 else "N/A"
    sup = f"${sc.support_zone:,.4f}" if sc.support_zone > 0 else "N/A"
    res = f"${sc.resistance_zone:,.4f}" if sc.resistance_zone > 0 else "N/A"

    # Entry zone
    if sc.wait_for_level:
        entry_hint = f"⚠️ Giá đang yếu ngắn hạn — entry zone: ${sc.entry_zone_low:,.4f}–${sc.entry_zone_high:,.4f}"
    else:
        entry_hint = f"Có thể DCA tại: ${sc.entry_zone_low:,.4f}–${price:,.4f}"

    # Social context block
    social_block = f"\n=== SOCIAL & NEWS ===\n{social.summary}\n" if (social and social.summary) else ""

    prompt = f"""
Bạn là trader phân tích crypto spot, viết theo phong cách thực chiến, có số liệu cụ thể, không hype.

=== MARKET DATA ===
Coin: {coin.name} ({coin.symbol})
Giá hiện tại: ${price:,.4f}
Market Cap: ${mc_b:.2f}B | Volume 24H: ${coin.volume_24h/1e6:.1f}M
FDV/MC: {coin.fdv_mc_ratio:.1f}x | Volume spike: {coin.volume_spike:.1f}x
Biến động: 1H {coin.change_1h:+.1f}% | 24H {coin.change_24h:+.1f}% | 7D {coin.change_7d:+.1f}% | 30D {coin.change_30d:+.1f}%
Narrative: {sc.narrative_label}
Score: {sc.total_score}/100 | {breakdown_str}

=== VÙNG GIÁ TÍNH SẴN ===
Support zone: {sup} | Resistance zone: {res}
Target 1 (conservative): {t1} | Target 2 (mid): {t2} | Target 3 (bull): {t3}
Entry gợi ý: {entry_hint}
{social_block}
=== YÊU CẦU ===
Viết phân tích theo phong cách trader thực chiến. Ví dụ tốt:
- "FET đang tích lũy quanh $1.20–1.25. Nếu break $1.35 với volume thì mở ra nhịp về $1.80."
- "Chờ giá về $1.10–1.15 (vùng support) và có nến đảo chiều mới DCA."
- "Không phá được $1.35 → giá nhiều khả năng test lại $1.00."

Chỉ trả về JSON, KHÔNG viết gì thêm:

{{
  "scenario_bullish": "Kịch bản tăng: mốc cần phá, target cụ thể bằng $, điều kiện (2-3 câu)",
  "scenario_bearish": "Kịch bản giảm: mốc mất, target giảm cụ thể, điều kiện (2-3 câu)",
  "short_term_view": "Góc nhìn 1-3 ngày: giá đang ở đâu, chờ gì, tránh gì (3-4 câu có số liệu)",
  "entry_condition": "Entry cụ thể: vùng giá $ nên vào, điều kiện xác nhận, cách chia nhỏ vốn",
  "targets": {{
    "t1": "{t1} (conservative — kháng cự gần nhất)",
    "t2": "{t2} (mid target — nếu momentum tốt)",
    "t3": "{t3} (bull case — nếu narrative bùng nổ)",
    "stop_loss": "Vùng ${sc.support_zone:,.4f} là invalidation — mất vùng này cắt lỗ"
  }},
  "thesis": "1-2 câu: tại sao coin này đáng chú ý, tích hợp news/social nếu có",
  "catalyst": ["catalyst 1", "catalyst 2", "catalyst 3"],
  "risks": ["rủi ro 1", "rủi ro 2"],
  "action": "ACCUMULATE hoặc WAIT_FOR_LEVEL hoặc WATCH hoặc AVOID",
  "action_reason": "1 câu giải thích action, có số liệu cụ thể",
  "social_highlight": "điều đáng chú ý nhất từ social/news (1 câu)"
}}

Rule:
- action = WAIT_FOR_LEVEL nếu giá đang yếu ngắn hạn nhưng thesis dài hạn vẫn tốt
- action = ACCUMULATE nếu setup tốt và giá ổn
- Luôn nêu $ cụ thể, không nói "vùng trên" hay "vùng dưới" chung chung
""".strip()

    return prompt


def analyze_coin(sc: ScoredCoin, social: SocialContext = None) -> dict:
    prompt = build_prompt(sc, social)
    try:
        raw_text = llm_client.call_llm(prompt, max_tokens=900, temperature=0.3)
        raw_text = raw_text.strip()
        if "```json" in raw_text:
            raw_text = raw_text.split("```json")[1].split("```")[0].strip()
        elif "```" in raw_text:
            raw_text = raw_text.split("```")[1].split("```")[0].strip()
        result = json.loads(raw_text)
        # Gắn thêm social meta + scorer targets vào result
        if social:
            result["_social_sentiment"]   = social.overall_sentiment
            result["_social_score"]       = social.sentiment_score
            result["_is_cg_trending"]     = social.is_cg_trending
            result["_cg_trending_rank"]   = social.cg_trending_rank
            result["_reddit_mentions"]    = social.reddit_mentions
        # Gắn targets từ scorer (GPT có thể override trong targets block)
        result["_target_1"]       = sc.target_1
        result["_target_2"]       = sc.target_2
        result["_target_3"]       = sc.target_3
        result["_support_zone"]   = sc.support_zone
        result["_wait_for_level"] = sc.wait_for_level
        result["_entry_zone_low"] = sc.entry_zone_low
        result["_entry_zone_high"]= sc.entry_zone_high
        return result
    except json.JSONDecodeError as e:
        print(f"[Analyst] JSON parse lỗi cho {sc.coin.symbol}: {e}")
        return _fallback_analysis(sc, social)
    except Exception as e:
        print(f"[Analyst] LLM lỗi cho {sc.coin.symbol}: {e}")
        return _fallback_analysis(sc, social)


def _fallback_analysis(sc: ScoredCoin, social: SocialContext = None) -> dict:
    coin  = sc.coin
    price = coin.price
    score = sc.total_score

    # Action logic
    if sc.wait_for_level and score >= 60:
        action        = "WAIT_FOR_LEVEL"
        action_reason = f"Thesis tốt nhưng giá đang yếu — chờ về ${sc.entry_zone_low:,.4f}–${sc.entry_zone_high:,.4f}"
    elif social and social.overall_sentiment == "negative" and score < 75:
        action        = "WATCH"
        action_reason = "Score khá nhưng sentiment tiêu cực — chờ xác nhận"
    elif score >= 75:
        action        = "ACCUMULATE"
        action_reason = f"Score cao — DCA từng phần tại ${sc.entry_zone_low:,.4f}–${price:,.4f}"
    elif score >= 60:
        action        = "WATCH"
        action_reason = "Setup đang hình thành, cần xác nhận thêm"
    else:
        action        = "AVOID"
        action_reason = "Chưa đủ tín hiệu mạnh"

    social_highlight = ""
    if social:
        if social.is_cg_trending:
            social_highlight = f"Đang top #{social.cg_trending_rank} CoinGecko Trending"
        elif social.reddit_mentions > 5:
            social_highlight = f"Được đề cập {social.reddit_mentions} lần trên Reddit 24h"
        elif social.overall_sentiment == "negative":
            social_highlight = "Sentiment xấu trên mạng xã hội — cần thận trọng"

    t1  = f"${sc.target_1:,.4f}" if sc.target_1 > 0 else "N/A"
    t2  = f"${sc.target_2:,.4f}" if sc.target_2 > 0 else "N/A"
    t3  = f"${sc.target_3:,.4f}" if sc.target_3 > 0 else "N/A"
    sup = f"${sc.support_zone:,.4f}" if sc.support_zone > 0 else "N/A"

    # Scenario
    res_zone = f"${sc.resistance_zone:,.4f}" if sc.resistance_zone > 0 else "N/A"
    if coin.change_24h < -2 or sc.wait_for_level:
        scenario_bullish = (
            f"Nếu giá giữ vùng {sup} và xuất hiện nến đảo chiều, "
            f"nhịp hồi về {res_zone} là khả thi. Break {res_zone} với volume → target {t1}."
        )
        scenario_bearish = (
            f"Mất vùng {sup} → phe bán tiếp tục kiểm soát, "
            f"có thể test thêm -{round(abs(coin.change_30d)*0.382, 1)}% nữa. "
            f"Invalidation khi mất {sup}."
        )
    else:
        scenario_bullish = (
            f"Giữ trên {sup} và break {res_zone} với volume → target {t1}, sau đó {t2}. "
            f"Bull case {t3} nếu narrative bùng nổ."
        )
        scenario_bearish = (
            f"Mất {sup} → pullback về vùng thấp hơn. "
            f"Chờ xác nhận lại structure trước khi xem xét mua lại."
        )

    p1 = sc.target_1_pct if hasattr(sc, "target_1_pct") else 0
    p2 = sc.target_2_pct if hasattr(sc, "target_2_pct") else 0
    p3 = sc.target_3_pct if hasattr(sc, "target_3_pct") else 0

    result = {
        "thesis": f"{coin.name} ({sc.narrative_label}) — {coin.change_7d:+.1f}% 7D, volume spike {coin.volume_spike:.1f}x. {social_highlight}",
        "catalyst": [
            f"Volume tăng {coin.volume_spike:.1f}x so với TB 7 ngày",
            f"Narrative: {sc.narrative_label}",
            social_highlight or "Theo dõi thêm phản ứng giá tại vùng kháng cự",
        ],
        "scenario_bullish": scenario_bullish,
        "scenario_bearish": scenario_bearish,
        "short_term_view": (
            f"Giá đang ở ${price:,.4f}, support {sup}, resistance {res_zone}. "
            + (f"Chờ về vùng {sc.entry_zone_low:,.4f}–{sc.entry_zone_high:,.4f} rồi mới vào." if sc.wait_for_level
               else f"Có thể DCA từng phần tại {sc.entry_zone_low:,.4f}–{price:,.4f}.")
            + f" Invalidation nếu mất {sup}."
        ),
        "entry_condition": sc.entry_condition,
        "targets": {
            "t1":        f"{t1} (+{p1:.0f}% conservative)",
            "t2":        f"{t2} (+{p2:.0f}% mid target)",
            "t3":        f"{t3} (+{p3:.0f}% bull case)",
            "stop_loss": f"{sup} — mất vùng này cắt lỗ",
        },
        "risks": [
            "BTC yếu sẽ kéo cả thị trường",
            f"FDV/MC: {coin.fdv_mc_ratio:.1f}x — rủi ro unlock token",
        ],
        "invalidation":    f"Mất {sup} hoặc BTC breakdown mạnh",
        "action":          action,
        "action_reason":   action_reason,
        "social_highlight": social_highlight,
        # scorer targets
        "_target_1":       sc.target_1,
        "_target_2":       sc.target_2,
        "_target_3":       sc.target_3,
        "_support_zone":   sc.support_zone,
        "_wait_for_level": sc.wait_for_level,
        "_entry_zone_low": sc.entry_zone_low,
        "_entry_zone_high":sc.entry_zone_high,
    }

    # Inject targets từ scorer vào result để reporter dùng
    result["_target_1"]    = sc.target_1
    result["_target_2"]    = sc.target_2
    result["_target_3"]    = sc.target_3
    result["_support"]     = sc.support_zone
    result["_resistance"]  = sc.resistance_zone

    if social:
        result["_social_sentiment"] = social.overall_sentiment
        result["_social_score"]     = social.sentiment_score
        result["_is_cg_trending"]   = social.is_cg_trending
        result["_cg_trending_rank"] = social.cg_trending_rank
        result["_reddit_mentions"]  = social.reddit_mentions

    return result


def analyze_top_coins(scored_coins: list,
                      threshold: int,
                      max_coins: int) -> list[dict]:
    candidates = [sc for sc in scored_coins if sc.total_score >= threshold][:max_coins]

    if not candidates:
        print(f"[Analyst] Không có coin nào vượt ngưỡng {threshold} điểm")
        return []

    has_llm = llm_client.get_provider() != "none"
    provider = llm_client.get_provider()
    if not has_llm:
        print("[Analyst] Không có LLM API key — dùng fallback analysis")
    else:
        print(f"[Analyst] Dùng provider: {provider}")

    # ── Fetch social context cho tất cả candidate (batch) ────
    print(f"[Analyst] Fetch social context cho {len(candidates)} coin...")
    symbols_names = [(sc.coin.symbol, sc.coin.name) for sc in candidates]
    cp_key  = CRYPTOPANIC_API_KEY if CRYPTOPANIC_API_KEY != "YOUR_CRYPTOPANIC_KEY" else ""
    socials = fetch_social_batch(symbols_names, cryptopanic_key=cp_key, delay=1.5)

    # ── Analyze từng coin ─────────────────────────────────────
    print(f"[Analyst] LLM analyze {len(candidates)} coin...")
    results = []
    for i, sc in enumerate(candidates):
        social = socials.get(sc.coin.symbol)
        print(f"  [{i+1}/{len(candidates)}] {sc.coin.symbol} "
              f"(score={sc.total_score} | "
              f"social={social.overall_sentiment if social else 'N/A'} "
              f"{'🔥trending' if social and social.is_cg_trending else ''})")

        if has_llm:
            analysis = analyze_coin(sc, social)
            time.sleep(1)
        else:
            analysis = _fallback_analysis(sc, social)

        results.append({"scored_coin": sc, "analysis": analysis})

    print(f"[Analyst] Xong {len(results)} coin.")
    return results
