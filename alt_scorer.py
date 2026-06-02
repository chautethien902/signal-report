"""
scorer.py
Module 3: Chấm điểm từng coin theo 5 nhóm tiêu chí (tổng 100 điểm).

Trọng số:
  Narrative   25đ  — coin thuộc trend đang hot không?
  Momentum    20đ  — giá đang mạnh hơn thị trường?
  Volume      20đ  — dòng tiền thực sự đang vào không?
  Tokenomics  15đ  — cấu trúc token có lành mạnh không?
  Sentiment   10đ  — market đang chú ý coin này không?
  Bonus       10đ  — các tín hiệu cộng thêm
"""

from dataclasses import dataclass, field
from alt_scanner import CoinData
from config import NARRATIVE_SCORES, DEFAULT_NARRATIVE_SCORE


@dataclass
class ScoredCoin:
    coin:               CoinData = None
    # Scores từng nhóm
    narrative_score:    int = 0
    momentum_score:     int = 0
    volume_score:       int = 0
    tokenomics_score:   int = 0
    sentiment_score:    int = 0
    bonus_score:        int = 0
    total_score:        int = 0
    # Detail để debug / hiển thị
    narrative_label:    str = ""
    score_breakdown:    dict = field(default_factory=dict)


# ── 1. Narrative (25đ) ───────────────────────────────────────

def score_narrative(categories: list[str]) -> tuple[int, str]:
    """
    Map coin categories → narrative score.
    Lấy score cao nhất nếu coin thuộc nhiều narrative.
    """
    if not categories:
        return DEFAULT_NARRATIVE_SCORE, "Không rõ narrative"

    best_score = DEFAULT_NARRATIVE_SCORE
    best_label = "General"

    for cat in categories:
        cat_lower = cat.lower().replace(" ", "-").replace("_", "-")
        for key, score in NARRATIVE_SCORES.items():
            if key in cat_lower or cat_lower in key:
                if score > best_score:
                    best_score = score
                    best_label = cat

    return best_score, best_label


# ── 2. Momentum (20đ) ────────────────────────────────────────

def score_momentum(change_7d: float, change_30d: float, weekly_closes: list) -> int:
    """
    Đánh giá momentum giá:
    - 7D và 30D change
    - Slope của 4 tuần gần nhất (tăng đều hay không)
    """
    score = 0

    # 7D performance
    if change_7d > 25:      score += 10
    elif change_7d > 15:    score += 8
    elif change_7d > 8:     score += 6
    elif change_7d > 3:     score += 4
    elif change_7d > 0:     score += 2
    elif change_7d > -10:   score += 1
    else:                   score += 0

    # 30D performance
    if change_30d > 50:     score += 10
    elif change_30d > 30:   score += 8
    elif change_30d > 15:   score += 6
    elif change_30d > 5:    score += 4
    elif change_30d > 0:    score += 2
    else:                   score += 0

    # Momentum slope: giá đang tăng đều hay chỉ pump 1 lần?
    if len(weekly_closes) >= 4:
        recent_4 = weekly_closes[-4:]
        # Đếm số tuần tăng trong 4 tuần cuối
        up_weeks = sum(1 for i in range(1, len(recent_4)) if recent_4[i] > recent_4[i-1])
        # 3/3 tuần tăng → bonus, nhưng đã tính trong 7D/30D nên không double count nhiều
        # Chỉ dùng để validate momentum bền
        if up_weeks < 2:
            score = max(0, score - 2)  # pump 1 lần rồi sideways → trừ nhẹ

    return min(20, score)


# ── 3. Volume Strength (20đ) ─────────────────────────────────

def score_volume(volume_24h: float, market_cap: float, volume_spike: float) -> int:
    """
    Đánh giá sức mạnh volume:
    - Volume/MC ratio: coin đang active không?
    - Volume spike: có đột biến gần đây không?
    """
    score = 0

    # Volume/MC ratio
    if market_cap > 0:
        ratio = volume_24h / market_cap
        if ratio > 0.30:    score += 14
        elif ratio > 0.15:  score += 11
        elif ratio > 0.08:  score += 8
        elif ratio > 0.04:  score += 5
        elif ratio > 0.02:  score += 3
        else:               score += 1

    # Volume spike: dòng tiền đang tăng đột biến?
    if volume_spike >= 3.0:    score += 6   # volume hôm nay gấp 3x TB
    elif volume_spike >= 2.0:  score += 4
    elif volume_spike >= 1.5:  score += 2
    else:                      score += 0

    return min(20, score)


