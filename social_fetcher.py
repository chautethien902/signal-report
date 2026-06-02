"""
social_fetcher.py
Thu thập tin tức + sentiment từ 4 nguồn:
  1. CoinGecko Trending  — coin đang hot nhất thị trường (0 API key)
  2. CryptoPanic         — tin tức crypto tổng hợp (free API key)
  3. Google News RSS     — tin tức từ Google (0 API key, scrape RSS)
  4. Reddit              — post/comment r/CryptoCurrency (free API)

Output: SocialContext — dict gọn để inject vào GPT prompt
"""

import re
import time
import requests
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timezone
from urllib.parse import quote

from config import CMC_API_KEY  # tái dùng, không cần key riêng


# ════════════════════════════════════════════════════════════
#  DATA CLASSES
# ════════════════════════════════════════════════════════════

@dataclass
class NewsItem:
    source:    str = ""
    title:     str = ""
    url:       str = ""
    sentiment: str = "neutral"   # positive / negative / neutral
    age_hours: float = 0.0


@dataclass
class SocialContext:
    symbol:           str = ""
    is_cg_trending:   bool  = False   # đang top trending CoinGecko
    cg_trending_rank: int   = 0       # rank 1-10, 0 = không trending
    news_items:       list  = field(default_factory=list)   # list NewsItem
    reddit_mentions:  int   = 0       # số post Reddit 24h
    reddit_sentiment: str   = "neutral"
    reddit_top_title: str   = ""      # tiêu đề post hot nhất
    overall_sentiment: str  = "neutral"  # tổng hợp
    sentiment_score:   int  = 0          # -100 đến +100
    summary:           str  = ""         # 1 đoạn tóm tắt để inject vào prompt


# ════════════════════════════════════════════════════════════
#  1. COINGECKO TRENDING
# ════════════════════════════════════════════════════════════

_cg_trending_cache: dict = {"data": [], "fetched_at": 0}
_CG_CACHE_TTL = 1800   # cache 30 phút, tránh gọi lại


def get_cg_trending_coins() -> list[dict]:
    """
    Lấy top 10 trending coin từ CoinGecko (không cần API key).
    Cache 30 phút để không gọi lại cho mỗi coin.
    """
    now = time.time()
    if now - _cg_trending_cache["fetched_at"] < _CG_CACHE_TTL:
        return _cg_trending_cache["data"]

    url = "https://api.coingecko.com/api/v3/search/trending"
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        coins = r.json().get("coins", [])
        result = []
        for i, item in enumerate(coins):
            c = item.get("item", {})
            result.append({
                "symbol": c.get("symbol", "").upper(),
                "name":   c.get("name", ""),
                "rank":   i + 1,
            })
        _cg_trending_cache["data"]       = result
        _cg_trending_cache["fetched_at"] = now
        print(f"[CG Trending] {len(result)} coin: {[c['symbol'] for c in result]}")
        return result
    except Exception as e:
        print(f"[CG Trending] Lỗi: {e}")
        return []


def check_trending(symbol: str) -> tuple[bool, int]:
    """Kiểm tra coin có đang top trending CoinGecko không."""
    trending = get_cg_trending_coins()
    for item in trending:
        if item["symbol"].upper() == symbol.upper():
            return True, item["rank"]
    return False, 0


# ════════════════════════════════════════════════════════════
#  2. CRYPTOPANIC
# ════════════════════════════════════════════════════════════

def fetch_cryptopanic(symbol: str, api_key: str = "", limit: int = 5) -> list[NewsItem]:
    """
    Lấy tin tức mới nhất về coin từ CryptoPanic.
    Free API key: đăng ký tại cryptopanic.com
    Nếu không có key: dùng public endpoint (ít tin hơn, không có sentiment).
    """
    if api_key and api_key != "YOUR_CRYPTOPANIC_KEY":
        url = "https://cryptopanic.com/api/v1/posts/"
        params = {
            "auth_token": api_key,
            "currencies": symbol,
            "filter":     "hot",
            "public":     "true",
        }
    else:
        # Public endpoint không cần key (giới hạn hơn)
        url = "https://cryptopanic.com/api/v1/posts/"
        params = {
            "currencies": symbol,
            "public":     "true",
        }

    try:
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        results = r.json().get("results", [])[:limit]
        items   = []
        for post in results:
            # Parse age
            created = post.get("created_at", "")
            age_h   = _parse_age_hours(created)
            # Sentiment từ votes
            votes    = post.get("votes", {})
            positive = votes.get("positive", 0)
            negative = votes.get("negative", 0)
            if positive > negative * 1.5:
                sentiment = "positive"
            elif negative > positive * 1.5:
                sentiment = "negative"
            else:
                sentiment = "neutral"

            items.append(NewsItem(
                source    = "CryptoPanic",
                title     = post.get("title", ""),
                url       = post.get("url", ""),
                sentiment = sentiment,
                age_hours = age_h,
            ))
        return items
    except Exception as e:
        print(f"[CryptoPanic {symbol}] Lỗi: {e}")
        return []


# ════════════════════════════════════════════════════════════
#  3. GOOGLE NEWS RSS
# ════════════════════════════════════════════════════════════

