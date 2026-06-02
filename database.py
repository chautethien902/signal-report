"""
database.py
SQLite database — lưu lịch sử BTC report và Alt scan.

Tables:
  btc_history    → lịch sử BTC score, giá, recommendation theo thời gian
  alt_scans      → mỗi lần scan alt là 1 record
  alt_results    → coin nào được analyze trong mỗi scan
  alt_coin_scores → lịch sử score của từng coin qua các lần scan
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path

# DB file nằm cùng thư mục với code
DB_PATH = Path(__file__).parent / "crypto_bot.db"


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row   # truy cập column bằng tên
    return conn


def init_db():
    """Tạo tables nếu chưa có. Gọi 1 lần khi boot."""
    conn = get_conn()
    c    = conn.cursor()

    # ── BTC history ──────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS btc_history (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp           TEXT NOT NULL,
            price               REAL,
            change_24h          REAL,
            change_7d           REAL,
            change_30d          REAL,
            dominance           REAL,
            ma50w               REAL,
            ma200w              REAL,
            trend_structure     TEXT,
            cycle_phase         TEXT,
            mvrv_proxy_score    INTEGER,
            fear_greed          INTEGER,
            fear_greed_label    TEXT,
            dxy                 REAL,
            overall_score       INTEGER,
            technical_score     INTEGER,
            macro_score         INTEGER,
            cycle_score         INTEGER,
            recommendation      TEXT,
            created_at          TEXT DEFAULT (datetime('now'))
        )
    """)

    # ── Alt scan sessions ─────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS alt_scans (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp       TEXT NOT NULL,
            total_scanned   INTEGER,
            total_filtered  INTEGER,
            total_analyzed  INTEGER,
            created_at      TEXT DEFAULT (datetime('now'))
        )
    """)

    # ── Alt coin results (per scan) ───────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS alt_results (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            scan_id         INTEGER REFERENCES alt_scans(id),
            timestamp       TEXT NOT NULL,
            symbol          TEXT,
            name            TEXT,
            price           REAL,
            market_cap      REAL,
            volume_24h      REAL,
            change_24h      REAL,
            change_7d       REAL,
            change_30d      REAL,
            volume_spike    REAL,
            fdv_mc_ratio    REAL,
            narrative       TEXT,
            total_score     INTEGER,
            narrative_score INTEGER,
            momentum_score  INTEGER,
            volume_score    INTEGER,
            tokenomics_score INTEGER,
            sentiment_score INTEGER,
            bonus_score     INTEGER,
            has_discrepancy INTEGER DEFAULT 0,
            discrepancy_notes TEXT,
            -- GPT analysis
            action          TEXT,
            thesis          TEXT,
            catalysts       TEXT,   -- JSON array
            risks           TEXT,   -- JSON array
            invalidation    TEXT,
            upside_conservative TEXT,
            upside_bull     TEXT,
            dca_note        TEXT,
            created_at      TEXT DEFAULT (datetime('now'))
        )
    """)

    # ── Coin score history (dùng cho chart trend) ─────────────
    # Mỗi lần coin xuất hiện trong scan → 1 record
    c.execute("""
        CREATE TABLE IF NOT EXISTS coin_score_history (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol      TEXT NOT NULL,
            timestamp   TEXT NOT NULL,
            price       REAL,
            score       INTEGER,
            action      TEXT,
            created_at  TEXT DEFAULT (datetime('now'))
        )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_coin_symbol ON coin_score_history(symbol)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_btc_ts ON btc_history(timestamp)")

    conn.commit()
    conn.close()
    print(f"[DB] Database ready: {DB_PATH}")


# ════════════════════════════════════════════════════════════
#  BTC WRITE / READ
# ════════════════════════════════════════════════════════════

def save_btc_report(analysis) -> int:
    """Lưu BTCAnalysis vào DB. Trả về row id."""
    conn = get_conn()
    c    = conn.cursor()
    c.execute("""
        INSERT INTO btc_history (
            timestamp, price, change_24h, change_7d, change_30d,
            dominance, ma50w, ma200w, trend_structure, cycle_phase,
            mvrv_proxy_score, fear_greed, fear_greed_label, dxy,
            overall_score, technical_score, macro_score, cycle_score,
            recommendation
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        datetime.utcnow().isoformat(),
        analysis.price, analysis.change_24h,
        analysis.change_7d, analysis.change_30d,
        analysis.dominance, analysis.ma50w, analysis.ma200w,
        analysis.trend_structure, analysis.cycle_phase,
        analysis.mvrv_proxy_score, analysis.fear_greed,
        analysis.fear_greed_label, analysis.dxy,
        analysis.overall_score, analysis.technical_score,
        analysis.macro_score, analysis.cycle_score,
        analysis.recommendation,
    ))
    row_id = c.lastrowid
    conn.commit()
    conn.close()
    return row_id


def get_btc_history(days: int = 30) -> list[dict]:
    """Lấy lịch sử BTC N ngày gần nhất."""
    conn = get_conn()
    c    = conn.cursor()
    c.execute("""
        SELECT * FROM btc_history
        WHERE created_at >= datetime('now', ?)
        ORDER BY created_at ASC
    """, (f"-{days} days",))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def get_latest_btc() -> dict | None:
    """Lấy BTC report mới nhất."""
    conn = get_conn()
    c    = conn.cursor()
    c.execute("SELECT * FROM btc_history ORDER BY created_at DESC LIMIT 1")
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


