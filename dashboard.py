"""
dashboard.py — Crypto Bot Dashboard
=====================================
Chạy: streamlit run dashboard.py
Mở browser: http://localhost:8501
"""

import json
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
from pathlib import Path

# Import database
import sys
sys.path.insert(0, str(Path(__file__).parent))
import database as db

# ── Page config ───────────────────────────────────────────────
st.set_page_config(
    page_title="Crypto Bot Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────
st.markdown("""
<style>
  .metric-card {
    background: #1e2130;
    border-radius: 10px;
    padding: 16px 20px;
    border-left: 4px solid #4c9fff;
  }
  .rec-strong-buy  { color: #00e676; font-weight: bold; font-size: 1.2em; }
  .rec-buy         { color: #69f0ae; font-weight: bold; }
  .rec-watch       { color: #ffd740; font-weight: bold; }
  .rec-avoid       { color: #ff6e6e; font-weight: bold; }
  .rec-danger      { color: #ff1744; font-weight: bold; font-size: 1.2em; }
  .score-high      { color: #00e676; }
  .score-mid       { color: #ffd740; }
  .score-low       { color: #ff6e6e; }
  .stTabs [data-baseweb="tab"] { font-size: 15px; }
</style>
""", unsafe_allow_html=True)

# ── Init DB ───────────────────────────────────────────────────
db.init_db()


# ════════════════════════════════════════════════════════════
#  HELPERS
# ════════════════════════════════════════════════════════════

def fmt_price(n):
    if n is None: return "N/A"
    if n >= 1:    return f"${n:,.3f}"
    if n >= 0.01: return f"${n:,.4f}"
    return f"${n:,.6f}"

def fmt_mc(n):
    if n is None: return "N/A"
    if n >= 1e9:  return f"${n/1e9:.2f}B"
    return f"${n/1e6:.0f}M"

def fmt_pct(n, show_arrow=True):
    if n is None: return "N/A"
    arrow = "↑" if n >= 0 else "↓"
    color = "green" if n >= 0 else "red"
    a     = arrow if show_arrow else ""
    return f'<span style="color:{color}">{a}{n:+.2f}%</span>'

def rec_class(rec):
    m = {
        "STRONG BUY": "rec-strong-buy",
        "BUY":        "rec-buy",
        "WATCH":      "rec-watch",
        "AVOID":      "rec-avoid",
        "DANGER":     "rec-danger",
    }
    return m.get(rec, "rec-watch")

def action_color(action):
    return {"ACCUMULATE": "#00e676", "WATCH": "#ffd740", "AVOID": "#ff6e6e"}.get(action, "#aaa")

def score_color(s):
    if s >= 70: return "#00e676"
    if s >= 50: return "#ffd740"
    return "#ff6e6e"


# ════════════════════════════════════════════════════════════
#  SIDEBAR
# ════════════════════════════════════════════════════════════

with st.sidebar:
    st.title("🤖 Crypto Bot")
    st.markdown("---")

    page = st.radio("Navigation", [
        "📊 Overview",
        "₿  BTC Analysis",
        "🔍 Alt Scanner",
        "📈 Coin History",
        "⭐ Top Recurring",
    ])

    st.markdown("---")
    if st.button("🔄 Refresh data"):
        st.cache_data.clear()
        st.rerun()

    st.caption(f"Last refresh: {datetime.now().strftime('%H:%M:%S')}")


# ════════════════════════════════════════════════════════════
#  OVERVIEW PAGE
# ════════════════════════════════════════════════════════════

if page == "📊 Overview":
    st.title("📊 Overview")

    btc   = db.get_latest_btc()
    alts  = db.get_latest_alt_scan()
    scans = db.get_all_alt_scans(limit=5)

    # ── BTC snapshot ─────────────────────────────────────────
    st.subheader("₿ BTC Snapshot")
    if btc:
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Giá",       fmt_price(btc["price"]))
        c2.metric("24H",       f"{btc['change_24h']:+.2f}%")
        c3.metric("Score",     f"{btc['overall_score']}/100")
        c4.metric("Cycle",     btc["cycle_phase"] or "N/A")
        c5.metric("Rec",       btc["recommendation"] or "N/A")

        rec = btc.get("recommendation", "WATCH")
        st.markdown(
            f'<p>BTC Recommendation: <span class="{rec_class(rec)}">{rec}</span></p>',
            unsafe_allow_html=True
        )
    else:
        st.info("Chưa có BTC data. Chạy bot trước: `python main.py --btc-only`")

    st.markdown("---")

    # ── Alt snapshot ─────────────────────────────────────────
    st.subheader("🔍 Latest Alt Scan")
    if alts:
        cols = st.columns(4)
        accumulate = [a for a in alts if a.get("action") == "ACCUMULATE"]
        watch      = [a for a in alts if a.get("action") == "WATCH"]
        avoid      = [a for a in alts if a.get("action") == "AVOID"]
        cols[0].metric("Coin analyzed", len(alts))
        cols[1].metric("🟢 ACCUMULATE", len(accumulate))
        cols[2].metric("🟡 WATCH",      len(watch))
        cols[3].metric("🔴 AVOID",      len(avoid))

        # Mini table
        df = pd.DataFrame([{
            "Symbol":    a["symbol"],
            "Score":     a["total_score"],
            "Action":    a["action"],
            "7D %":      f"{a['change_7d']:+.1f}%",
            "Narrative": a["narrative"] or "",
        } for a in alts])
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("Chưa có Alt scan data. Chạy: `python main.py --alt-only`")

    st.markdown("---")

    # ── Scan history ─────────────────────────────────────────
    st.subheader("📋 Scan History")
    if scans:
        df2 = pd.DataFrame([{
            "Timestamp":  s["timestamp"],
            "Scanned":    s["total_scanned"],
            "Filtered":   s["total_filtered"],
            "Analyzed":   s["total_analyzed"],
        } for s in scans])
        st.dataframe(df2, use_container_width=True, hide_index=True)
    else:
        st.info("Chưa có lịch sử scan.")


# ════════════════════════════════════════════════════════════
#  BTC PAGE
# ════════════════════════════════════════════════════════════

elif page == "₿  BTC Analysis":
    st.title("₿ BTC Analysis")

    btc_hist = db.get_btc_history(days=30)
    latest   = db.get_latest_btc()

    if not latest:
        st.info("Chưa có BTC data. Chạy: `python main.py --btc-only`")
        st.stop()

    # ── Metrics row ───────────────────────────────────────────
    cols = st.columns(6)
    cols[0].metric("Giá",         fmt_price(latest["price"]))
    cols[1].metric("24H",         f"{latest['change_24h']:+.2f}%")
    cols[2].metric("7D",          f"{latest['change_7d']:+.2f}%")
    cols[3].metric("Dominance",   f"{latest['dominance']:.1f}%")
    cols[4].metric("Fear&Greed",  f"{latest['fear_greed']} ({latest['fear_greed_label']})")
    cols[5].metric("MA200W",      fmt_price(latest["ma200w"]))

    # ── Recommendation box ────────────────────────────────────
    rec = latest.get("recommendation", "WATCH")
    st.markdown(f"""
    <div style="background:#1e2130;border-radius:10px;padding:20px;margin:16px 0;border-left:5px solid {
        '#00e676' if 'BUY' in rec else '#ffd740' if rec == 'WATCH' else '#ff6e6e'
    }">
        <h2 style="margin:0">Recommendation: <span class="{rec_class(rec)}">{rec}</span></h2>
        <p style="color:#888;margin:4px 0">Cycle: {latest['cycle_phase']} | 
        MVRV proxy: {latest['mvrv_proxy_score']}/100 | 
        Trend: {latest['trend_structure']}</p>
    </div>
    """, unsafe_allow_html=True)

    if btc_hist:
        df = pd.DataFrame(btc_hist)
        df["created_at"] = pd.to_datetime(df["created_at"])

        tab1, tab2, tab3 = st.tabs(["Price & MA", "Scores Over Time", "Cycle & Macro"])

        with tab1:
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=df["created_at"], y=df["price"],
                name="BTC Price", line=dict(color="#f7931a", width=2)
            ))
            fig.add_trace(go.Scatter(
                x=df["created_at"], y=df["ma50w"],
                name="MA50W", line=dict(color="#4c9fff", dash="dash")
            ))
            fig.add_trace(go.Scatter(
                x=df["created_at"], y=df["ma200w"],
                name="MA200W", line=dict(color="#ff6e6e", dash="dot")
            ))
            fig.update_layout(
                title="BTC Price vs Moving Averages",
                paper_bgcolor="#0e1117", plot_bgcolor="#0e1117",
                font_color="#fafafa", height=400,
            )
            st.plotly_chart(fig, use_container_width=True)

        with tab2:
            fig2 = go.Figure()
            fig2.add_trace(go.Scatter(
                x=df["created_at"], y=df["overall_score"],
                name="Overall Score", line=dict(color="#a78bfa", width=2), fill="tozeroy",
                fillcolor="rgba(167,139,250,0.1)"
            ))
            fig2.add_trace(go.Scatter(
                x=df["created_at"], y=df["technical_score"],
                name="Technical", line=dict(color="#4c9fff", dash="dash")
            ))
            fig2.add_trace(go.Scatter(
                x=df["created_at"], y=df["cycle_score"],
                name="Cycle", line=dict(color="#ffd740", dash="dash")
            ))
            fig2.add_trace(go.Scatter(
                x=df["created_at"], y=df["macro_score"],
                name="Macro", line=dict(color="#69f0ae", dash="dash")
            ))
            fig2.add_hline(y=70, line_dash="dot", line_color="#00e676",
                           annotation_text="Strong Buy zone")
            fig2.add_hline(y=50, line_dash="dot", line_color="#ffd740",
                           annotation_text="Watch zone")
            fig2.update_layout(
                title="BTC Scores Over Time",
                yaxis=dict(range=[0, 100]),
                paper_bgcolor="#0e1117", plot_bgcolor="#0e1117",
                font_color="#fafafa", height=400,
            )
            st.plotly_chart(fig2, use_container_width=True)

        with tab3:
            col1, col2 = st.columns(2)
            with col1:
                fig3 = go.Figure(go.Scatter(
                    x=df["created_at"], y=df["fear_greed"],
                    mode="lines+markers", name="Fear & Greed",
                    line=dict(color="#ffd740"), marker=dict(size=4),
                ))
                fig3.add_hrect(y0=0,  y1=25, fillcolor="rgba(255,23,68,0.1)",   line_width=0, annotation_text="Extreme Fear")
                fig3.add_hrect(y0=75, y1=100, fillcolor="rgba(255,193,7,0.1)",  line_width=0, annotation_text="Extreme Greed")
                fig3.update_layout(
                    title="Fear & Greed Index", yaxis=dict(range=[0,100]),
                    paper_bgcolor="#0e1117", plot_bgcolor="#0e1117",
                    font_color="#fafafa", height=300,
                )
                st.plotly_chart(fig3, use_container_width=True)
            with col2:
                fig4 = go.Figure(go.Scatter(
                    x=df["created_at"], y=df["dominance"],
                    mode="lines", name="BTC Dominance",
                    line=dict(color="#f7931a"),
                ))
                fig4.update_layout(
                    title="BTC Dominance %",
                    paper_bgcolor="#0e1117", plot_bgcolor="#0e1117",
                    font_color="#fafafa", height=300,
                )
                st.plotly_chart(fig4, use_container_width=True)


