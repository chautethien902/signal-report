"""
main.py — Crypto Bot: BTC Module + Alt Scanner
===============================================

Cách chạy:
  python main.py                 → chạy cả 2 module 1 lần (test)
  python main.py --btc-only      → chỉ chạy BTC report 1 lần
  python main.py --alt-only      → chỉ chạy Alt scan 1 lần
  python main.py --dry-run       → chạy không gọi GPT, không gửi Telegram
  python main.py --schedule      → chạy tự động (smart trigger + schedule backup)

Khi --schedule:
  Smart triggers:
    Volatility  → BTC ±3% trong 1H  → chạy cả BTC + Alt
    News event  → FED/CPI/ETF/hack  → chạy cả BTC + Alt
    Cooldown    → 2h sau mỗi trigger (tránh spam)

  Schedule backup:
    BTC report  → mỗi 12h
    Alt scan    → mỗi 6h
    BTC alert   → mỗi 1h
"""

import argparse
import schedule
import time
from datetime import datetime, timezone

from config import (
    BTC_REPORT_INTERVAL_HOURS, BTC_ALERT_CHECK_HOURS,
    BTC_DROP_ALERT_PCT, BTC_PUMP_ALERT_PCT,
    ALT_SCAN_INTERVAL_HOURS, ALT_SCAN_TOP_N_COINS,
    ALT_SCORE_THRESHOLD, ALT_MAX_ANALYZE,
    CMC_ENABLED, CMC_API_KEY, OPENAI_API_KEY,
    TELEGRAM_BOT_TOKEN,
)
import database as db
from trigger_engine import (
    run_trigger_engine, TriggerEvent,
    VOLATILITY_THRESHOLD_PCT, NEWS_CHECK_MIN, COOLDOWN_MINUTES,
)

# ── BTC imports ───────────────────────────────────────────────
import btc_fetcher  as btc_fetch
import btc_analyzer as btc_analyze
import btc_reporter as btc_report

# ── Alt imports ───────────────────────────────────────────────
import alt_scanner  as alt_scan
import alt_filter   as alt_filt
import alt_scorer   as alt_score
import alt_analyst  as alt_analyst_mod
import alt_reporter as alt_report


# ════════════════════════════════════════════════════════════
#  BTC TASKS
# ════════════════════════════════════════════════════════════

def run_btc_report():
    """Full BTC daily report."""
    ts = _now()
    _section("BTC DAILY REPORT")
    try:
        raw      = btc_fetch.fetch_all_btc_data()
        analysis = btc_analyze.run_analysis(raw)
        # Generate scenario analysis (GPT nếu có key, fallback nếu không)
        analysis = btc_analyze.generate_scenario_analysis(analysis, OPENAI_API_KEY)
        message  = btc_report.build_daily_report(analysis, raw["timestamp"])
        btc_report.send_telegram(message)
        # ── Lưu vào DB ──
        db.save_btc_report(analysis)
        print(f"[BTC] ✅ Score={analysis.overall_score}/100 | {analysis.recommendation} | Saved to DB")
    except Exception as e:
        print(f"[BTC] ❌ Lỗi report: {e}")


def run_btc_alert_check():
    """Check pump/dump bất thường."""
    try:
        raw      = btc_fetch.fetch_all_btc_data()
        analysis = btc_analyze.run_analysis(raw)
        change   = analysis.change_24h

        if change <= BTC_DROP_ALERT_PCT:
            print(f"[BTC Alert] 🚨 Dump {change:.1f}%")
            msg = btc_report.build_alert_message(analysis, "DUMP", raw["timestamp"])
            btc_report.send_telegram(msg)
        elif change >= BTC_PUMP_ALERT_PCT:
            print(f"[BTC Alert] 🚀 Pump {change:.1f}%")
            msg = btc_report.build_alert_message(analysis, "PUMP", raw["timestamp"])
            btc_report.send_telegram(msg)
        else:
            print(f"[BTC Alert] OK — 24H: {change:+.2f}%")
    except Exception as e:
        print(f"[BTC Alert] ❌ Lỗi: {e}")


# ════════════════════════════════════════════════════════════
#  ALT TASKS
# ════════════════════════════════════════════════════════════

