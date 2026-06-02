"""
alt_analyst.py
Module 4: Gọi OpenAI GPT để viết deep analysis cho coin đạt ngưỡng score.
GPT nhận market data + social context (news, Reddit, trending) để phân tích toàn diện hơn.
"""

import os
import json
import time
from openai import OpenAI
from alt_scorer import ScoredCoin
from config import OPENAI_API_KEY, CRYPTOPANIC_API_KEY
from social_fetcher import SocialContext, fetch_social_batch


def get_openai_client():
    key = OPENAI_API_KEY
    if key.startswith("sk-"):
        return OpenAI(api_key=key)
    env_key = os.environ.get("OPENAI_API_KEY", "")
    if env_key:
        return OpenAI(api_key=env_key)
    return None


def build_prompt(sc: ScoredCoin, social: SocialContext = None) -> str:
    coin = sc.coin
    mc_b = coin.market_cap / 1e9
    breakdown_str = " | ".join(f"{k}: {v}" for k, v in sc.score_breakdown.items())

    # Social context block — chỉ thêm nếu có data
    if social and social.summary:
        social_block = f"""
=== SOCIAL & NEWS CONTEXT ===
{social.summary}
"""
    else:
        social_block = ""

    prompt = f"""
Bạn là chuyên gia phân tích crypto spot trading thực dụng, trung thực, không hype.

Hãy phân tích coin sau và viết report NGẮN GỌN, SÚC TÍCH (không dài dòng):

=== MARKET DATA ===
Coin: {coin.name} ({coin.symbol})
Giá: ${coin.price:,.4f}
Market Cap: ${mc_b:.2f}B
Volume 24H: ${coin.volume_24h/1e6:.1f}M
FDV/MC ratio: {coin.fdv_mc_ratio:.1f}x

Biến động:
- 1H: {coin.change_1h:+.2f}%
- 24H: {coin.change_24h:+.2f}%
- 7D: {coin.change_7d:+.2f}%
- 30D: {coin.change_30d:+.2f}%

Volume spike (vs TB 7D): {coin.volume_spike:.1f}x
Narrative: {sc.narrative_label}
Score: {sc.total_score}/100 | {breakdown_str}
{social_block}
=== YÊU CẦU ===
Dựa vào CẢ HAI market data VÀ social/news context ở trên, viết report JSON:
- Nếu tin tức/sentiment tiêu cực → phản ánh vào risks và action
- Nếu coin đang trending hoặc được đề cập nhiều → nêu trong catalyst
- Nếu news và price action mâu thuẫn → chỉ ra điều đó trong thesis

Chỉ trả về JSON, không viết gì thêm:

{{
  "thesis": "1-2 câu: tại sao coin này đáng chú ý lúc này, có tích hợp thông tin news/social",
  "catalyst": ["catalyst 1 (có thể từ news)", "catalyst 2", "catalyst 3"],
  "upside": {{
    "conservative": "ví dụ: x1.5 (~$X)",
    "bull_case": "ví dụ: x3 (~$X)",
    "condition": "điều kiện để bull case xảy ra"
  }},
  "risks": ["rủi ro 1 (có thể từ news tiêu cực)", "rủi ro 2", "rủi ro 3"],
  "invalidation": "điều kiện cụ thể nào khiến thesis này sai",
  "action": "ACCUMULATE hoặc WATCH hoặc AVOID",
  "action_reason": "1 câu giải thích tại sao, tích hợp cả data + sentiment",
  "dca_note": "nếu ACCUMULATE: gợi ý vùng giá DCA, nếu WATCH: chờ gì",
  "social_highlight": "1 câu tóm tắt điều đáng chú ý nhất từ social/news"
}}

Hãy thực tế, đừng hype. Nếu sentiment xấu thì nói thẳng.
""".strip()

    return prompt