# ════════════════════════════════════════════════════════════
#  ALT SCANNER PAGE
# ════════════════════════════════════════════════════════════

elif page == "🔍 Alt Scanner":
    st.title("🔍 Alt Scanner — Latest Results")

    alts = db.get_latest_alt_scan()
    if not alts:
        st.info("Chưa có Alt scan data. Chạy: `python main.py --alt-only`")
        st.stop()

    # ── Filter sidebar ────────────────────────────────────────
    with st.sidebar:
        st.markdown("### Filters")
        min_score = st.slider("Min Score", 0, 100, 60)
        actions   = st.multiselect(
            "Action", ["ACCUMULATE", "WATCH", "AVOID"],
            default=["ACCUMULATE", "WATCH"]
        )

    filtered = [a for a in alts
                if a["total_score"] >= min_score
                and a.get("action") in actions]

    st.caption(f"Hiển thị {len(filtered)}/{len(alts)} coin")

    # ── Score distribution chart ──────────────────────────────
    scores = [a["total_score"] for a in alts]
    fig = go.Figure(go.Histogram(
        x=scores, nbinsx=20,
        marker_color="#4c9fff", opacity=0.8,
    ))
    fig.add_vline(x=min_score, line_dash="dash", line_color="#ffd740",
                  annotation_text=f"Filter: {min_score}")
    fig.update_layout(
        title="Score Distribution (tất cả coin analyzed)",
        xaxis_title="Score", yaxis_title="Count",
        paper_bgcolor="#0e1117", plot_bgcolor="#0e1117",
        font_color="#fafafa", height=220, margin=dict(t=40,b=30),
    )
    st.plotly_chart(fig, use_container_width=True)

    # ── Coin cards ────────────────────────────────────────────
    for coin in filtered:
        action     = coin.get("action", "WATCH")
        ac         = action_color(action)
        disc_badge = "⚠️ " if coin.get("has_discrepancy") else ""

        with st.expander(
            f"{disc_badge}{coin['symbol']} — {coin['total_score']}/100 — "
            f"{action} — {coin.get('change_7d', 0):+.1f}% 7D",
            expanded=False
        ):
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Giá",         fmt_price(coin["price"]))
            c2.metric("Market Cap",  fmt_mc(coin["market_cap"]))
            c3.metric("7D",          f"{coin['change_7d']:+.2f}%")
            c4.metric("Vol Spike",   f"{coin['volume_spike']:.1f}x")

            # Score breakdown bar chart
            bd = {
                "Narrative":   coin["narrative_score"],
                "Momentum":    coin["momentum_score"],
                "Volume":      coin["volume_score"],
                "Tokenomics":  coin["tokenomics_score"],
                "Sentiment":   coin["sentiment_score"],
                "Bonus":       coin["bonus_score"],
            }
            max_vals = {"Narrative": 25, "Momentum": 20, "Volume": 20,
                        "Tokenomics": 15, "Sentiment": 10, "Bonus": 10}
            pct      = {k: v / max_vals[k] * 100 for k, v in bd.items()}

            fig2 = go.Figure(go.Bar(
                x=list(pct.values()), y=list(pct.keys()),
                orientation="h",
                marker_color=[
                    "#00e676" if v >= 70 else "#ffd740" if v >= 40 else "#ff6e6e"
                    for v in pct.values()
                ],
                text=[f"{bd[k]}/{max_vals[k]}" for k in bd],
                textposition="inside",
            ))
            fig2.update_layout(
                height=200, xaxis=dict(range=[0, 100], title="% of max"),
                paper_bgcolor="#0e1117", plot_bgcolor="#0e1117",
                font_color="#fafafa", margin=dict(l=0, r=0, t=10, b=0),
            )
            st.plotly_chart(fig2, use_container_width=True)

            # Thesis + catalysts + risks
            col_l, col_r = st.columns(2)
            with col_l:
                st.markdown(f"**🧠 Thesis**")
                st.write(coin.get("thesis", "N/A"))
                st.markdown(f"**⚡ Catalysts**")
                for cat in coin.get("catalysts", []):
                    st.write(f"• {cat}")
            with col_r:
                st.markdown(f"**⚠️ Risks**")
                for risk in coin.get("risks", []):
                    st.write(f"• {risk}")
                st.markdown(f"**❌ Invalidation**")
                st.write(coin.get("invalidation", "N/A"))

            st.markdown(f"**📌 DCA Note:** {coin.get('dca_note','N/A')}")

            if coin.get("has_discrepancy"):
                st.warning(f"⚠️ CMC Data lệch: " +
                           " | ".join(coin.get("discrepancy_notes", [])))


