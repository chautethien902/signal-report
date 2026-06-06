"""
dashboard.py — Crypto Bot Signal Dashboard
Streamlit Cloud + Supabase PostgreSQL
"""

import json
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))
import database as db

st.set_page_config(
    page_title="Crypto Signal Report",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
  [data-testid="stAppViewContainer"] { background: #0d1117; }
  .signal-card {
    background: #161b22;
    border-radius: 12px;
    padding: 20px 24px;
    margin-bottom: 16px;
    border-left: 4px solid #30363d;
  }
  .signal-card.accumulate { border-left-color: #3fb950; }
  .signal-card.watch      { border-left-color: #d29922; }
  .signal-card.wait       { border-left-color: #8b949e; }
  .tag {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 12px;
    font-size: 12px;
    font-weight: 600;
    margin-right: 6px;
  }
  .tag-acc   { background:#1a4226; color:#3fb950; }
  .tag-watch { background:#3d2e00; color:#d29922; }
  .tag-wait  { background:#21262d; color:#8b949e; }
  .tag-neg   { background:#3d1a1a; color:#f85149; }
  .price-big { font-size: 28px; font-weight: 700; color: #e6edf3; }
  .label     { font-size: 11px; color: #8b949e; margin-bottom: 2px; text-transform: uppercase; letter-spacing: 0.05em; }
  .value     { font-size: 15px; font-weight: 600; color: #e6edf3; }
  .green     { color: #3fb950; }
  .red       { color: #f85149; }
  .yellow    { color: #d29922; }
  .gray      { color: #8b949e; }
  hr.divider { border: none; border-top: 1px solid #21262d; margin: 12px 0; }
  .scenario-box {
    background: #0d1117;
    border-radius: 8px;
    padding: 12px 16px;
    margin-top: 8px;
    font-size: 13px;
    color: #c9d1d9;
    line-height: 1.6;
  }
  .entry-box {
    background: #1c2128;
    border: 1px solid #d29922;
    border-radius: 8px;
    padding: 12px 16px;
    margin-top: 8px;
    font-size: 13px;
  }
</style>
""", unsafe_allow_html=True)

db.init_db()


# ── Helpers ──────────────────────────────────────────────────

def fmt_price(n):
    if n is None: return "N/A"
    if n >= 1:    return f"${n:,.3f}"
    if n >= 0.01: return f"${n:,.4f}"
    return f"${n:,.6f}"

def fmt_mc(n):
    if n is None: return "N/A"
    if n >= 1e9:  return f"${n/1e9:.2f}B"
    return f"${n/1e6:.0f}M"

def pct_color(n):
    if n is None: return "N/A"
    cls = "green" if n >= 0 else "red"
    arrow = "▲" if n >= 0 else "▼"
    return f'<span class="{cls}">{arrow} {abs(n):.2f}%</span>'

def action_tag(action):
    if action == "ACCUMULATE":
        return '<span class="tag tag-acc">ACCUMULATE</span>'
    elif action == "WATCH":
        return '<span class="tag tag-watch">WATCH</span>'
    elif action == "WAIT_FOR_LEVEL":
        return '<span class="tag tag-wait">⏳ WAIT</span>'
    else:
        return f'<span class="tag tag-neg">{action}</span>'


# ── Sidebar ───────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📊 Crypto Bot")
    st.markdown("---")
    page = st.radio("", ["🏠 Overview", "📈 BTC Analysis", "🔍 Alt Signals"])
    st.markdown("---")
    if st.button("🔄 Refresh"):
        st.cache_data.clear()
        st.rerun()
    st.caption(f"Updated: {datetime.now().strftime('%H:%M:%S')}")


# ════════════════════════════════════════════════════════════
#  OVERVIEW
# ════════════════════════════════════════════════════════════

if page == "🏠 Overview":
    st.title("📊 Overview")

    btc  = db.get_latest_btc()
    alts = db.get_latest_alt_scan()

    # BTC bar
    if btc:
        c1,c2,c3,c4,c5 = st.columns(5)
        c1.metric("BTC Price",  f"${btc['price']:,.0f}")
        c2.metric("24H",        f"{btc['change_24h']:+.2f}%")
        c3.metric("Score",      f"{btc['overall_score']}/100")
        c4.metric("Cycle",      btc['cycle_phase'])
        c5.metric("Signal",     btc['recommendation'])

    st.markdown("---")

    # Alt summary
    if alts:
        acc   = [a for a in alts if a['action'] == 'ACCUMULATE']
        watch = [a for a in alts if a['action'] == 'WATCH']
        wait  = [a for a in alts if a['action'] == 'WAIT_FOR_LEVEL']

        st.subheader("🔍 Alt Scan Summary")
        c1,c2,c3,c4 = st.columns(4)
        c1.metric("Total analyzed", len(alts))
        c2.metric("🟢 ACCUMULATE",  len(acc))
        c3.metric("🟡 WATCH",       len(watch))
        c4.metric("⏳ WAIT",        len(wait))


# ════════════════════════════════════════════════════════════
#  BTC ANALYSIS
# ════════════════════════════════════════════════════════════

elif page == "📈 BTC Analysis":
    st.title("₿ BTC Analysis")

    btc = db.get_latest_btc()
    if not btc:
        st.info("Chưa có data. Chạy: `python main.py --btc-only`")
        st.stop()

    c1,c2,c3,c4,c5,c6 = st.columns(6)
    c1.metric("Price",       f"${btc['price']:,.0f}")
    c2.metric("24H",         f"{btc['change_24h']:+.2f}%")
    c3.metric("7D",          f"{btc['change_7d']:+.2f}%")
    c4.metric("Dominance",   f"{btc['dominance']:.1f}%")
    c5.metric("Fear&Greed",  f"{btc['fear_greed']} ({btc['fear_greed_label']})")
    c6.metric("MA200W",      f"${btc['ma200w']:,.0f}" if btc['ma200w'] else "N/A")

    rec = btc['recommendation']
    color = "#3fb950" if "BUY" in str(rec) else "#d29922" if rec == "WATCH" else "#f85149"
    st.markdown(f"""
    <div style="background:#161b22;border-radius:10px;padding:18px;
                margin:12px 0;border-left:5px solid {color}">
        <div style="font-size:20px;font-weight:700;color:#e6edf3">
            Signal: <span style="color:{color}">{rec}</span>
        </div>
        <div style="color:#8b949e;margin-top:4px">
            Cycle: {btc['cycle_phase']} &nbsp;|&nbsp;
            Trend: {btc['trend_structure']} &nbsp;|&nbsp;
            MVRV proxy: {btc['mvrv_proxy_score']}/100
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Chart lịch sử
    hist = db.get_btc_history(days=30)
    if len(hist) > 1:
        df = pd.DataFrame(hist)
        df["created_at"] = pd.to_datetime(df["created_at"])
        tab1, tab2 = st.tabs(["Price", "Score"])
        with tab1:
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=df["created_at"], y=df["price"],
                line=dict(color="#f7931a", width=2), name="BTC"))
            if "ma50w" in df:
                fig.add_trace(go.Scatter(x=df["created_at"], y=df["ma50w"],
                    line=dict(color="#4c9fff", dash="dash"), name="MA50W"))
            if "ma200w" in df:
                fig.add_trace(go.Scatter(x=df["created_at"], y=df["ma200w"],
                    line=dict(color="#f85149", dash="dot"), name="MA200W"))
            fig.update_layout(height=320, paper_bgcolor="#0d1117",
                plot_bgcolor="#0d1117", font_color="#e6edf3",
                margin=dict(t=20,b=20))
            st.plotly_chart(fig, use_container_width=True)
        with tab2:
            fig2 = go.Figure()
            fig2.add_trace(go.Scatter(x=df["created_at"], y=df["overall_score"],
                fill="tozeroy", line=dict(color="#a78bfa",width=2), name="Score",
                fillcolor="rgba(167,139,250,0.1)"))
            fig2.add_hline(y=70, line_dash="dot", line_color="#3fb950")
            fig2.add_hline(y=50, line_dash="dot", line_color="#d29922")
            fig2.update_layout(height=280, yaxis=dict(range=[0,100]),
                paper_bgcolor="#0d1117", plot_bgcolor="#0d1117",
                font_color="#e6edf3", margin=dict(t=20,b=20))
            st.plotly_chart(fig2, use_container_width=True)


# ════════════════════════════════════════════════════════════
#  ALT SIGNALS — chỉ show ACCUMULATE + WATCH, format như hình 4
# ════════════════════════════════════════════════════════════

elif page == "🔍 Alt Signals":
    st.title("🔍 Alt Signals")

    alts = db.get_latest_alt_scan()
    if not alts:
        st.info("Chưa có data alt scan.")
        st.stop()

    # Chỉ lấy ACCUMULATE và WATCH (bỏ AVOID)
    signals = [a for a in alts
               if a.get("action") in ("ACCUMULATE", "WATCH", "WAIT_FOR_LEVEL")]

    if not signals:
        st.info("Không có coin nào có signal ACCUMULATE/WATCH lúc này.")
        st.stop()

    st.caption(f"**{len(signals)} coin** có signal đáng chú ý — cập nhật lúc "
               f"{signals[0].get('timestamp','')}")

    for coin in signals:
        action   = coin.get("action", "WATCH")
        card_cls = ("accumulate" if action == "ACCUMULATE"
                    else "watch" if action == "WATCH"
                    else "wait")

        # Parse JSON fields
        catalysts = coin.get("catalysts") or []
        risks     = coin.get("risks") or []
        if isinstance(catalysts, str):
            try: catalysts = json.loads(catalysts)
            except: catalysts = []
        if isinstance(risks, str):
            try: risks = json.loads(risks)
            except: risks = []

        # Core fields
        dca_note     = coin.get("dca_note") or ""
        upside_cons  = coin.get("upside_conservative") or ""
        upside_bull  = coin.get("upside_bull") or ""
        invalidation = coin.get("invalidation") or ""

        # Scenario bullish — ưu tiên DB column mới, fallback về upside_bull
        scenario_bull_text = (
            coin.get("scenario_bullish") or
            upside_cons or
            (f"Target: {upside_cons}" if upside_cons else None) or
            "—"
        )

        # Entry condition — ưu tiên DB column mới, fallback về dca_note
        entry_text = (
            coin.get("entry_condition") or
            dca_note or
            "—"
        )

        # Risk text
        risk_text = "<br>".join(f"• {r}" for r in risks[:3]) if risks else "—"

        # Thesis
        thesis_text = coin.get("thesis") or "—"

        # Target line
        target_line = (
            f'<div style="margin-top:6px;font-size:12px;color:#8b949e">'
            f'🎯 Target: <b style="color:#3fb950">{upside_cons}</b>'
            + (f' → bull case <b style="color:#3fb950">{upside_bull}</b>' if upside_bull else "")
            + "</div>"
        ) if upside_cons else ""

        # % change color
        c7d  = coin.get("change_7d",  0) or 0
        c24h = coin.get("change_24h", 0) or 0
        mc   = coin.get("market_cap", 0) or 0

        st.markdown(f"""
        <div class="signal-card {card_cls}">

          <!-- Header -->
          <div style="display:flex;align-items:center;gap:10px;margin-bottom:12px">
            <span style="font-size:20px;font-weight:700;color:#e6edf3">
              {coin.get("symbol","")}
            </span>
            <span style="color:#8b949e;font-size:14px">{coin.get("name","")}</span>
            {action_tag(action)}
            <span style="margin-left:auto;font-size:13px;color:#8b949e">
              Score: <b style="color:#e6edf3">{coin.get("total_score",0)}/100</b>
            </span>
          </div>

          <!-- Price row -->
          <div style="display:flex;gap:32px;margin-bottom:12px;flex-wrap:wrap">
            <div>
              <div class="label">Giá</div>
              <div class="price-big">{fmt_price(coin.get("price"))}</div>
            </div>
            <div>
              <div class="label">Market Cap</div>
              <div class="value">{fmt_mc(mc)}</div>
            </div>
            <div>
              <div class="label">7D</div>
              <div class="value">{pct_color(c7d)}</div>
            </div>
            <div>
              <div class="label">24H</div>
              <div class="value">{pct_color(c24h)}</div>
            </div>
            <div>
              <div class="label">Vol Spike</div>
              <div class="value">{coin.get("volume_spike",0):.1f}x</div>
            </div>
            <div>
              <div class="label">Narrative</div>
              <div class="value" style="color:#a78bfa">{coin.get("narrative","")}</div>
            </div>
          </div>

          <hr class="divider">

          <!-- Hai kịch bản -->
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px">
            <div class="scenario-box">
              <div style="color:#3fb950;font-weight:600;margin-bottom:6px">
                🟢 Kịch bản tăng
              </div>
              {scenario_bull_text}
            </div>
            <div class="scenario-box">
              <div style="color:#f85149;font-weight:600;margin-bottom:6px">
                🔴 Kịch bản giảm / Rủi ro
              </div>
              {risk_text}
            </div>
          </div>

          <!-- Góc nhìn ngắn hạn (thesis) -->
          <div style="font-size:13px;color:#c9d1d9;margin-bottom:10px">
            <span style="color:#8b949e">⚡ Góc nhìn: </span>
            {thesis_text}
          </div>

          <!-- Invalidation -->
          <div style="font-size:12px;color:#8b949e;margin-bottom:10px">
            ❌ <b>Invalidation:</b> {invalidation or "—"}
          </div>

          <!-- Entry box -->
          <div class="entry-box">
            <div style="font-weight:600;color:#d29922;margin-bottom:6px">
              📍 Entry / DCA
            </div>
            <div style="font-size:13px;color:#c9d1d9">
              {entry_text}
            </div>
            {target_line}
          </div>

        </div>
        """, unsafe_allow_html=True)