# ── 4. Tokenomics (15đ) ──────────────────────────────────────

def score_tokenomics(fdv_mc_ratio: float, change_30d: float) -> int:
    """
    Đánh giá tokenomics dựa trên FDV/MC ratio.
    Ratio thấp = phần lớn token đã lưu hành = ít rủi ro unlock dump.
    
    Ngoài ra nếu coin đã tăng mạnh 30D nhưng FDV/MC xấu → trừ thêm.
    """
    score = 0

    if fdv_mc_ratio <= 1.1:    score = 15   # gần như không có token chưa unlock
    elif fdv_mc_ratio <= 1.5:  score = 12
    elif fdv_mc_ratio <= 2.5:  score = 9
    elif fdv_mc_ratio <= 4.0:  score = 6
    elif fdv_mc_ratio <= 6.0:  score = 3
    else:                      score = 0    # tokenomics rất xấu

    # Penalize nếu đã pump mạnh nhưng tokenomics xấu (dễ bị dump unlock)
    if change_30d > 50 and fdv_mc_ratio > 3.0:
        score = max(0, score - 3)

    return score


# ── 5. Sentiment proxy (10đ) ─────────────────────────────────

def score_sentiment(change_24h: float, volume_spike: float, change_7d: float) -> int:
    """
    Proxy sentiment từ price + volume action (không cần social API).
    Lý do: price action phản ánh sentiment thực tế.
    
    Sau này có thể thay bằng CryptoPanic API để chính xác hơn.
    """
    score = 0

    # Coin đang được chú ý: giá tăng + volume tăng đồng thời
    if change_24h > 5 and volume_spike > 1.5:
        score += 6
    elif change_24h > 2 and volume_spike > 1.3:
        score += 4
    elif change_24h > 0:
        score += 2

    # 7D strong → market đang quan tâm
    if change_7d > 20:    score += 4
    elif change_7d > 10:  score += 2

    return min(10, score)


# ── Bonus (10đ) ──────────────────────────────────────────────

def score_bonus(coin: CoinData) -> int:
    """
    Các tín hiệu cộng thêm không fit vào nhóm trên.
    """
    bonus = 0

    # Market cap mid-range có upside tốt nhất
    mc = coin.market_cap
    if 200_000_000 <= mc <= 2_000_000_000:
        bonus += 5   # sweet spot: đủ lớn để tin, đủ nhỏ để x3-x5

    # Volume tăng mạnh nhưng giá chưa tăng nhiều → early signal
    if coin.volume_spike > 2.0 and coin.change_7d < 15:
        bonus += 3

    # 30D tốt + 7D tốt → momentum bền, không phải pump 1 lần
    if coin.change_30d > 20 and coin.change_7d > 5:
        bonus += 2

    return min(10, bonus)


# ── Main scorer ──────────────────────────────────────────────

def score_coin(coin: CoinData) -> ScoredCoin:
    """Chấm điểm 1 coin, trả về ScoredCoin."""
    sc = ScoredCoin(coin=coin)

    sc.narrative_score, sc.narrative_label = score_narrative(coin.categories)
    sc.momentum_score   = score_momentum(coin.change_7d, coin.change_30d, coin.weekly_closes)
    sc.volume_score     = score_volume(coin.volume_24h, coin.market_cap, coin.volume_spike)
    sc.tokenomics_score = score_tokenomics(coin.fdv_mc_ratio, coin.change_30d)
    sc.sentiment_score  = score_sentiment(coin.change_24h, coin.volume_spike, coin.change_7d)
    sc.bonus_score      = score_bonus(coin)

    sc.total_score = (
        sc.narrative_score +
        sc.momentum_score  +
        sc.volume_score    +
        sc.tokenomics_score +
        sc.sentiment_score +
        sc.bonus_score
    )

    sc.score_breakdown = {
        "Narrative":   sc.narrative_score,
        "Momentum":    sc.momentum_score,
        "Volume":      sc.volume_score,
        "Tokenomics":  sc.tokenomics_score,
        "Sentiment":   sc.sentiment_score,
        "Bonus":       sc.bonus_score,
    }

    return sc


def score_all(coins: list[CoinData]) -> list[ScoredCoin]:
    """Chấm điểm toàn bộ list, sort theo score giảm dần."""
    print(f"[Scorer] Chấm điểm {len(coins)} coin...")
    scored = [score_coin(c) for c in coins]
    scored.sort(key=lambda x: x.total_score, reverse=True)
    return scored