# ════════════════════════════════════════════════════════════
#  COIN HISTORY PAGE
# ════════════════════════════════════════════════════════════

elif page == "📈 Coin History":
    st.title("📈 Coin Score History")

    # Lấy danh sách symbol đã từng xuất hiện
    conn = db.get_conn()
    c    = conn.cursor()
    c.execute("SELECT DISTINCT symbol FROM coin_score_history ORDER BY symbol")
    symbols = [r["symbol"] for r in c.fetchall()]
    conn.close()

    if not symbols:
        st.info("Chưa có dữ liệu lịch sử. Cần chạy bot ít nhất 1 lần.")
        st.stop()

    col1, col2 = st.columns([2, 1])
    with col1:
        selected = st.selectbox("Chọn coin", symbols)
    with col2:
        days = st.selectbox("Khoảng thời gian", [7, 14, 30, 60], index=2)

    hist = db.get_coin_score_history(selected, days=days)

    if not hist:
        st.warning(f"Không có dữ liệu cho {selected} trong {days} ngày qua.")
        st.stop()

    df = pd.DataFrame(hist)
    df["created_at"] = pd.to_datetime(df["created_at"])

    # Score trend
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["created_at"], y=df["score"],
        mode="lines+markers", name="Score",
        line=dict(color="#a78bfa", width=2),
        marker=dict(
            color=[action_color(a) for a in df["action"]],
            size=8, symbol="circle",
        )
    ))
    fig.add_hline(y=70, line_dash="dot", line_color="#00e676", annotation_text="Buy zone")
    fig.add_hline(y=50, line_dash="dot", line_color="#ffd740", annotation_text="Watch zone")
    fig.update_layout(
        title=f"{selected} — Score History ({days}D)",
        yaxis=dict(range=[0, 100], title="Score"),
        paper_bgcolor="#0e1117", plot_bgcolor="#0e1117",
        font_color="#fafafa", height=350,
    )
    st.plotly_chart(fig, use_container_width=True)

    # Price trend
    fig2 = go.Figure(go.Scatter(
        x=df["created_at"], y=df["price"],
        mode="lines", name="Price",
        line=dict(color="#ffd740", width=2), fill="tozeroy",
        fillcolor="rgba(255,215,64,0.07)"
    ))
    fig2.update_layout(
        title=f"{selected} — Price History ({days}D)",
        paper_bgcolor="#0e1117", plot_bgcolor="#0e1117",
        font_color="#fafafa", height=280,
    )
    st.plotly_chart(fig2, use_container_width=True)

    # Raw data table
    with st.expander("Raw data"):
        st.dataframe(
            df[["created_at","price","score","action"]].sort_values("created_at", ascending=False),
            use_container_width=True, hide_index=True,
        )


