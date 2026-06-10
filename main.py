"""
main.py — Crypto Bot: BTC Module + Alt Scanner
===============================================

Cách chạy:
  python main.py                 → chạy cả 2 module 1 lần (test)
  python main.py --btc-only      → chỉ chạy BTC report 1 lần
  python main.py --alt-only      → chỉ chạy Alt scan 1 lần
  python main.py --dry-run       → chạy không gọi GPT, không gửi Telegram
  python main.py --btc-alert     → chỉ chạy BTC alert check
  python main.py --schedule      → chạy tự động theo lịch (production)

Lịch khi --schedule:
  BTC full report : mỗi 24h
  BTC alert check : mỗi 1h
  Alt scan        : mỗi 6h
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
    _section("BTC DAILY REPORT")
    try:
        raw      = btc_fetch.fetch_all_btc_data()
        analysis = btc_analyze.run_analysis(raw)
        analysis = btc_analyze.generate_scenario_analysis(analysis, OPENAI_API_KEY)
        message  = btc_report.build_daily_report(analysis, raw["timestamp"])
        btc_report.send_telegram(message)
        db.save_btc_report(analysis)
        # Lưu key levels để smart alert dùng
        db.save_btc_key_levels(
            price      = analysis.price,
            resistance = analysis.dca_zone_high or analysis.price * 1.05,
            support    = analysis.dca_zone_low  or analysis.ma50w or analysis.price * 0.92,
        )
        print(f"[BTC] ✅ Score={analysis.overall_score}/100 | {analysis.recommendation}")
    except Exception as e:
        print(f"[BTC] ❌ Lỗi: {e}")
        import traceback; traceback.print_exc()


def run_btc_alert_check():
    """
    Smart alert: chỉ gửi khi giá chạm/phá key level từ lần phân tích trước.
    Fallback về pump/dump % nếu không có key levels.
    """
    try:
        raw      = btc_fetch.fetch_all_btc_data()
        analysis = btc_analyze.run_analysis(raw)
        change   = analysis.change_24h
        price    = analysis.price
        ts       = raw["timestamp"]

        # Lấy key levels từ lần phân tích trước
        prev_levels = db.get_last_btc_key_levels()
        prev_res = prev_levels["resistance"] if prev_levels else 0
        prev_sup = prev_levels["support"]    if prev_levels else 0

        should_alert = False
        alert_reason = ""

        if prev_res > 0 or prev_sup > 0:
            # Smart check: giá chạm/phá level
            near_resistance = prev_res > 0 and abs(price - prev_res) / prev_res < 0.015
            broke_resistance = prev_res > 0 and price > prev_res * 1.01
            near_support    = prev_sup > 0 and abs(price - prev_sup) / prev_sup < 0.015
            broke_support   = prev_sup > 0 and price < prev_sup * 0.99

            if broke_resistance:
                should_alert = True
                alert_reason = f"BREAKOUT kháng cự ${prev_res:,.0f}"
            elif near_resistance:
                should_alert = True
                alert_reason = f"TEST kháng cự ${prev_res:,.0f}"
            elif broke_support:
                should_alert = True
                alert_reason = f"BREAKDOWN hỗ trợ ${prev_sup:,.0f}"
            elif near_support:
                should_alert = True
                alert_reason = f"TEST hỗ trợ ${prev_sup:,.0f}"
        else:
            # Fallback: dùng % thay đổi nếu chưa có key levels
            if change <= BTC_DROP_ALERT_PCT:
                should_alert = True
                alert_reason = f"Dump {change:.1f}%"
            elif change >= BTC_PUMP_ALERT_PCT:
                should_alert = True
                alert_reason = f"Pump +{change:.1f}%"

        if should_alert:
            # Xác định cur_type và cur_level
            if prev_res > 0 and price > prev_res * 1.01:
                cur_type = "BREAKOUT";    cur_level = prev_res
            elif prev_res > 0 and abs(price - prev_res) / prev_res < 0.015:
                cur_type = "RESISTANCE";  cur_level = prev_res
            elif prev_sup > 0 and price < prev_sup * 0.99:
                cur_type = "BREAKDOWN";   cur_level = prev_sup
            elif prev_sup > 0 and abs(price - prev_sup) / prev_sup < 0.015:
                cur_type = "SUPPORT_TEST"; cur_level = prev_sup
            else:
                cur_type = "MOVE";        cur_level = price

            # Dedup: chỉ gửi nếu event mới HOẶC giá di chuyển > 3%
            last_alert      = db.get_last_btc_alert()
            already_sent    = False
            if last_alert:
                last_type   = last_alert.get("level_type", "")
                last_level  = float(last_alert.get("level_price") or 0)
                last_price  = float(last_alert.get("btc_price")   or 0)
                same_event  = (last_type == cur_type and
                               last_level > 0 and
                               abs(last_level - cur_level) < cur_level * 0.005)
                barely_moved = (last_price > 0 and
                                abs(price - last_price) / last_price < 0.03)
                already_sent = same_event and barely_moved

            if not already_sent:
                print(f"[BTC Alert] ⚡ {alert_reason} → gửi")
                msg = btc_report.build_smart_alert(analysis, "MOVE", ts, prev_res, prev_sup)
                btc_report.send_telegram(msg)
                db.save_btc_alert("MOVE", cur_type, cur_level, price)
            else:
                print(f"[BTC Alert] ⏭  Bỏ qua — cùng event, giá chưa di chuyển đáng kể")
        else:
            print(f"[BTC Alert] OK — Price: ${price:,.0f} | 24H: {change:+.2f}%"
                  + (f" | Res: ${prev_res:,.0f} | Sup: ${prev_sup:,.0f}" if prev_res else ""))

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

        # 3. CMC cross-check
        if CMC_ENABLED:
            filtered = alt_scan.enrich_with_cmc(filtered, CMC_API_KEY)

        # 4. Categories (smart: infer keyword trước, API sau)
        filtered = alt_scan.fetch_categories_bulk(filtered, max_api_calls=30)

        # 5. Binance OHLCV
        filtered = alt_scan.enrich_with_binance(filtered)

        # 6. Score
        scored = alt_score.score_all(filtered)

        # Print top 20
        print(f"\n[Alt] Top 20:")
        for i, s in enumerate(scored[:20], 1):
            disc = "⚠️ " if s.coin.has_discrepancy else "   "
            wfl  = "⏳" if s.wait_for_level else "  "
            print(f"  {i:2}. {disc}{wfl}{s.coin.symbol:10} {s.total_score:3}/100  "
                  f"7D:{s.coin.change_7d:+6.1f}%  "
                  f"T1:${s.target_1:.3f}(+{s.target_1_pct:.0f}%)  "
                  f"{s.narrative_label}")

        # 7. GPT analysis
        if not dry_run and OPENAI_API_KEY.startswith("sk-"):
            results = alt_analyst_mod.analyze_top_coins(
                scored,
                threshold=ALT_SCORE_THRESHOLD,
                max_coins=ALT_MAX_ANALYZE,
            )
        else:
            print("[Alt] Fallback analysis (no GPT)")
            results = [
                {"scored_coin": s, "analysis": alt_analyst_mod._fallback_analysis(s)}
                for s in scored[:ALT_MAX_ANALYZE]
                if s.total_score >= ALT_SCORE_THRESHOLD
            ]

        # 8. Lưu DB + cleanup cũ
        db.save_alt_scan(ts, len(coins), len(filtered), results)
        db.cleanup_old_scans(keep_last_n=2)   # chỉ giữ 2 scan gần nhất
        stats = db.get_db_stats()
        print(f"[DB] Stats: {stats}")

        # 9. Gửi Telegram
        alt_report.send_full_report(results, ts, len(coins))
        print(f"\n[Alt] ✅ {len(results)} coin phân tích xong.")

    except Exception as e:
        print(f"[Alt] ❌ Lỗi: {e}")
        import traceback; traceback.print_exc()


# ════════════════════════════════════════════════════════════
#  SCHEDULER
# ════════════════════════════════════════════════════════════

def start_scheduler(dry_run: bool = False):
    db.init_db()
    print("\n" + "="*55)
    print("  CRYPTO BOT — SCHEDULER KHỞI ĐỘNG")
    print("="*55)
    print(f"  BTC report  : mỗi {BTC_REPORT_INTERVAL_HOURS}h")
    print(f"  BTC alert   : mỗi {BTC_ALERT_CHECK_HOURS}h")
    print(f"  Alt scan    : mỗi {ALT_SCAN_INTERVAL_HOURS}h")
    print(f"  CMC check   : {'✅ bật' if CMC_ENABLED else '❌ tắt'}")
    print(f"  GPT analyze : {'✅ bật' if OPENAI_API_KEY.startswith('sk-') else '❌ tắt'}")
    print(f"  Telegram    : {'✅ bật' if TELEGRAM_BOT_TOKEN != 'YOUR_BOT_TOKEN' else '❌ in console'}")
    print("="*55)

    # Chạy ngay lần đầu
    print("\n[Boot] Chạy lần đầu...")
    run_btc_report()
    run_alt_scan(dry_run=dry_run)

    # Đặt lịch
    schedule.every(BTC_REPORT_INTERVAL_HOURS).hours.do(run_btc_report)
    schedule.every(BTC_ALERT_CHECK_HOURS).hours.do(run_btc_alert_check)
    schedule.every(ALT_SCAN_INTERVAL_HOURS).hours.do(run_alt_scan, dry_run=dry_run)

    print("\n[Scheduler] Đang chạy... (Ctrl+C để dừng)\n")
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
    parser = argparse.ArgumentParser(description="Crypto Bot — BTC + Alt Scanner")
    parser.add_argument("--schedule",  action="store_true", help="Chạy tự động theo lịch")
    parser.add_argument("--btc-only",  action="store_true", help="Chỉ chạy BTC module")
    parser.add_argument("--alt-only",  action="store_true", help="Chỉ chạy Alt scanner")
    parser.add_argument("--dry-run",   action="store_true", help="Không gọi GPT, in console")
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