def run_alt_scan(dry_run: bool = False):
    """Full alt coin scan + analysis + report."""
    ts = _now()
    _section("ALT SCANNER")

    try:
        # 1. Lấy data CoinGecko
        coins = alt_scan.fetch_all_coins(total=ALT_SCAN_TOP_N_COINS)

        # 2. Filter
        filtered, reasons = alt_filt.filter_coins(coins)
        alt_filt.print_filter_stats(len(coins), filtered, reasons)

        if not filtered:
            print("[Alt] Không có coin nào pass filter.")
            return

        # 3. CMC cross-check (1 API call duy nhất)
        if CMC_ENABLED:
            filtered = alt_scan.enrich_with_cmc(filtered, CMC_API_KEY)
            flagged  = [c for c in filtered if c.has_discrepancy]
            if flagged:
                print(f"\n[CMC] ⚠️  {len(flagged)} coin có data lệch:")
                for c in flagged:
                    for note in c.discrepancy_notes:
                        print(f"  {c.symbol}: {note}")

        # 4. Lấy categories thông minh: infer từ keyword trước, gọi API ít thôi
        filtered = alt_scan.fetch_categories_bulk(filtered, max_api_calls=30)

        # 5. Binance OHLCV
        filtered = alt_scan.enrich_with_binance(filtered)

        # 6. Score
        scored = alt_score.score_all(filtered)

        # Print top 20
        print(f"\n[Alt] Top 20:")
        for i, s in enumerate(scored[:20], 1):
            disc = "⚠️ " if s.coin.has_discrepancy else "   "
            print(f"  {i:2}. {disc}{s.coin.symbol:10} {s.total_score:3}/100  "
                  f"7D:{s.coin.change_7d:+6.1f}%  "
                  f"Spike:{s.coin.volume_spike:.1f}x  "
                  f"{s.narrative_label}")

        # 7. GPT analysis
        if not dry_run and OPENAI_API_KEY.startswith("sk-"):
            results = alt_analyst_mod.analyze_top_coins(
                scored,
                threshold=ALT_SCORE_THRESHOLD,
                max_coins=ALT_MAX_ANALYZE,
            )
        else:
            if dry_run:
                print("[Alt] Dry run — dùng fallback analysis")
            else:
                print("[Alt] OpenAI key chưa cấu hình — dùng fallback")
            results = [
                {"scored_coin": s, "analysis": alt_analyst_mod._fallback_analysis(s)}
                for s in scored[:ALT_MAX_ANALYZE]
                if s.total_score >= ALT_SCORE_THRESHOLD
            ]

        # 8. Lưu vào DB
        db.save_alt_scan(ts, len(coins), len(filtered), results)

        # 9. Gửi Telegram
        alt_report.send_full_report(results, ts, len(coins))
        print(f"\n[Alt] ✅ {len(results)} coin phân tích xong. Saved to DB.")

    except Exception as e:
        print(f"[Alt] ❌ Lỗi scan: {e}")
        import traceback; traceback.print_exc()


# ════════════════════════════════════════════════════════════
#  SCHEDULER
# ════════════════════════════════════════════════════════════

def on_trigger(event: TriggerEvent, dry_run: bool = False):
    """
    Callback khi trigger engine fire — chạy cả BTC + Alt.
    Gửi thêm notification báo lý do trigger.
    """
    ts = _now()
    severity_emoji = "🚨" if event.severity == "HIGH" else "⚠️"

    # Gửi alert trước về lý do trigger
    trigger_msg = (
        f"{severity_emoji} <b>TRIGGER: {event.trigger_type}</b>\n"
        f"🕐 {ts}\n\n"
        f"📌 {event.reason}\n"
    )
    if event.news_title:
        trigger_msg += f"📰 {event.news_title}\n"
    trigger_msg += "\n⏳ Đang chạy scan toàn bộ..."
    btc_report.send_telegram(trigger_msg)

    _section(f"TRIGGERED: {event.trigger_type} — {event.reason}")
    run_btc_report()
    run_alt_scan(dry_run=dry_run)


