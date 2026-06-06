"""
database.py
Hỗ trợ 2 chế độ:
  1) PostgreSQL/Supabase nếu có biến môi trường DATABASE_URL
  2) SQLite local crypto_bot.db nếu chưa cấu hình DATABASE_URL

Nhờ vậy local bot và Streamlit Cloud có thể dùng chung Supabase database.
"""

import os
import sqlite3
import json
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

DB_PATH = Path(__file__).parent / "crypto_bot.db"
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
USE_POSTGRES = bool(DATABASE_URL)


def _normalize_database_url(url: str) -> str:
    """Supabase đôi khi đưa URL dạng postgresql:// hoặc postgres://; psycopg2 dùng được cả hai."""
    return url.strip()


def get_conn():
    """Trả connection theo DATABASE_URL nếu có, ngược lại dùng SQLite local."""
    if USE_POSTGRES:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        conn = psycopg2.connect(_normalize_database_url(DATABASE_URL), cursor_factory=RealDictCursor)
        return conn

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _rows_to_dicts(rows):
    return [dict(r) for r in rows]


def _one_to_dict(row):
    return dict(row) if row else None


def _execute_many(cursor, statements: list[str]):
    for sql in statements:
        cursor.execute(sql)


def init_db():
    """Tạo tables nếu chưa có. Gọi 1 lần khi boot."""
    conn = get_conn()
    c = conn.cursor()

    if USE_POSTGRES:
        statements = [
            """
            CREATE TABLE IF NOT EXISTS btc_history (
                id                  SERIAL PRIMARY KEY,
                timestamp           TEXT NOT NULL,
                price               DOUBLE PRECISION,
                change_24h          DOUBLE PRECISION,
                change_7d           DOUBLE PRECISION,
                change_30d          DOUBLE PRECISION,
                dominance           DOUBLE PRECISION,
                ma50w               DOUBLE PRECISION,
                ma200w              DOUBLE PRECISION,
                trend_structure     TEXT,
                cycle_phase         TEXT,
                mvrv_proxy_score    INTEGER,
                fear_greed          INTEGER,
                fear_greed_label    TEXT,
                dxy                 DOUBLE PRECISION,
                overall_score       INTEGER,
                technical_score     INTEGER,
                macro_score         INTEGER,
                cycle_score         INTEGER,
                recommendation      TEXT,
                created_at          TIMESTAMPTZ DEFAULT NOW()
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS alt_scans (
                id              SERIAL PRIMARY KEY,
                timestamp       TEXT NOT NULL,
                total_scanned   INTEGER,
                total_filtered  INTEGER,
                total_analyzed  INTEGER,
                created_at      TIMESTAMPTZ DEFAULT NOW()
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS alt_results (
                id                  SERIAL PRIMARY KEY,
                scan_id             INTEGER REFERENCES alt_scans(id),
                timestamp           TEXT NOT NULL,
                symbol              TEXT,
                name                TEXT,
                price               DOUBLE PRECISION,
                market_cap          DOUBLE PRECISION,
                volume_24h          DOUBLE PRECISION,
                change_24h          DOUBLE PRECISION,
                change_7d           DOUBLE PRECISION,
                change_30d          DOUBLE PRECISION,
                volume_spike        DOUBLE PRECISION,
                fdv_mc_ratio        DOUBLE PRECISION,
                narrative           TEXT,
                total_score         INTEGER,
                narrative_score     INTEGER,
                momentum_score      INTEGER,
                volume_score        INTEGER,
                tokenomics_score    INTEGER,
                sentiment_score     INTEGER,
                bonus_score         INTEGER,
                has_discrepancy     INTEGER DEFAULT 0,
                discrepancy_notes   TEXT,
                action              TEXT,
                thesis              TEXT,
                catalysts           TEXT,
                risks               TEXT,
                invalidation        TEXT,
                upside_conservative TEXT,
                upside_bull         TEXT,
                dca_note            TEXT,
                scenario_bullish    TEXT,
                entry_condition     TEXT,
                created_at          TIMESTAMPTZ DEFAULT NOW()
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS coin_score_history (
                id          SERIAL PRIMARY KEY,
                symbol      TEXT NOT NULL,
                timestamp   TEXT NOT NULL,
                price       DOUBLE PRECISION,
                score       INTEGER,
                action      TEXT,
                created_at  TIMESTAMPTZ DEFAULT NOW()
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_coin_symbol ON coin_score_history(symbol)",
            "CREATE INDEX IF NOT EXISTS idx_btc_ts ON btc_history(timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_alt_scans_created ON alt_scans(created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_alt_results_scan ON alt_results(scan_id)",
        ]
    else:
        statements = [
            """
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
            """,
            """
            CREATE TABLE IF NOT EXISTS alt_scans (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp       TEXT NOT NULL,
                total_scanned   INTEGER,
                total_filtered  INTEGER,
                total_analyzed  INTEGER,
                created_at      TEXT DEFAULT (datetime('now'))
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS alt_results (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                scan_id             INTEGER REFERENCES alt_scans(id),
                timestamp           TEXT NOT NULL,
                symbol              TEXT,
                name                TEXT,
                price               REAL,
                market_cap          REAL,
                volume_24h          REAL,
                change_24h          REAL,
                change_7d           REAL,
                change_30d          REAL,
                volume_spike        REAL,
                fdv_mc_ratio        REAL,
                narrative           TEXT,
                total_score         INTEGER,
                narrative_score     INTEGER,
                momentum_score      INTEGER,
                volume_score        INTEGER,
                tokenomics_score    INTEGER,
                sentiment_score     INTEGER,
                bonus_score         INTEGER,
                has_discrepancy     INTEGER DEFAULT 0,
                discrepancy_notes   TEXT,
                action              TEXT,
                thesis              TEXT,
                catalysts           TEXT,
                risks               TEXT,
                invalidation        TEXT,
                upside_conservative TEXT,
                upside_bull         TEXT,
                dca_note            TEXT,
                scenario_bullish    TEXT,
                entry_condition     TEXT,
                created_at          TEXT DEFAULT (datetime('now'))
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS coin_score_history (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol      TEXT NOT NULL,
                timestamp   TEXT NOT NULL,
                price       REAL,
                score       INTEGER,
                action      TEXT,
                created_at  TEXT DEFAULT (datetime('now'))
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_coin_symbol ON coin_score_history(symbol)",
            "CREATE INDEX IF NOT EXISTS idx_btc_ts ON btc_history(timestamp)",
        ]

    _execute_many(c, statements)
    conn.commit()
    conn.close()
    # Migration: thêm cột mới nếu chưa có (tương thích DB cũ)
    try:
        conn2 = get_conn()
        c2 = conn2.cursor()
        if USE_POSTGRES:
            for col, col_type in [("scenario_bullish", "TEXT"), ("entry_condition", "TEXT")]:
                c2.execute(f"ALTER TABLE alt_results ADD COLUMN IF NOT EXISTS {col} {col_type}")
        else:
            c2.execute("PRAGMA table_info(alt_results)")
            existing = [r["name"] if isinstance(r, dict) else r[1] for r in c2.fetchall()]
            for col, col_type in [("scenario_bullish", "TEXT"), ("entry_condition", "TEXT")]:
                if col not in existing:
                    c2.execute(f"ALTER TABLE alt_results ADD COLUMN {col} {col_type}")
        conn2.commit()
        conn2.close()
        print("[DB] Migration OK")
    except Exception as e:
        print(f"[DB Migration] {e}")

    target = "Supabase/PostgreSQL" if USE_POSTGRES else str(DB_PATH)
    print(f"[DB] Database ready: {target}")


def save_btc_report(analysis) -> int:
    """Lưu BTCAnalysis vào DB. Trả về row id."""
    conn = get_conn()
    c = conn.cursor()

    values = (
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
    )

    if USE_POSTGRES:
        c.execute("""
            INSERT INTO btc_history (
                timestamp, price, change_24h, change_7d, change_30d,
                dominance, ma50w, ma200w, trend_structure, cycle_phase,
                mvrv_proxy_score, fear_greed, fear_greed_label, dxy,
                overall_score, technical_score, macro_score, cycle_score,
                recommendation
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id
        """, values)
        row_id = c.fetchone()["id"]
    else:
        c.execute("""
            INSERT INTO btc_history (
                timestamp, price, change_24h, change_7d, change_30d,
                dominance, ma50w, ma200w, trend_structure, cycle_phase,
                mvrv_proxy_score, fear_greed, fear_greed_label, dxy,
                overall_score, technical_score, macro_score, cycle_score,
                recommendation
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, values)
        row_id = c.lastrowid

    conn.commit()
    conn.close()
    return row_id


def get_btc_history(days: int = 30) -> list[dict]:
    conn = get_conn()
    c = conn.cursor()
    if USE_POSTGRES:
        c.execute("""
            SELECT * FROM btc_history
            WHERE created_at >= NOW() - (%s || ' days')::interval
            ORDER BY created_at ASC
        """, (days,))
    else:
        c.execute("""
            SELECT * FROM btc_history
            WHERE created_at >= datetime('now', ?)
            ORDER BY created_at ASC
        """, (f"-{days} days",))
    rows = _rows_to_dicts(c.fetchall())
    conn.close()
    return rows


def get_latest_btc() -> dict | None:
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM btc_history ORDER BY created_at DESC LIMIT 1")
    row = c.fetchone()
    conn.close()
    return _one_to_dict(row)


def save_alt_scan(timestamp: str, total_scanned: int, total_filtered: int, results: list) -> int:
    conn = get_conn()
    c = conn.cursor()

    if USE_POSTGRES:
        c.execute("""
            INSERT INTO alt_scans (timestamp, total_scanned, total_filtered, total_analyzed)
            VALUES (%s,%s,%s,%s)
            RETURNING id
        """, (timestamp, total_scanned, total_filtered, len(results)))
        scan_id = c.fetchone()["id"]
    else:
        c.execute("""
            INSERT INTO alt_scans (timestamp, total_scanned, total_filtered, total_analyzed)
            VALUES (?,?,?,?)
        """, (timestamp, total_scanned, total_filtered, len(results)))
        scan_id = c.lastrowid

    result_sql_pg = """
        INSERT INTO alt_results (
            scan_id, timestamp, symbol, name, price, market_cap,
            volume_24h, change_24h, change_7d, change_30d,
            volume_spike, fdv_mc_ratio, narrative, total_score,
            narrative_score, momentum_score, volume_score,
            tokenomics_score, sentiment_score, bonus_score,
            has_discrepancy, discrepancy_notes,
            action, thesis, catalysts, risks, invalidation,
            upside_conservative, upside_bull, dca_note,
            scenario_bullish, entry_condition
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """
    result_sql_sqlite = result_sql_pg.replace("%s", "?")

    hist_sql_pg = """
        INSERT INTO coin_score_history (symbol, timestamp, price, score, action)
        VALUES (%s,%s,%s,%s,%s)
    """
    hist_sql_sqlite = hist_sql_pg.replace("%s", "?")

    for r in results:
        sc = r["scored_coin"]
        an = r["analysis"]
        coin = sc.coin
        upside = an.get("upside", {})

        vals = (
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
            an.get("scenario_bullish", "") or an.get("upside", {}).get("bull_case", ""),
            an.get("entry_condition", "") or an.get("dca_note", ""),
        )
        c.execute(result_sql_pg if USE_POSTGRES else result_sql_sqlite, vals)
        c.execute(hist_sql_pg if USE_POSTGRES else hist_sql_sqlite, (
            coin.symbol, timestamp, coin.price, sc.total_score, an.get("action", "WATCH")
        ))

    conn.commit()
    conn.close()
    return scan_id


def get_latest_alt_scan() -> list[dict]:
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id FROM alt_scans ORDER BY created_at DESC LIMIT 1")
    row = c.fetchone()
    if not row:
        conn.close()
        return []
    scan_id = row["id"] if isinstance(row, dict) else row["id"]
    if USE_POSTGRES:
        c.execute("""
            SELECT * FROM alt_results
            WHERE scan_id = %s
            ORDER BY total_score DESC
        """, (scan_id,))
    else:
        c.execute("""
            SELECT * FROM alt_results
            WHERE scan_id = ?
            ORDER BY total_score DESC
        """, (scan_id,))
    rows = _rows_to_dicts(c.fetchall())
    conn.close()
    for r in rows:
        r["catalysts"] = json.loads(r.get("catalysts") or "[]")
        r["risks"] = json.loads(r.get("risks") or "[]")
        r["discrepancy_notes"] = json.loads(r.get("discrepancy_notes") or "[]")
    return rows


def get_all_alt_scans(limit: int = 20) -> list[dict]:
    conn = get_conn()
    c = conn.cursor()
    if USE_POSTGRES:
        c.execute("SELECT * FROM alt_scans ORDER BY created_at DESC LIMIT %s", (limit,))
    else:
        c.execute("SELECT * FROM alt_scans ORDER BY created_at DESC LIMIT ?", (limit,))
    rows = _rows_to_dicts(c.fetchall())
    conn.close()
    return rows


def get_coin_score_history(symbol: str, days: int = 30) -> list[dict]:
    conn = get_conn()
    c = conn.cursor()
    if USE_POSTGRES:
        c.execute("""
            SELECT * FROM coin_score_history
            WHERE symbol = %s
              AND created_at >= NOW() - (%s || ' days')::interval
            ORDER BY created_at ASC
        """, (symbol.upper(), days))
    else:
        c.execute("""
            SELECT * FROM coin_score_history
            WHERE symbol = ?
              AND created_at >= datetime('now', ?)
            ORDER BY created_at ASC
        """, (symbol.upper(), f"-{days} days"))
    rows = _rows_to_dicts(c.fetchall())
    conn.close()
    return rows


def get_top_recurring_coins(min_appearances: int = 2, days: int = 30) -> list[dict]:
    conn = get_conn()
    c = conn.cursor()
    if USE_POSTGRES:
        c.execute("""
            SELECT symbol,
                   COUNT(*) AS appearances,
                   AVG(score) AS avg_score,
                   MAX(score) AS max_score,
                   MAX(created_at) AS last_seen,
                   (ARRAY_AGG(action ORDER BY created_at DESC))[1] AS last_action
            FROM coin_score_history
            WHERE created_at >= NOW() - (%s || ' days')::interval
            GROUP BY symbol
            HAVING COUNT(*) >= %s
            ORDER BY avg_score DESC
        """, (days, min_appearances))
    else:
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
    rows = _rows_to_dicts(c.fetchall())
    conn.close()
    return rows


if __name__ == "__main__":
    init_db()
    print("DB initialized OK")
    print("Mode:", "PostgreSQL/Supabase" if USE_POSTGRES else "SQLite local")


def cleanup_old_scans(keep_last_n: int = 2):
    """Xóa alt_scans cũ, chỉ giữ N scan gần nhất."""
    conn = get_conn()
    c    = conn.cursor()

    if USE_POSTGRES:
        c.execute("SELECT id FROM alt_scans ORDER BY created_at DESC LIMIT %s", (keep_last_n,))
    else:
        c.execute("SELECT id FROM alt_scans ORDER BY created_at DESC LIMIT ?", (keep_last_n,))

    rows     = c.fetchall()
    keep_ids = [r["id"] if isinstance(r, dict) else r[0] for r in rows]

    if not keep_ids:
        conn.close()
        return 0

    if USE_POSTGRES:
        ph = ",".join(["%s"] * len(keep_ids))
        c.execute(f"DELETE FROM alt_results WHERE scan_id NOT IN ({ph})", keep_ids)
        c.execute(f"DELETE FROM alt_scans   WHERE id       NOT IN ({ph})", keep_ids)
        c.execute("DELETE FROM coin_score_history WHERE created_at < NOW() - INTERVAL '7 days'")
        c.execute("DELETE FROM btc_history WHERE created_at < NOW() - INTERVAL '30 days'")
    else:
        ph = ",".join(["?"] * len(keep_ids))
        c.execute(f"DELETE FROM alt_results WHERE scan_id NOT IN ({ph})", keep_ids)
        c.execute(f"DELETE FROM alt_scans   WHERE id       NOT IN ({ph})", keep_ids)
        c.execute("DELETE FROM coin_score_history WHERE created_at < datetime('now','-7 days')")
        c.execute("DELETE FROM btc_history WHERE created_at < datetime('now','-30 days')")

    conn.commit()
    conn.close()
    print(f"[DB Cleanup] Giữ lại {keep_last_n} scan gần nhất. Đã xóa data cũ.")
    return keep_last_n


def get_db_stats() -> dict:
    """Thống kê số rows từng table."""
    conn = get_conn()
    c    = conn.cursor()
    stats = {}
    for table in ["btc_history", "alt_scans", "alt_results", "coin_score_history"]:
        if USE_POSTGRES:
            c.execute(f"SELECT COUNT(*) as cnt FROM {table}")
        else:
            c.execute(f"SELECT COUNT(*) as cnt FROM {table}")
        row = c.fetchone()
        stats[table] = row["cnt"] if isinstance(row, dict) else row[0]
    conn.close()
    return stats


def save_btc_key_levels(price: float, resistance: float, support: float):
    """Lưu key levels BTC để dùng cho smart alert."""
    conn = get_conn()
    c    = conn.cursor()
    if USE_POSTGRES:
        c.execute("""
            CREATE TABLE IF NOT EXISTS btc_key_levels (
                id SERIAL PRIMARY KEY, price DOUBLE PRECISION,
                resistance DOUBLE PRECISION, support DOUBLE PRECISION,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )""")
        c.execute("INSERT INTO btc_key_levels (price,resistance,support) VALUES (%s,%s,%s)",
                  (price, resistance, support))
    else:
        c.execute("""
            CREATE TABLE IF NOT EXISTS btc_key_levels (
                id INTEGER PRIMARY KEY AUTOINCREMENT, price REAL,
                resistance REAL, support REAL,
                created_at TEXT DEFAULT (datetime('now'))
            )""")
        c.execute("INSERT INTO btc_key_levels (price,resistance,support) VALUES (?,?,?)",
                  (price, resistance, support))
    conn.commit()
    conn.close()


def get_last_btc_key_levels() -> dict:
    """Lấy key levels từ lần phân tích trước."""
    conn = get_conn()
    c    = conn.cursor()
    try:
        c.execute("SELECT * FROM btc_key_levels ORDER BY created_at DESC LIMIT 1")
        row = c.fetchone()
        conn.close()
        return _one_to_dict(row)
    except:
        conn.close()
        return None