def fetch_google_news(symbol: str, name: str, limit: int = 5) -> list[NewsItem]:
    """
    Lấy tin từ Google News RSS — không cần API key.
    Query: "<symbol> crypto" hoặc "<name> cryptocurrency"
    """
    query = quote(f"{name} crypto OR {symbol} cryptocurrency")
    url   = f"https://news.google.com/rss/search?q={query}&hl=en&gl=US&ceid=US:en"

    try:
        r = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        root  = ET.fromstring(r.content)
        items = []

        for item in root.findall(".//item")[:limit]:
            title   = item.findtext("title", "")
            link    = item.findtext("link", "")
            pub_date = item.findtext("pubDate", "")
            age_h   = _parse_rss_age(pub_date)

            # Simple sentiment từ keywords trong title
            title_lower = title.lower()
            pos_words = ["surge", "rally", "bullish", "pump", "breakout",
                         "gain", "rise", "soar", "all-time", "adoption"]
            neg_words = ["crash", "dump", "bearish", "fall", "drop",
                         "plunge", "hack", "scam", "ban", "warning"]
            pos = sum(1 for w in pos_words if w in title_lower)
            neg = sum(1 for w in neg_words if w in title_lower)
            if pos > neg:   sentiment = "positive"
            elif neg > pos: sentiment = "negative"
            else:           sentiment = "neutral"

            items.append(NewsItem(
                source    = "Google News",
                title     = _clean_title(title),
                url       = link,
                sentiment = sentiment,
                age_hours = age_h,
            ))
        return items
    except Exception as e:
        print(f"[Google News {symbol}] Lỗi: {e}")
        return []


# ════════════════════════════════════════════════════════════
#  4. REDDIT
# ════════════════════════════════════════════════════════════

def fetch_reddit(symbol: str, name: str, limit: int = 10) -> dict:
    """
    Tìm mentions trên r/CryptoCurrency và r/Bitcoin.
    Dùng Reddit JSON API public (không cần OAuth).
    Trả về: {mentions, sentiment, top_title}
    """
    subreddits = ["CryptoCurrency", "CryptoMarkets", "altcoin"]
    query      = f"{symbol} OR {name}"
    all_posts  = []

    for sub in subreddits:
        url = f"https://www.reddit.com/r/{sub}/search.json"
        params = {
            "q":        query,
            "sort":     "new",
            "limit":    limit,
            "restrict_sr": "true",
            "t":        "day",   # 24h
        }
        try:
            r = requests.get(
                url, params=params, timeout=10,
                headers={"User-Agent": "CryptoBot/1.0"}
            )
            if r.status_code == 200:
                posts = r.json().get("data", {}).get("children", [])
                all_posts.extend([p["data"] for p in posts])
            time.sleep(0.5)   # Reddit rate limit
        except Exception as e:
            print(f"[Reddit {sub}] Lỗi: {e}")

    if not all_posts:
        return {"mentions": 0, "sentiment": "neutral", "top_title": ""}

    # Sentiment từ upvote ratio và title
    pos_count = 0
    neg_count = 0
    top_post  = max(all_posts, key=lambda p: p.get("score", 0), default={})

    for post in all_posts:
        ratio = post.get("upvote_ratio", 0.5)
        title = post.get("title", "").lower()
        neg_words = ["dump", "crash", "scam", "rug", "exit", "dead", "bearish", "warning"]
        pos_words = ["moon", "bullish", "buy", "pump", "gem", "undervalued", "hold"]
        has_neg = any(w in title for w in neg_words)
        has_pos = any(w in title for w in pos_words)

        if ratio > 0.7 or has_pos:  pos_count += 1
        if ratio < 0.4 or has_neg:  neg_count += 1

    if pos_count > neg_count * 1.5:   sentiment = "positive"
    elif neg_count > pos_count * 1.5: sentiment = "negative"
    else:                             sentiment = "neutral"

    return {
        "mentions":  len(all_posts),
        "sentiment": sentiment,
        "top_title": top_post.get("title", "")[:120],
    }


# ════════════════════════════════════════════════════════════
#  TỔNG HỢP
# ════════════════════════════════════════════════════════════