# ════════════════════════════════════════════════════════════
#  ALT WRITE / READ
# ════════════════════════════════════════════════════════════

def save_alt_scan(timestamp: str, total_scanned: int,
                  total_filtered: int, results: list) -> int:
    """
    Lưu 1 lần alt scan vào DB.
    results: list of {scored_coin, analysis} từ alt_analyst
    Trả về scan_id.
    """
    conn = get_conn()
    c    = conn.cursor()

    # Tạo scan session
    c.execute("""
        INSERT INTO alt_scans (timestamp, total_scanned, total_filtered, total_analyzed)
        VALUES (?,?,?,?)
    """, (timestamp, total_scanned, total_filtered, len(results)))
    scan_id = c.lastrowid

    # Lưu từng coin result
    for r in results:
        sc       = r["scored_coin"]
        an       = r["analysis"]
        coin     = sc.coin
        upside   = an.get("upside", {})

        c.execute("""
            INSERT INTO alt_results (
                scan_id, timestamp, symbol, name, price, market_cap,
                volume_24h, change_24h, change_7d, change_30d,
                volume_spike, fdv_mc_ratio, narrative, total_score,
                narrative_score, momentum_score, volume_score,
                tokenomics_score, sentiment_score, bonus_score,
                has_discrepancy, discrepancy_notes,
                action, thesis, catalysts, risks, invalidation,
                upside_conservative, upside_bull, dca_note
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            scan_id, timestamp,
            coin.symbol, coin.name, coin.price, coin.market_cap,
            coin.volume_24h, coin.change_24h, coin.change_7d, coin.change_30d,
            coin.volume_spike, coin.fdv_mc_ratio,
            sc.narrative_label, sc.total_score,
            sc.score_breakdown.get("Narrative", 0),
            sc.score_breakdown.get("Momentum", 0),
            sc.score_breakdown.get("Volume", 0),
            sc.score_breakdown.get("Tokenomics", 0),
            sc.score_breakdown.get("Sentiment", 0),
            sc.score_breakdown.get("Bonus", 0),
            1 if coin.has_discrepancy else 0,
            json.dumps(coin.discrepancy_notes),
            an.get("action", "WATCH"),
            an.get("thesis", ""),
            json.dumps(an.get("catalyst", [])),
            json.dumps(an.get("risks", [])),
            an.get("invalidation", ""),
            upside.get("conservative", ""),
            upside.get("bull_case", ""),
            an.get("dca_note", ""),
        ))

        # Lưu vào coin_score_history để vẽ chart trend
        c.execute("""
            INSERT INTO coin_score_history (symbol, timestamp, price, score, action)
            VALUES (?,?,?,?,?)
        """, (
            coin.symbol, timestamp, coin.price,
            sc.total_score, an.get("action", "WATCH"),
        ))

    conn.commit()
    conn.close()
    return scan_id


def get_latest_alt_scan() -> list[dict]:
    """Lấy kết quả scan alt mới nhất."""
    conn = get_conn()
    c    = conn.cursor()
    c.execute("SELECT id FROM alt_scans ORDER BY created_at DESC LIMIT 1")
    row = c.fetchone()
    if not row:
        conn.close()
        return []
    scan_id = row["id"]
    c.execute("""
        SELECT * FROM alt_results
        WHERE scan_id = ?
        ORDER BY total_score DESC
    """, (scan_id,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    # Parse JSON fields
    for r in rows:
        r["catalysts"]         = json.loads(r.get("catalysts") or "[]")
        r["risks"]             = json.loads(r.get("risks") or "[]")
        r["discrepancy_notes"] = json.loads(r.get("discrepancy_notes") or "[]")
    return rows


def get_all_alt_scans(limit: int = 20) -> list[dict]:
    """Lấy N scan gần nhất (metadata)."""
    conn = get_conn()
    c    = conn.cursor()
    c.execute("""
        SELECT * FROM alt_scans
        ORDER BY created_at DESC LIMIT ?
    """, (limit,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def get_coin_score_history(symbol: str, days: int = 30) -> list[dict]:
    """Lịch sử score của 1 coin cụ thể."""
    conn = get_conn()
    c    = conn.cursor()
    c.execute("""
        SELECT * FROM coin_score_history
        WHERE symbol = ?
          AND created_at >= datetime('now', ?)
        ORDER BY created_at ASC
    """, (symbol.upper(), f"-{days} days"))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def get_top_recurring_coins(min_appearances: int = 2, days: int = 30) -> list[dict]:
    """
    Coin nào xuất hiện nhiều lần trong N ngày qua → tín hiệu bền hơn.
    """
    conn = get_conn()
    c    = conn.cursor()
    c.execute("""
        SELECT symbol,
               COUNT(*)        AS appearances,
               AVG(score)      AS avg_score,
               MAX(score)      AS max_score,
               MAX(created_at) AS last_seen,
               MAX(CASE WHEN created_at = (SELECT MAX(created_at) FROM coin_score_history c2 WHERE c2.symbol = c1.symbol) THEN action END) AS last_action
        FROM coin_score_history c1
        WHERE created_at >= datetime('now', ?)
        GROUP BY symbol
        HAVING COUNT(*) >= ?
        ORDER BY avg_score DESC
    """, (f"-{days} days", min_appearances))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


if __name__ == "__main__":
    init_db()
    print("DB initialized OK")
    print(f"Path: {DB_PATH}")
