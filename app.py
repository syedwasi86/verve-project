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
    page_icon="shield",
    layout="wide",
)

# -- Global CSS ---------------------------------------------------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

.main { background-color: #0e1117; }

[data-testid="stMetricLabel"]  { color: #a0aec0 !important; font-size: 0.78rem; font-weight: 600; letter-spacing: .08em; text-transform: uppercase; }
[data-testid="stMetricValue"]  { color: #f0f4f8 !important; font-size: 1.55rem; font-weight: 700; }
[data-testid="stMetricDelta"]  { font-size: 0.78rem; }

.section-header {
    font-size: 1.05rem; font-weight: 700; color: #a0aec0;
    letter-spacing: .1em; text-transform: uppercase;
    margin: 1.4rem 0 .6rem 0;
    border-left: 3px solid #7c3aed; padding-left: .6rem;
}

.verdict-human {
    background: linear-gradient(135deg,#064e3b,#065f46);
    border: 1px solid #10b981; border-radius: 12px; padding: 18px 24px;
    color: #d1fae5; font-size: 1.05rem; font-weight: 600;
}
.verdict-ai {
    background: linear-gradient(135deg,#1e3a5f,#1e40af);
    border: 1px solid #3b82f6; border-radius: 12px; padding: 18px 24px;
    color: #dbeafe; font-size: 1.05rem; font-weight: 600;
}
.verdict-paste {
    background: linear-gradient(135deg,#451a03,#78350f);
    border: 1px solid #f59e0b; border-radius: 12px; padding: 18px 24px;
    color: #fef3c7; font-size: 1.05rem; font-weight: 600;
}
.verdict-waiting {
    background: linear-gradient(135deg,#1a1a2e,#16213e);
    border: 1px solid #4b5563; border-radius: 12px; padding: 18px 24px;
    color: #9ca3af; font-size: 1.05rem;
}

.gt-chip {
    display:inline-block; padding:3px 12px; border-radius:999px;
    font-size:.78rem; font-weight:700; margin:0 4px;
}
.chip-human  { background:#065f46; color:#d1fae5; }
.chip-paste  { background:#78350f; color:#fef3c7; }
.chip-ai     { background:#1e3a8a; color:#dbeafe; }
</style>
""", unsafe_allow_html=True)

# -- Sidebar ------------------------------------------------------------------
try:
    st.sidebar.image("verve_logo.png", use_container_width=True)
except Exception:
    st.sidebar.markdown(
        "<div style='text-align:center;font-size:3rem;font-weight:900;"
        "color:#7c3aed;letter-spacing:-.02em;padding:8px 0'>V</div>",
        unsafe_allow_html=True,
    )

st.sidebar.markdown("""
<style>
[data-testid="stSidebar"] { background: #0d0f1a !important; }
.sb-section-label {
    font-size: .65rem; font-weight: 700; letter-spacing: .12em;
    text-transform: uppercase; color: #7c3aed;
    margin: 1.2rem 0 .35rem 0;
}
.sb-card {
    background: rgba(124,58,237,.08);
    border: 1px solid rgba(124,58,237,.25);
    border-radius: 10px;
    padding: 10px 14px;
    margin-bottom: .5rem;
}
.sb-row { display:flex; justify-content:space-between; align-items:center;
           font-size:.82rem; margin:.25rem 0; }
.sb-key  { color:#8892a4; }
.sb-val  { color:#e2e8f0; font-weight:600; font-family:monospace;
           max-width:120px; overflow:hidden; text-overflow:ellipsis;
           white-space:nowrap; }
</style>
""", unsafe_allow_html=True)

api_url = API_BASE

# -- Header -------------------------------------------------------------------
st.title("Verve - Human Authenticity Portal")
st.markdown("*Real-time behavioral biometrics dashboard. Tracks keystroke dynamics to distinguish Human, AI, and Paste authorship.*")
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
            '<div class="sb-card"><span style="color:#6b7280;font-size:.82rem">No active session</span></div>',
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
            '<div class="sb-card"><span style="color:#6b7280;font-size:.82rem">Awaiting session</span></div>',
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
_SRC_COLOR = {"Human": "#10b981", "AI": "#3b82f6", "Paste": "#f59e0b", "Unknown": "#6b7280"}
_SRC_LEVEL = {"Human": 1,         "AI": 2,          "Paste": 3,          "Unknown": 0}

def _hex_to_rgb(h):
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

def _build_stateflow(runs_list):
    """Return a Plotly figure for the stepped authorship state-flow."""
    fig = go.Figure()
    for run in runs_list:
        col  = _SRC_COLOR.get(run["source"], "#6b7280")
        span = run["x_end"] - run["x_start"]
        fig.add_vrect(x0=run["x_start"], x1=run["x_end"],
                      fillcolor=col, opacity=0.07, line_width=0)
        if span > max(runs_list[-1]["x_end"] * 0.04, 5):
            fig.add_annotation(
                x=(run["x_start"] + run["x_end"]) / 2,
                y=_SRC_LEVEL.get(run["source"], 0) + 0.38,
                text=run["source"], showarrow=False,
                font=dict(color=col, size=9), opacity=0.75,
            )
    legend_seen = set()
    for run in runs_list:
        src = run["source"]
        col = _SRC_COLOR.get(src, "#6b7280")
        lev = _SRC_LEVEL.get(src, 0)
        r, g, b = _hex_to_rgb(col)
        show_leg = src not in legend_seen
        legend_seen.add(src)
        span = run["x_end"] - run["x_start"]
        fig.add_trace(go.Scatter(
            x=[run["x_start"], run["x_end"]], y=[lev, lev],
            mode="lines", name=src, showlegend=show_leg,
            line=dict(color=col, width=4.5),
            fill="tozeroy", fillcolor=f"rgba({r},{g},{b},0.09)",
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
                      line=dict(color="rgba(255,255,255,0.55)", width=2))
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

    # accuracy_match: percentage overlap between GT and ML prediction
    # = sum of min(gt_k%, pred_k%) across {Human, Paste, AI}
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
        icon = "[Human]"
        summary = (
            f"<b>Verified Human Authorship</b> - Authenticity score: <b>{authenticity_score:.1f}%</b> "
            f"| Confidence: <b>{confidence:.2%}</b><br>"
            f"Behavioral traces match organic problem-solving patterns.<br>"
            f"Ground Truth: {gt_html}"
        )
    elif label_name == "AI":
        css_class = "verdict-ai"
        icon = "[AI]"
        summary = (
            f"<b>AI-Assisted Pattern Detected</b> - Authenticity score: <b>{authenticity_score:.1f}%</b> "
            f"| Confidence: <b>{confidence:.2%}</b><br>"
            f"Behavioral traces suggest AI-generated or completed content.<br>"
            f"Ground Truth: {gt_html}"
        )
    else:
        css_class = "verdict-paste"
        icon = "[Paste]"
        summary = (
            f"<b>Paste / Mixed Input Detected</b> - Authenticity score: <b>{authenticity_score:.1f}%</b> "
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
        st.metric("System Validation Match", f"{accuracy_match:.1f}%",
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
                        ["Authenticity Score", "System Validation Match",
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
        font_color="#e2e8f0", height=300,
        xaxis=dict(
            title="Cumulative Characters Written (backspaces & enters excluded)",
            showgrid=True, gridcolor="rgba(255,255,255,0.06)",
            range=[0, total_chars * 1.02],
        ),
        yaxis=dict(
            tickvals=[1, 2, 3],
            ticktext=["Human", "AI", "Paste"],
            tickfont=dict(size=13), range=[0.3, 3.7],
            showgrid=True, gridcolor="rgba(255,255,255,0.07)", zeroline=False,
        ),
        legend=dict(orientation="h", yanchor="bottom", y=1.05,
                    xanchor="right", x=1, font=dict(size=11)),
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
        font_color="#e2e8f0", height=280,
        xaxis=dict(title="Cumulative Characters (demo)",
                   showgrid=True, gridcolor="rgba(255,255,255,0.06)"),
        yaxis=dict(
            tickvals=[1, 2, 3],
            ticktext=["Human", "AI", "Paste"],
            tickfont=dict(size=13), range=[0.3, 3.7],
            showgrid=True, gridcolor="rgba(255,255,255,0.07)", zeroline=False,
        ),
        legend=dict(orientation="h", yanchor="bottom", y=1.05,
                    xanchor="right", x=1, font=dict(size=11)),
        margin=dict(t=45, b=45, l=110, r=20),
    )
    for trace in fig_ph.data:
        trace.update(opacity=0.45)
    st.plotly_chart(fig_ph, use_container_width=True)
    st.caption(
        "(Demo - submit a session to see the real timeline.)"
        " Notice how the AI plateau spans hundreds of characters in one instant jump,"
        " while human stretches are short incremental steps."
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
            color_discrete_map={"Human": "#10b981", "Paste": "#f59e0b", "AI": "#3b82f6"},
            hole=0.48,
        )
        fig_pie.update_layout(
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            font_color="#e2e8f0", height=340,
            legend=dict(orientation="h", yanchor="top", y=-0.05),
            margin=dict(t=20, b=20, l=20, r=20),
        )
        fig_pie.update_traces(textinfo="percent+label", textfont_size=13)
        st.plotly_chart(fig_pie, use_container_width=True)
        st.caption("Character-weighted distribution of window-level classifier predictions.")
    else:
        st.info("No prediction data yet.")

with gt_col:
    st.subheader("Validation Reference")
    if has_session:
        gt_df = pd.DataFrame(
            [{"Authorship": k, "Percentage (%)": v} for k, v in gt.items()]
        )
        color_map = {"Human": "#10b981", "Paste": "#f59e0b", "AI": "#3b82f6"}
        fig_gt = px.bar(
            gt_df, x="Authorship", y="Percentage (%)",
            color="Authorship", color_discrete_map=color_map,
            text_auto=".1f",
        )
        fig_gt.update_layout(
            showlegend=False,
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            font_color="#e2e8f0", yaxis_range=[0, 100], height=340,
            margin=dict(t=20, b=20, l=20, r=20),
        )
        fig_gt.update_traces(textposition="outside")
        st.plotly_chart(fig_gt, use_container_width=True)
        st.caption(
            f"Ground Truth tags - "
            f"Human: {gt.get('Human', 0):.1f}% | "
            f"Paste: {gt.get('Paste', 0):.1f}% | "
            f"AI: {gt.get('AI', 0):.1f}%"
        )
    else:
        st.info("No session data yet.")

st.divider()

# =============================================================================
# BLOCK 5 - Technical Biometric Data (collapsible deep-dive)
# =============================================================================
with st.expander("Technical Biometric Data", expanded=False):

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
                return ["background-color: rgba(16,185,129,0.12)"] * 4
            return ["background-color: rgba(239,68,68,0.10)"] * 4

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
                line=dict(color="#10b981", width=2), marker=dict(size=5),
            ))
            fig_cmp.add_trace(go.Scatter(
                x=windows_nums, y=pd_series,
                mode="lines+markers", name="ML Prediction",
                line=dict(color="#7c3aed", width=2, dash="dot"), marker=dict(size=5),
            ))
            fig_cmp.update_layout(
                yaxis=dict(tickvals=[0, 1, 2], ticktext=["Human", "AI", "Paste"],
                           title="Label"),
                xaxis_title="Window #",
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                font_color="#e2e8f0", height=280,
                legend=dict(orientation="h", yanchor="bottom", y=1.02),
            )
            st.plotly_chart(fig_cmp, use_container_width=True)
    else:
        st.info("Per-window breakdown will appear here once a session is processed.")

# -- Footer -------------------------------------------------------------------
st.divider()
st.caption("Project Verve - Version v0.0.1 - Behavioral Biometric Authentication System")