def fetch_social_context(
    symbol: str,
    name:   str,
    cryptopanic_key: str = "",
) -> SocialContext:
    """
    Entry point chính — lấy toàn bộ social data cho 1 coin.
    Trả về SocialContext đã có summary sẵn để inject vào GPT prompt.
    """
    ctx = SocialContext(symbol=symbol)

    # 1. CoinGecko Trending (đã cache, không tốn API call thêm)
    ctx.is_cg_trending, ctx.cg_trending_rank = check_trending(symbol)

    # 2. CryptoPanic
    cp_news = fetch_cryptopanic(symbol, cryptopanic_key, limit=4)
    ctx.news_items.extend(cp_news)

    # 3. Google News
    gn_news = fetch_google_news(symbol, name, limit=4)
    ctx.news_items.extend(gn_news)

    # 4. Reddit
    reddit = fetch_reddit(symbol, name, limit=10)
    ctx.reddit_mentions  = reddit["mentions"]
    ctx.reddit_sentiment = reddit["sentiment"]
    ctx.reddit_top_title = reddit["top_title"]

    # Tính overall sentiment score (-100 đến +100)
    score = 0
    if ctx.is_cg_trending:
        score += 30 - (ctx.cg_trending_rank * 2)   # rank 1 = +28, rank 10 = +10

    for item in ctx.news_items:
        if item.age_hours <= 24:
            if item.sentiment == "positive": score += 8
            elif item.sentiment == "negative": score -= 8
            else: score += 1

    reddit_score_map = {"positive": 15, "neutral": 0, "negative": -15}
    score += reddit_score_map.get(ctx.reddit_sentiment, 0)
    score += min(15, ctx.reddit_mentions * 2)   # nhiều mentions = +điểm

    ctx.sentiment_score = max(-100, min(100, score))

    if ctx.sentiment_score >= 25:     ctx.overall_sentiment = "positive"
    elif ctx.sentiment_score <= -20:  ctx.overall_sentiment = "negative"
    else:                             ctx.overall_sentiment = "neutral"

    # Build summary để inject vào GPT
    ctx.summary = _build_summary(ctx)
    return ctx


def _build_summary(ctx: SocialContext) -> str:
    """Tóm tắt social context thành đoạn văn cho GPT."""
    parts = []

    # Trending
    if ctx.is_cg_trending:
        parts.append(f"🔥 Đang top #{ctx.cg_trending_rank} CoinGecko Trending")

    # Tin tức gần đây
    recent_news = [n for n in ctx.news_items if n.age_hours <= 48]
    if recent_news:
        pos = sum(1 for n in recent_news if n.sentiment == "positive")
        neg = sum(1 for n in recent_news if n.sentiment == "negative")
        parts.append(f"📰 {len(recent_news)} tin tức 48h: {pos} tích cực, {neg} tiêu cực")
        # Lấy 3 title tiêu biểu
        for n in recent_news[:3]:
            emoji = "+" if n.sentiment == "positive" else "-" if n.sentiment == "negative" else "•"
            parts.append(f"  {emoji} [{n.source}] {n.title[:80]}")
    else:
        parts.append("📰 Không có tin tức đáng kể 48h qua")

    # Reddit
    if ctx.reddit_mentions > 0:
        parts.append(
            f"💬 Reddit: {ctx.reddit_mentions} mentions 24h — "
            f"sentiment {ctx.reddit_sentiment}"
        )
        if ctx.reddit_top_title:
            parts.append(f"  Top post: \"{ctx.reddit_top_title}\"")
    else:
        parts.append("💬 Reddit: ít được đề cập 24h qua")

    # Kết luận sentiment
    parts.append(
        f"📊 Social sentiment tổng hợp: {ctx.overall_sentiment.upper()} "
        f"(score: {ctx.sentiment_score:+d}/100)"
    )

    return "\n".join(parts)


# ════════════════════════════════════════════════════════════
#  HELPERS
# ════════════════════════════════════════════════════════════

def _parse_age_hours(iso_str: str) -> float:
    """Parse ISO datetime string → số giờ từ bây giờ."""
    try:
        dt  = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        return (now - dt).total_seconds() / 3600
    except:
        return 999.0


def _parse_rss_age(rss_date: str) -> float:
    """Parse RSS date format → số giờ từ bây giờ."""
    from email.utils import parsedate_to_datetime
    try:
        dt  = parsedate_to_datetime(rss_date)
        now = datetime.now(timezone.utc)
        return (now - dt).total_seconds() / 3600
    except:
        return 999.0


def _clean_title(title: str) -> str:
    """Xóa tên source thường append vào cuối title Google News."""
    return re.sub(r"\s*-\s*[^-]+$", "", title).strip()


# ════════════════════════════════════════════════════════════
#  BATCH (dùng trong pipeline)
# ════════════════════════════════════════════════════════════

def fetch_social_batch(
    symbols_names: list[tuple[str, str]],
    cryptopanic_key: str = "",
    delay: float = 1.5,
) -> dict[str, SocialContext]:
    """
    Lấy social context cho nhiều coin cùng lúc.
    Tự động prefetch CG trending (1 call cho tất cả).
    
    symbols_names: list of (symbol, name)
    Trả về: {symbol: SocialContext}
    """
    # Prefetch trending 1 lần cho tất cả
    get_cg_trending_coins()

    results = {}
    for i, (symbol, name) in enumerate(symbols_names):
        print(f"  [{i+1}/{len(symbols_names)}] Social fetch: {symbol}...")
        ctx = fetch_social_context(symbol, name, cryptopanic_key)
        results[symbol] = ctx
        if i < len(symbols_names) - 1:
            time.sleep(delay)   # tránh rate limit

    return results


if __name__ == "__main__":
    # Test nhanh
    print("=== Test Social Fetcher ===\n")
    ctx = fetch_social_context("BTC", "Bitcoin")
    print(ctx.summary)
    print(f"\nSentiment score: {ctx.sentiment_score}")
    print(f"Is trending: {ctx.is_cg_trending} (rank {ctx.cg_trending_rank})")