# ════════════════════════════════════════════════════════════
#  TOP RECURRING PAGE
# ════════════════════════════════════════════════════════════

elif page == "⭐ Top Recurring":
    st.title("⭐ Top Recurring Coins")
    st.caption("Coin nào xuất hiện nhiều lần → tín hiệu bền hơn, ít nhiễu hơn 1 lần pump.")

    col1, col2 = st.columns(2)
    with col1:
        days = st.slider("Khoảng thời gian (ngày)", 7, 60, 30)
    with col2:
        min_app = st.slider("Xuất hiện tối thiểu", 2, 10, 2)

    recurring = db.get_top_recurring_coins(min_appearances=min_app, days=days)

    if not recurring:
        st.info(f"Chưa có coin nào xuất hiện ≥ {min_app} lần trong {days} ngày qua.")
        st.stop()

    # Bar chart
    df = pd.DataFrame(recurring)
    fig = go.Figure(go.Bar(
        x=df["symbol"], y=df["avg_score"],
        marker_color=[
            "#00e676" if s >= 70 else "#ffd740" if s >= 50 else "#ff6e6e"
            for s in df["avg_score"]
        ],
        text=df["appearances"].apply(lambda x: f"{x}x"),
        textposition="outside",
    ))
    fig.update_layout(
        title=f"Top Recurring Coins (avg score, {days}D)",
        yaxis=dict(range=[0, 100], title="Avg Score"),
        paper_bgcolor="#0e1117", plot_bgcolor="#0e1117",
        font_color="#fafafa", height=350,
    )
    st.plotly_chart(fig, use_container_width=True)

    # Table
    df_show = df.rename(columns={
        "symbol": "Symbol", "appearances": "Lần xuất hiện",
        "avg_score": "Avg Score", "max_score": "Max Score",
        "last_seen": "Last Seen", "last_action": "Last Action",
    })
    df_show["Avg Score"] = df_show["Avg Score"].round(1)
    st.dataframe(df_show, use_container_width=True, hide_index=True)

    st.info(
        "💡 **Insight:** Coin xuất hiện nhiều lần với avg score cao → "
        "bot liên tục nhận ra tín hiệu tốt, không phải pump 1 lần rồi tắt. "
        "Đây thường là coin đáng chú ý hơn."
    )
