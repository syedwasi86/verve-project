import os
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import requests

# -- Config -------------------------------------------------------------------
API_BASE = os.getenv("VERVE_API_URL", "http://localhost:8000")

# -- Session state ------------------------------------------------------------
if "last_session_id" not in st.session_state:
    st.session_state.last_session_id = None
if "last_api_result" not in st.session_state:
    st.session_state.last_api_result = None

# -- Page config --------------------------------------------------------------
st.set_page_config(
    page_title="Verve: Authenticity Dashboard",
    page_icon="🛡️",
    layout="wide",
)

# -- Enhanced High-Contrast Global CSS -----------------------------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Plus Jakarta Sans', sans-serif !important;
}

.stApp {
    background-color: #0B0F19 !important;
    color: #F3F4F6 !important;
}

/* Typography & Headings */
h1 {
    color: #FFFFFF !important;
    font-weight: 800 !important;
    letter-spacing: -0.02em !important;
    font-size: 2.2rem !important;
    margin-bottom: 0.2rem !important;
}

h2, h3, h4 {
    color: #F8FAFC !important;
    font-weight: 700 !important;
}

p, span, label, div {
    color: #E2E8F0 !important;
}

.stCaption {
    color: #94A3B8 !important;
    font-weight: 500 !important;
}

/* High Contrast Metric Cards */
[data-testid="stMetric"] {
    background: linear-gradient(135deg, rgba(30, 41, 59, 0.85), rgba(15, 23, 42, 0.95)) !important;
    border: 1px solid rgba(255, 255, 255, 0.16) !important;
    border-radius: 12px !important;
    padding: 14px 18px !important;
    box-shadow: 0 4px 18px rgba(0, 0, 0, 0.45) !important;
    transition: transform 0.2s ease, border-color 0.2s ease;
}

[data-testid="stMetric"]:hover {
    border-color: rgba(168, 85, 247, 0.6) !important;
    transform: translateY(-2px);
}

[data-testid="stMetricLabel"] {
    color: #CBD5E1 !important;
    font-size: 0.82rem !important;
    font-weight: 700 !important;
    letter-spacing: 0.08em !important;
    text-transform: uppercase !important;
}

[data-testid="stMetricValue"] {
    color: #FFFFFF !important;
    font-size: 1.8rem !important;
    font-weight: 800 !important;
}

[data-testid="stMetricDelta"] {
    font-weight: 700 !important;
    font-size: 0.82rem !important;
}

/* Section Header */
.section-header {
    font-size: 1.15rem;
    font-weight: 800;
    color: #F8FAFC;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    margin: 1.6rem 0 0.8rem 0;
    border-left: 4px solid #A855F7;
    padding-left: 0.75rem;
}

/* Verdict Banners */
.verdict-human {
    background: linear-gradient(135deg, rgba(6, 78, 59, 0.95), rgba(16, 185, 129, 0.35));
    border: 1.5px solid #10B981;
    border-radius: 14px;
    padding: 20px 24px;
    color: #ECFDF5;
    font-size: 1.1rem;
    font-weight: 600;
    box-shadow: 0 4px 20px rgba(16, 185, 129, 0.25);
}
.verdict-ai {
    background: linear-gradient(135deg, rgba(30, 58, 138, 0.95), rgba(59, 130, 246, 0.35));
    border: 1.5px solid #3B82F6;
    border-radius: 14px;
    padding: 20px 24px;
    color: #EFF6FF;
    font-size: 1.1rem;
    font-weight: 600;
    box-shadow: 0 4px 20px rgba(59, 130, 246, 0.25);
}
.verdict-paste {
    background: linear-gradient(135deg, rgba(120, 53, 15, 0.95), rgba(245, 158, 11, 0.35));
    border: 1.5px solid #F59E0B;
    border-radius: 14px;
    padding: 20px 24px;
    color: #FFFBEB;
    font-size: 1.1rem;
    font-weight: 600;
    box-shadow: 0 4px 20px rgba(245, 158, 11, 0.25);
}
.verdict-waiting {
    background: linear-gradient(135deg, rgba(30, 41, 59, 0.85), rgba(15, 23, 42, 0.95));
    border: 1.5px solid #64748B;
    border-radius: 14px;
    padding: 20px 24px;
    color: #F1F5F9;
    font-size: 1.05rem;
}