def start_scheduler(dry_run: bool = False):
    """
    Chạy Smart Trigger Engine + Schedule backup song song.
    - Thread 1: Trigger engine (volatility + news)
    - Thread 2: Schedule backup (BTC 12h + Alt 6h + BTC alert 1h)
    """
    db.init_db()

    cp_key = CRYPTOPANIC_API_KEY if "CRYPTOPANIC_API_KEY" in dir() else ""
    try:
        from config import CRYPTOPANIC_API_KEY as cp_key
    except ImportError:
        cp_key = ""

    print("\n" + "="*55)
    print("  CRYPTO BOT — SMART TRIGGER MODE")
    print("="*55)
    print(f"  🔥 Volatility trigger : BTC ±{VOLATILITY_THRESHOLD_PCT}% trong 1H")
    print(f"  📰 News trigger       : FED/CPI/ETF/hack... mỗi {NEWS_CHECK_MIN}p")
    print(f"  ⏳ Cooldown           : {COOLDOWN_MINUTES} phút sau trigger")
    print(f"  ── Schedule backup ──────────────────")
    print(f"  BTC report  : mỗi 12h")
    print(f"  BTC alert   : mỗi 1h")
    print(f"  Alt scan    : mỗi {ALT_SCAN_INTERVAL_HOURS}h")
    print(f"  ── Status ───────────────────────────")
    print(f"  CMC         : {'✅' if CMC_ENABLED else '❌ chưa có key'}")
    print(f"  GPT         : {'✅' if OPENAI_API_KEY.startswith('sk-') else '❌ chưa có key'}")
    print(f"  Telegram    : {'✅' if TELEGRAM_BOT_TOKEN != 'YOUR_BOT_TOKEN' else '❌ in console'}")
    print("="*55)

    # ── Chạy lần đầu khi boot ─────────────────────────────
    print("\n[Boot] Chạy lần đầu...")
    run_btc_report()
    run_alt_scan(dry_run=dry_run)

    # ── Thread 1: Trigger Engine ──────────────────────────
    def trigger_loop():
        run_trigger_engine(
            on_trigger_callback=lambda e: on_trigger(e, dry_run=dry_run),
            cryptopanic_key=cp_key,
            dry_run=dry_run,
        )

    t = threading.Thread(target=trigger_loop, daemon=True, name="TriggerEngine")
    t.start()
    print("\n[TriggerEngine] Thread khởi động ✅")

    # ── Thread 2: Schedule backup ─────────────────────────
    schedule.every(12).hours.do(run_btc_report)
    schedule.every(BTC_ALERT_CHECK_HOURS).hours.do(run_btc_alert_check)
    schedule.every(ALT_SCAN_INTERVAL_HOURS).hours.do(run_alt_scan, dry_run=dry_run)

    print("[Scheduler] Backup schedule active ✅")
    print("\n[Bot] Đang chạy... (Ctrl+C để dừng)\n")

    while True:
        schedule.run_pending()
        time.sleep(30)


# ════════════════════════════════════════════════════════════
#  HELPERS
# ════════════════════════════════════════════════════════════

def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

def _section(title: str):
    print(f"\n{'='*55}")
    print(f"  [{datetime.now().strftime('%H:%M:%S')}] {title}")
    print(f"{'='*55}")


# ════════════════════════════════════════════════════════════
#  ENTRY POINT
# ════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Crypto Bot — BTC Module + Alt Scanner",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("--schedule",  action="store_true", help="Chạy tự động theo lịch")
    parser.add_argument("--btc-only",  action="store_true", help="Chỉ chạy BTC module")
    parser.add_argument("--alt-only",  action="store_true", help="Chỉ chạy Alt scanner")
    parser.add_argument("--dry-run",   action="store_true", help="Không gọi GPT, in console thay Telegram")
    parser.add_argument("--btc-alert", action="store_true", help="Chỉ chạy BTC alert check")
    args = parser.parse_args()

    if args.btc_alert:
        db.init_db()
        run_btc_alert_check()
    elif args.btc_only:
        db.init_db()
        run_btc_report()
    elif args.alt_only:
        db.init_db()
        run_alt_scan(dry_run=args.dry_run)
    elif args.schedule:
        start_scheduler(dry_run=args.dry_run)
    else:
        db.init_db()
        _section("BTC MODULE")
        run_btc_report()
        _section("ALT SCANNER")
        run_alt_scan(dry_run=args.dry_run)
        print(f"\n✅ Done.")


if __name__ == "__main__":
    main()