def analyze_coin(sc: ScoredCoin, client, social: SocialContext = None) -> dict:
    prompt = build_prompt(sc, social)
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=900,
        )
        raw_text = response.choices[0].message.content.strip()
        if "```json" in raw_text:
            raw_text = raw_text.split("```json")[1].split("```")[0].strip()
        elif "```" in raw_text:
            raw_text = raw_text.split("```")[1].split("```")[0].strip()
        result = json.loads(raw_text)
        # Gắn thêm social meta vào result để reporter dùng
        if social:
            result["_social_sentiment"]   = social.overall_sentiment
            result["_social_score"]       = social.sentiment_score
            result["_is_cg_trending"]     = social.is_cg_trending
            result["_cg_trending_rank"]   = social.cg_trending_rank
            result["_reddit_mentions"]    = social.reddit_mentions
        return result
    except json.JSONDecodeError as e:
        print(f"[Analyst] JSON parse lỗi cho {sc.coin.symbol}: {e}")
        return _fallback_analysis(sc, social)
    except Exception as e:
        print(f"[Analyst] GPT lỗi cho {sc.coin.symbol}: {e}")
        return _fallback_analysis(sc, social)


def _fallback_analysis(sc: ScoredCoin, social: SocialContext = None) -> dict:
    coin  = sc.coin
    score = sc.total_score

    # Điều chỉnh action dựa trên sentiment nếu có
    if social and social.overall_sentiment == "negative" and score < 75:
        action        = "WATCH"
        action_reason = "Score khá nhưng sentiment tiêu cực — chờ xác nhận"
    elif score >= 75:
        action        = "ACCUMULATE"
        action_reason = "Score cao, nhiều tín hiệu tích cực"
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

    result = {
        "thesis": f"{coin.name} có momentum tốt ({coin.change_7d:+.1f}% 7D, volume spike {coin.volume_spike:.1f}x).",
        "catalyst": [
            f"Volume tăng {coin.volume_spike:.1f}x so với TB 7 ngày",
            f"Narrative: {sc.narrative_label}",
            social_highlight or "Cần theo dõi thêm",
        ],
        "upside": {
            "conservative": "x1.5",
            "bull_case":    "x3",
            "condition":    "Altseason + narrative tiếp tục mạnh",
        },
        "risks": [
            "BTC yếu sẽ kéo cả thị trường",
            f"FDV/MC: {coin.fdv_mc_ratio:.1f}x — rủi ro unlock",
            f"Sentiment: {social.overall_sentiment if social else 'unknown'}",
        ],
        "invalidation":    "Mất momentum hoặc BTC breakdown mạnh",
        "action":          action,
        "action_reason":   action_reason,
        "dca_note":        f"DCA quanh ${coin.price:,.4f}, chia nhỏ vốn",
        "social_highlight": social_highlight,
    }

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

    client = get_openai_client()
    if not client:
        print("[Analyst] Không có OpenAI API key — dùng fallback analysis")

    # ── Fetch social context cho tất cả candidate (batch) ────
    print(f"[Analyst] Fetch social context cho {len(candidates)} coin...")
    symbols_names = [(sc.coin.symbol, sc.coin.name) for sc in candidates]
    cp_key  = CRYPTOPANIC_API_KEY if CRYPTOPANIC_API_KEY != "YOUR_CRYPTOPANIC_KEY" else ""
    socials = fetch_social_batch(symbols_names, cryptopanic_key=cp_key, delay=1.5)

    # ── Analyze từng coin ─────────────────────────────────────
    print(f"[Analyst] GPT analyze {len(candidates)} coin...")
    results = []
    for i, sc in enumerate(candidates):
        social = socials.get(sc.coin.symbol)
        print(f"  [{i+1}/{len(candidates)}] {sc.coin.symbol} "
              f"(score={sc.total_score} | "
              f"social={social.overall_sentiment if social else 'N/A'} "
              f"{'🔥trending' if social and social.is_cg_trending else ''})")

        if client:
            analysis = analyze_coin(sc, client, social)
            time.sleep(1)
        else:
            analysis = _fallback_analysis(sc, social)

        results.append({"scored_coin": sc, "analysis": analysis})

    print(f"[Analyst] Xong {len(results)} coin.")
    return results