/* Ground Truth Chips */
.gt-chip {
    display: inline-block;
    padding: 4px 14px;
    border-radius: 999px;
    font-size: 0.82rem;
    font-weight: 700;
    margin: 4px 4px 0 4px;
}
.chip-human  { background: #065F46; color: #D1FAE5; border: 1px solid #10B981; }
.chip-paste  { background: #78350F; color: #FEF3C7; border: 1px solid #F59E0B; }
.chip-ai     { background: #1E3A8A; color: #DBEAFE; border: 1px solid #3B82F6; }

/* Sidebar Styling */
[data-testid="stSidebar"] {
    background-color: #0F172A !important;
    border-right: 1px solid rgba(255, 255, 255, 0.1) !important;
}

.sb-section-label {
    font-size: 0.72rem;
    font-weight: 800;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: #C084FC;
    margin: 1.4rem 0 0.5rem 0;
}

.sb-card {
    background: rgba(30, 41, 59, 0.85);
    border: 1px solid rgba(168, 85, 247, 0.35);
    border-radius: 12px;
    padding: 12px 16px;
    margin-bottom: 0.6rem;
}

.sb-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 0.88rem;
    margin: 0.35rem 0;
}

.sb-key { color: #94A3B8; font-weight: 500; }
.sb-val { color: #F8FAFC; font-weight: 700; font-family: monospace; }
</style>
""", unsafe_allow_html=True)

# -- Sidebar ------------------------------------------------------------------
try:
    st.sidebar.image("verve_logo.png", use_container_width=True)
except Exception:
    st.sidebar.markdown(
        "<div style='text-align:center;font-size:3rem;font-weight:900;"
        "color:#A855F7;letter-spacing:-.02em;padding:8px 0'>V</div>",
        unsafe_allow_html=True,
    )

st.sidebar.markdown("""
<style>
.sb-section-label {
    font-size: .72rem; font-weight: 800; letter-spacing: .12em;
    text-transform: uppercase; color: #C084FC;
    margin: 1.2rem 0 .4rem 0;
}
</style>
""", unsafe_allow_html=True)

api_url = API_BASE

# -- Header -------------------------------------------------------------------
st.title("Verve — Human Authenticity Portal")
st.markdown("<p style='color:#CBD5E1; font-size:1.05rem; margin-top:-0.4rem;'>Real-time behavioral biometrics dashboard. Tracks keystroke dynamics to distinguish Human, AI, and Paste authorship.</p>", unsafe_allow_html=True)
st.divider()

# -- Fetch latest result from API ---------------------------------------------
api_result = None
try:
    resp = requests.get(f"{api_url.rstrip('/')}/latest", timeout=5)
    resp.raise_for_status()
    api_response = resp.json()

    current_num_events = api_response.get("num_events", 0)
    if current_num_events > 0 and current_num_events != st.session_state.last_session_id:
        st.session_state.last_session_id = current_num_events
        st.session_state.last_api_result = api_response
        api_result = api_response
    else:
        api_result = st.session_state.last_api_result if st.session_state.last_api_result else api_response

except requests.exceptions.ConnectionError:
    api_result = st.session_state.last_api_result
    st.error("Cannot reach the API. Is the FastAPI backend running? Run: `uvicorn backend.main:app --reload` from the project root.")
except requests.exceptions.HTTPError as e:
    api_result = st.session_state.last_api_result
    st.error(f"API error: {e.response.status_code} - {e.response.text[:200]}")
except Exception as e:
    api_result = st.session_state.last_api_result
    st.error(f"Unexpected error: {e}")

has_session = bool(
    api_result
    and api_result.get("status") == "ok"
    and api_result.get("num_events", 0) > 0
)

# -- Populate sidebar with live session data ----------------------------------
with st.sidebar:
    st.markdown('<div class="sb-section-label">Session Metadata</div>', unsafe_allow_html=True)
    if has_session:
        meta        = api_result.get("session_meta", {})
        session_id  = meta.get("sessionId", "-")
        duration_s  = meta.get("duration_s", 0)
        num_events  = api_result.get("num_events", 0)
        sid_display = (session_id[:14] + "...") if len(session_id) > 14 else session_id
        st.markdown(
            f"""
            <div class="sb-card">
              <div class="sb-row">
                <span class="sb-key">ID</span>
                <span class="sb-val" title="{session_id}">{sid_display}</span>
              </div>
              <div class="sb-row">
                <span class="sb-key">Duration</span>
                <span class="sb-val">{duration_s:.1f} s</span>
              </div>
              <div class="sb-row">
                <span class="sb-key">Events</span>
                <span class="sb-val">{num_events} captured</span>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div class="sb-card"><span style="color:#94A3B8;font-size:.82rem">No active session</span></div>',
            unsafe_allow_html=True,
        )

    st.markdown('<div class="sb-section-label">System Specs</div>', unsafe_allow_html=True)
    if has_session:
        _sb_pred      = api_result.get("prediction", {})
        _sb_feats     = api_result.get("features", {})
        model_name    = _sb_pred.get("model", "-")
        num_feats     = sum(1 for v in _sb_feats.values() if v is not None and v != "-")
        st.markdown(
            f"""
            <div class="sb-card">
              <div class="sb-row">
                <span class="sb-key">Model</span>
                <span class="sb-val" title="{model_name}">{model_name}</span>
              </div>
              <div class="sb-row">
                <span class="sb-key">Features</span>
                <span class="sb-val">{num_feats} extracted</span>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div class="sb-card"><span style="color:#94A3B8;font-size:.82rem">Awaiting session</span></div>',
            unsafe_allow_html=True,
        )

    st.markdown("---")
    if st.button("Refresh Dashboard", use_container_width=True, key="sidebar_refresh"):
        try:
            resp = requests.get(f"{API_BASE.rstrip('/')}/latest", timeout=5)
            resp.raise_for_status()
            fresh = resp.json()
            st.session_state.last_api_result = fresh
        except Exception:
            pass
        st.rerun()
    st.caption("Polls `/latest` for new session data.")

# =============================================================================
# Helper constants & functions for the state-flow chart
# =============================================================================
_SRC_COLOR = {"Human": "#10B981", "AI": "#3B82F6", "Paste": "#F59E0B", "Unknown": "#6B7280"}
_SRC_LEVEL = {"Human": 1,         "AI": 2,          "Paste": 3,          "Unknown": 0}

def _hex_to_rgb(h):
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

def _build_stateflow(runs_list):
    """Return a Plotly figure for the stepped authorship state-flow."""
    fig = go.Figure()
    for run in runs_list:
        col  = _SRC_COLOR.get(run["source"], "#6B7280")
        span = run["x_end"] - run["x_start"]
        fig.add_vrect(x0=run["x_start"], x1=run["x_end"],
                      fillcolor=col, opacity=0.12, line_width=0)
        if span > max(runs_list[-1]["x_end"] * 0.04, 5):
            fig.add_annotation(
                x=(run["x_start"] + run["x_end"]) / 2,
                y=_SRC_LEVEL.get(run["source"], 0) + 0.38,
                text=run["source"], showarrow=False,
                font=dict(color=col, size=11, family="Plus Jakarta Sans"), opacity=0.9,
            )
    legend_seen = set()
    for run in runs_list:
        src = run["source"]
        col = _SRC_COLOR.get(src, "#6B7280")
        lev = _SRC_LEVEL.get(src, 0)
        r, g, b = _hex_to_rgb(col)
        show_leg = src not in legend_seen
        legend_seen.add(src)
        span = run["x_end"] - run["x_start"]
        fig.add_trace(go.Scatter(
            x=[run["x_start"], run["x_end"]], y=[lev, lev],
            mode="lines", name=src, showlegend=show_leg,
            line=dict(color=col, width=5),
            fill="tozeroy", fillcolor=f"rgba({r},{g},{b},0.15)",
            hovertemplate=(
                f"<b>{src}</b><br>"
                f"Chars {run['x_start']}-{run['x_end']}<br>"
                f"Span: {span} chars<extra></extra>"
            ),
        ))
    for i in range(len(runs_list) - 1):
        x_t    = runs_list[i]["x_end"]
        y_from = _SRC_LEVEL.get(runs_list[i]["source"], 0)
        y_to   = _SRC_LEVEL.get(runs_list[i + 1]["source"], 0)
        fig.add_shape(type="line", x0=x_t, y0=y_from, x1=x_t, y1=y_to,
                      line=dict(color="rgba(255,255,255,0.75)", width=2))
    return fig

# =============================================================================
# Pre-compute shared values
# =============================================================================
if has_session:
    pred       = api_result.get("prediction", {})
    feats      = api_result.get("features", {})
    gt         = api_result.get("ground_truth", {})
    dist       = api_result.get("class_distribution", {})
    per_window = api_result.get("per_window", [])

    label_name         = pred.get("label_name", "Unknown")
    confidence         = pred.get("confidence", 0.0)
    authenticity_score = pred.get("authenticity_score", 0.0)
    is_trustworthy     = float(authenticity_score) >= 50.0

    _categories = ["Human", "Paste", "AI"]
    accuracy_match = sum(
        min(gt.get(k, 0.0), dist.get(k, 0.0))
        for k in _categories
    )

    gt_html = (
        f'<span class="gt-chip chip-human">Human {gt.get("Human",0):.1f}%</span>'
        f'<span class="gt-chip chip-paste">Paste {gt.get("Paste",0):.1f}%</span>'
        f'<span class="gt-chip chip-ai">AI {gt.get("AI",0):.1f}%</span>'
    )

# =============================================================================
# BLOCK 1 - Verdict Banner (colour-coded by dominant label)
# =============================================================================
if has_session:
    if label_name == "Human":
        css_class = "verdict-human"
        icon = "🟢"
        summary = (
            f"<b>Verified Human Authorship</b> — Authenticity score: <b>{authenticity_score:.1f}%</b> "
            f"| Confidence: <b>{confidence:.2%}</b><br>"
            f"Behavioral traces match organic problem-solving patterns.<br>"
            f"Ground Truth: {gt_html}"
        )
    elif label_name == "AI":
        css_class = "verdict-ai"
        icon = "🔵"
        summary = (
            f"<b>AI-Assisted Pattern Detected</b> — Authenticity score: <b>{authenticity_score:.1f}%</b> "
            f"| Confidence: <b>{confidence:.2%}</b><br>"
            f"Behavioral traces suggest AI-generated or completed content.<br>"
            f"Ground Truth: {gt_html}"
        )
    else:
        css_class = "verdict-paste"
        icon = "🟠"
        summary = (
            f"<b>Paste / Mixed Input Detected</b> — Authenticity score: <b>{authenticity_score:.1f}%</b> "
            f"| Confidence: <b>{confidence:.2%}</b><br>"
            f"Large paste operations or mixed input detected.<br>"
            f"Ground Truth: {gt_html}"
        )
    st.markdown(f'<div class="{css_class}">{icon} {summary}</div>', unsafe_allow_html=True)
else:
    st.markdown(
        '<div class="verdict-waiting">Start a session in the VS Code sidebar, '
        "then click <b>Post to Backend</b> to run the ML model and see the verdict here.</div>",
        unsafe_allow_html=True,
    )

st.divider()

# =============================================================================
# BLOCK 2 - Top Metrics Row
# =============================================================================
if has_session:
    m1, m2, m3, m4, m5 = st.columns(5)
    with m1:
        st.metric("Authenticity Score", f"{float(authenticity_score):.1f}%",
                  delta="High Trust" if is_trustworthy else "Low Trust")
    with m2:
        st.metric("Validation Match", f"{accuracy_match:.1f}%",
                  delta="GT vs Prediction overlap")
    with m3:
        st.metric("Session Label", label_name,
                  delta=f"Confidence {confidence:.2%}")
    with m4:
        br = feats.get("burst_ratio", 0)
        st.metric("Burst Ratio", f"{br:.3f}",
                  delta="Low = Human" if br < 0.5 else "High = AI/Paste")
    with m5:
        st.metric("Avg Flight Time", f"{feats.get('mean_flight_time', 0):.0f} ms",
                  delta="Raw event mean")
else:
    m1, m2, m3, m4, m5 = st.columns(5)
    for col, lbl in zip([m1, m2, m3, m4, m5],
                        ["Authenticity Score", "Validation Match",
                         "Session Label", "Burst Ratio", "Avg Flight Time"]):
        col.metric(lbl, "-", delta="Awaiting session")

st.divider()

# =============================================================================
# BLOCK 3 - Authorship Transition Timeline (primary visualization)
# =============================================================================
st.markdown('<div class="section-header">Authorship Transition Timeline</div>',
            unsafe_allow_html=True)

rhythm_raw = api_result.get("rhythm_data", []) if has_session else []

if rhythm_raw:
    rhythm_df = pd.DataFrame(rhythm_raw)
    rhythm_df.columns = ["cumchars", "Source", "chars"]

    runs = []
    prev_src, span_start = None, 0
    for _, row in rhythm_df.iterrows():
        src = row["Source"]
        if src != prev_src:
            if prev_src is not None:
                runs.append({"source": prev_src,
                             "x_start": span_start,
                             "x_end": int(row["cumchars"])})
            span_start = int(row["cumchars"])
            prev_src   = src
    if prev_src is not None:
        runs.append({"source": prev_src,
                     "x_start": span_start,
                     "x_end": int(rhythm_df["cumchars"].iloc[-1])})

    fig_sf = _build_stateflow(runs)
    total_chars = int(rhythm_df["cumchars"].iloc[-1])
    fig_sf.update_layout(
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#F8FAFC", family="Plus Jakarta Sans"),
        height=320,
        xaxis=dict(
            title=dict(text="Cumulative Characters Written", font=dict(color="#F1F5F9", size=13)),
            showgrid=True, gridcolor="rgba(255,255,255,0.12)",
            tickfont=dict(color="#E2E8F0", size=12),
            range=[0, total_chars * 1.02],
        ),
        yaxis=dict(
            tickvals=[1, 2, 3],
            ticktext=["Human", "AI", "Paste"],
            tickfont=dict(color="#F8FAFC", size=13, weight="bold"), range=[0.3, 3.7],
            showgrid=True, gridcolor="rgba(255,255,255,0.12)", zeroline=False,
        ),
        legend=dict(orientation="h", yanchor="bottom", y=1.05,
                    xanchor="right", x=1, font=dict(color="#F8FAFC", size=12)),
        margin=dict(t=45, b=45, l=110, r=20),
    )
    st.plotly_chart(fig_sf, use_container_width=True)

    n_h = sum(1 for r in runs if r["source"] == "Human")
    n_a = sum(1 for r in runs if r["source"] == "AI")
    n_p = sum(1 for r in runs if r["source"] == "Paste")
    st.caption(
        f"Human: {n_h} stretch{'es' if n_h != 1 else ''}  |  "
        f"AI: {n_a} block{'s' if n_a != 1 else ''}  |  "
        f"Paste: {n_p} event{'s' if n_p != 1 else ''}  |  "
        f"{total_chars:,} content characters total"
    )
else:
    demo_runs = [
        {"source": "Human", "x_start": 0,   "x_end": 42},
        {"source": "AI",    "x_start": 42,  "x_end": 342},
        {"source": "Human", "x_start": 342, "x_end": 390},
        {"source": "Paste", "x_start": 390, "x_end": 520},
        {"source": "Human", "x_start": 520, "x_end": 570},
    ]
    fig_ph = _build_stateflow(demo_runs)
    fig_ph.update_layout(
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#F8FAFC", family="Plus Jakarta Sans"),
        height=300,
        xaxis=dict(title=dict(text="Cumulative Characters (demo)", font=dict(color="#F1F5F9", size=13)),
                   showgrid=True, gridcolor="rgba(255,255,255,0.12)",
                   tickfont=dict(color="#E2E8F0", size=12)),
        yaxis=dict(
            tickvals=[1, 2, 3],
            ticktext=["Human", "AI", "Paste"],
            tickfont=dict(color="#F8FAFC", size=13, weight="bold"), range=[0.3, 3.7],
            showgrid=True, gridcolor="rgba(255,255,255,0.12)", zeroline=False,
        ),
        legend=dict(orientation="h", yanchor="bottom", y=1.05,
                    xanchor="right", x=1, font=dict(color="#F8FAFC", size=12)),
        margin=dict(t=45, b=45, l=110, r=20),
    )
    for trace in fig_ph.data:
        trace.update(opacity=0.6)
    st.plotly_chart(fig_ph, use_container_width=True)
    st.caption(
        "(Demo — submit a session from VS Code extension to see live real-time metrics)."
    )

st.divider()

# =============================================================================
# BLOCK 4 - Comparison: ML Prediction Donut | Ground Truth Bar
# =============================================================================
st.markdown('<div class="section-header">Authorship Distribution Comparison</div>',
            unsafe_allow_html=True)

pred_col, gt_col = st.columns([3, 2])

with pred_col:
    st.subheader("ML Prediction")
    if has_session and dist:
        dist_df = pd.DataFrame(
            [{"Authorship": k, "Percentage (%)": float(v)} for k, v in dist.items()]
        )
        fig_pie = px.pie(
            dist_df, names="Authorship", values="Percentage (%)",
            color="Authorship",
            color_discrete_map={"Human": "#10B981", "Paste": "#F59E0B", "AI": "#3B82F6"},
            hole=0.48,
        )
        fig_pie.update_layout(
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#F8FAFC", family="Plus Jakarta Sans"),
            height=350,
            legend=dict(orientation="h", yanchor="top", y=-0.05, font=dict(color="#F8FAFC", size=12)),
            margin=dict(t=20, b=20, l=20, r=20),
        )
        fig_pie.update_traces(textinfo="percent+label", textfont=dict(size=14, color="#FFFFFF"))
        st.plotly_chart(fig_pie, use_container_width=True)
        st.caption("Character-weighted distribution of classifier predictions.")
    else:
        st.info("No prediction data available yet.")

with gt_col:
    st.subheader("Validation Reference")
    if has_session:
        gt_df = pd.DataFrame(
            [{"Authorship": k, "Percentage (%)": v} for k, v in gt.items()]
        )
        color_map = {"Human": "#10B981", "Paste": "#F59E0B", "AI": "#3B82F6"}
        fig_gt = px.bar(
            gt_df, x="Authorship", y="Percentage (%)",
            color="Authorship", color_discrete_map=color_map,
            text_auto=".1f",
        )
        fig_gt.update_layout(
            showlegend=False,
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#F8FAFC", family="Plus Jakarta Sans"),
            yaxis=dict(range=[0, 100], tickfont=dict(color="#E2E8F0"), gridcolor="rgba(255,255,255,0.12)"),
            xaxis=dict(tickfont=dict(color="#F8FAFC", size=13, weight="bold")),
            height=350,
            margin=dict(t=20, b=20, l=20, r=20),
        )
        fig_gt.update_traces(textposition="outside", textfont=dict(size=13, color="#FFFFFF"))
        st.plotly_chart(fig_gt, use_container_width=True)
        st.caption(
            f"Ground Truth tags — "
            f"Human: {gt.get('Human', 0):.1f}% | "
            f"Paste: {gt.get('Paste', 0):.1f}% | "
            f"AI: {gt.get('AI', 0):.1f}%"
        )
    else:
        st.info("No session ground truth data yet.")

st.divider()

# =============================================================================
# BLOCK 5 - Technical Biometric Data (collapsible deep-dive)
# =============================================================================
with st.expander("Technical Biometric Data & Feature Breakdown", expanded=False):

    # 5a. Extracted Features Table
    st.markdown('<div class="section-header">Extracted Features (ML Input)</div>',
                unsafe_allow_html=True)
    if has_session and feats:
        feats_display = {
            "Mean Dwell Time (ms)"   : feats.get("mean_dwell_time", "-"),
            "Flight Time Jitter (ms)": feats.get("flight_time_jitter", "-"),
            "Mean Flight Time (ms)"  : feats.get("mean_flight_time", "-"),
            "Std Flight Time (ms)"   : feats.get("std_flight_time", "-"),
            "Typing Velocity (CPS)"  : feats.get("typing_velocity", "-"),
            "Correction Rate"        : feats.get("correction_rate", "-"),
            "Burst Ratio"            : feats.get("burst_ratio", "-"),
            "Max Burst Length"       : feats.get("max_burst_length", "-"),
            "Bulk Event Ratio"       : feats.get("bulk_event_ratio", "-"),
            "Mean Cursor Jump"       : feats.get("mean_cursor_jump", "-"),
            "Event Entropy"          : feats.get("event_entropy", "-"),
            "Windows Analysed"       : feats.get("num_windows", "-"),
        }
        feats_df = pd.DataFrame(
            [{"Feature": k, "Value": (f"{v:.4f}" if isinstance(v, float) else v)}
             for k, v in feats_display.items()]
        )
        st.dataframe(feats_df, use_container_width=True, hide_index=True)
    else:
        st.info("Feature values will appear here once a session is processed.")

    st.divider()

    # 5b. Per-Window Breakdown
    st.markdown('<div class="section-header">Per-Window Breakdown</div>',
                unsafe_allow_html=True)
    if has_session and per_window:
        pw_df = pd.DataFrame(per_window)
        pw_df.columns = ["Window #", "Chars in Window", "Ground Truth", "Prediction"]

        def highlight_match(row):
            if row["Ground Truth"] == row["Prediction"]:
                return ["background-color: rgba(16,185,129,0.2)"] * 4
            return ["background-color: rgba(239,68,68,0.2)"] * 4

        st.dataframe(
            pw_df.style.apply(highlight_match, axis=1),
            use_container_width=True, hide_index=True,
        )

        correct = sum(1 for r in per_window if r["ground_truth"] == r["prediction"])
        total   = len(per_window)
        acc     = correct / total * 100 if total else 0
        st.metric("Window-level Accuracy", f"{acc:.1f}%",
                  delta=f"{correct} / {total} windows correct")

        if len(per_window) <= 60:
            label_to_int = {"Human": 0, "AI": 1, "Paste": 2, "Unknown": -1}
            windows_nums = [r["window"]       for r in per_window]
            gt_series    = [label_to_int.get(r["ground_truth"], -1) for r in per_window]
            pd_series    = [label_to_int.get(r["prediction"],   -1) for r in per_window]

            fig_cmp = go.Figure()
            fig_cmp.add_trace(go.Scatter(
                x=windows_nums, y=gt_series,
                mode="lines+markers", name="Ground Truth",
                line=dict(color="#10B981", width=3), marker=dict(size=7),
            ))
            fig_cmp.add_trace(go.Scatter(
                x=windows_nums, y=pd_series,
                mode="lines+markers", name="ML Prediction",
                line=dict(color="#C084FC", width=3, dash="dot"), marker=dict(size=7),
            ))
            fig_cmp.update_layout(
                yaxis=dict(tickvals=[0, 1, 2], ticktext=["Human", "AI", "Paste"],
                           title=dict(text="Label", font=dict(color="#F8FAFC")),
                           tickfont=dict(color="#F8FAFC", size=13, weight="bold"),
                           gridcolor="rgba(255,255,255,0.12)"),
                xaxis=dict(title=dict(text="Window #", font=dict(color="#F1F5F9")),
                           tickfont=dict(color="#E2E8F0"),
                           gridcolor="rgba(255,255,255,0.12)"),
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#F8FAFC", family="Plus Jakarta Sans"), height=300,
                legend=dict(orientation="h", yanchor="bottom", y=1.02, font=dict(color="#F8FAFC")),
            )
            st.plotly_chart(fig_cmp, use_container_width=True)
    else:
        st.info("Per-window breakdown will appear here once a session is processed.")

# -- Footer -------------------------------------------------------------------
st.divider()
st.caption("Verve — Behavioral Biometric Authentication System")
