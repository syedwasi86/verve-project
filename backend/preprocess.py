"""
preprocess.py — Verve Backend Processing Module

Pure function module: no file I/O, no print statements, no __main__ block.
Called by main.py (FastAPI) to process a raw VerveSession JSON dict into
a structured result dict containing features, ground truth, and ML predictions.
"""

import numpy as np
import pandas as pd
import joblib
from pathlib import Path
from typing import Any, Dict

# Importing feature extraction helpers
from backend.features_util import (
    events_to_dataframe,
    create_sliding_windows,
    extract_features,
)

# ── Resolve model paths relative to THIS file so the server works
#    regardless of which directory uvicorn is launched from ──────────
_BACKEND_DIR = Path(__file__).parent
_SCALER_PATH  = _BACKEND_DIR / "scaler_cls.pkl"
_ENCODER_PATH = _BACKEND_DIR / "label_encoder.pkl"
_MODEL_PATH   = _BACKEND_DIR / "best_classifier.pkl"

# Load models once at import time for performance
try:
    _cls_scaler  = joblib.load(_SCALER_PATH)
    _cls_encoder = joblib.load(_ENCODER_PATH)
    _cls_model   = joblib.load(_MODEL_PATH)
    _models_loaded = True
    _model_name  = type(_cls_model).__name__   # e.g. "RandomForestClassifier"
except Exception as _e:
    _models_loaded = False
    _load_error = str(_e)
    _model_name  = "Unknown"


# ── Tag mappings ──────────────────────────────────────────────────────
_TAG_MAP = {"h": "Human", "p": "Paste", "a": "AI", "u": "Unknown"}

# Window hyperparameters (must match training)
_WINDOW_SIZE = 40
_STEP_SIZE   = 8


def process_session(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process a raw VerveSession JSON dict and return a structured result.

    Parameters
    ----------
    data : dict
        Raw session payload from the VS Code extension.
        Expected keys: sessionId, startTime, endTime, languageId,
                       filePath, events (list of event dicts)

    Returns
    -------
    dict with keys:
        status            : "ok" | "error" | "no_data"
        num_events        : int
        session_meta      : dict  (sessionId, languageId, filePath, duration_s)
        ground_truth      : dict  {"Human": %, "Paste": %, "AI": %}
        features          : dict  aggregated session-level features (mean across windows)
        prediction        : dict  {label_name, confidence, authenticity_score,
                                   human_probability, paste_probability, ai_probability}
        class_distribution: dict  {"Human": %, "Paste": %, "AI": %} – weighted window preds
        per_window        : list  [{"window": i, "length": int,
                                    "ground_truth": str, "prediction": str}, ...]
        error             : str   (only present on error)
    """
    # ── 1. Parse events into DataFrame ───────────────────────────────
    try:
        df = events_to_dataframe(data)
    except Exception as exc:
        return {"status": "error", "error": f"Failed to parse events: {exc}"}

    if df.empty:
        return {"status": "no_data", "num_events": 0}

    df = df.sort_values("t").reset_index(drop=True)
    df["l"] = pd.to_numeric(df["l"], errors="coerce").fillna(0)
    df["f"] = pd.to_numeric(df["f"], errors="coerce").fillna(0)

    num_events = len(df)

    # ── 2. Session metadata ──────────────────────────────────────────
    start_time = data.get("startTime", 0)
    end_time   = data.get("endTime", 0)
    duration_s = max((end_time - start_time) / 1000.0, 0) if end_time else 0
    session_meta = {
        "sessionId":  data.get("sessionId", ""),
        "languageId": data.get("languageId", ""),
        "filePath":   data.get("filePath", ""),
        "duration_s": round(duration_s, 2),
    }

    # ── 3. Ground truth percentages (character-weighted) ─────────────
    total_chars = df["l"].sum()
    if total_chars > 0:
        true_h = float(df.loc[df["s"] == "h", "l"].sum() / total_chars * 100)
        true_p = float(df.loc[df["s"] == "p", "l"].sum() / total_chars * 100)
        true_a = float(df.loc[df["s"] == "a", "l"].sum() / total_chars * 100)
    else:
        true_h = true_p = true_a = 0.0

    ground_truth = {
        "Human": round(true_h, 2),
        "Paste": round(true_p, 2),
        "AI":    round(true_a, 2),
    }

    # ── 4. Session-level scalar features (computed from raw events) ──
    #    These supplement the window-level features for the dashboard.
    mean_flight_time = float(df["f"].mean()) if len(df) > 0 else 0.0
    std_flight_time  = float(df["f"].std())  if len(df) > 1 else 0.0

    # ── 4b. Build rhythm data for the Authorship State-Flow chart ────
    #    Strategy: keep only CONTENT-CREATION events (single + bulk keys,
    #    exclude backspace / enter / unknown-source / zero-length).
    #    Compute cumulative character count as the X-axis so AI blocks
    #    appear as long flat plateaus and human typing as a slow slope.
    #    Each record: { "cumchars": int, "s": source_label, "l": chars }
    _SOURCE_LABEL = {"h": "Human", "p": "Paste", "a": "AI", "u": "Unknown"}
    rhythm_content = df[
        df["k"].isin(["single", "bulk"]) &   # content keys only
        (df["s"] != "u") &                    # drop unknown-source events
        (df["l"] > 0)                         # drop zero-length insertions
    ].copy()
    rhythm_content["cumchars"] = rhythm_content["l"].cumsum().astype(int)
    # Sample down to ≤500 rows while keeping cumchars positions meaningful
    if len(rhythm_content) > 500:
        step = max(1, len(rhythm_content) // 500)
        rhythm_content = rhythm_content.iloc[::step].head(500)
    rhythm_data = [
        {
            "cumchars": int(row["cumchars"]),
            "s": _SOURCE_LABEL.get(str(row["s"]), "Unknown"),
            "l": int(row["l"]),
        }
        for _, row in rhythm_content.iterrows()
    ]

    # ── 5. Sliding window feature extraction ─────────────────────────
    windows = create_sliding_windows(df, _WINDOW_SIZE, _STEP_SIZE)

    if not windows:
        return {
            "status":     "no_data",
            "num_events": num_events,
            "session_meta": session_meta,
            "ground_truth": ground_truth,
            "features":   {},
            "prediction": {},
            "class_distribution": {},
            "per_window": [],
        }

    features_list  = []
    lengths        = []
    window_gt_cls  = []

    for w in windows:
        feats = extract_features(w)
        features_list.append(feats)

        w_len = float(w["l"].sum())
        lengths.append(w_len)

        if w_len > 0:
            dominant = w.groupby("s")["l"].sum().idxmax()
            window_gt_cls.append(_TAG_MAP.get(dominant, "Unknown"))
        else:
            window_gt_cls.append("Unknown")

    total_length_weighted = sum(lengths) if sum(lengths) > 0 else 1.0

    # ── 6. Build feature DataFrame + clip outlier ────────────────────
    X_unscaled = pd.DataFrame(features_list)
    if "flight_time_jitter" in X_unscaled.columns:
        X_unscaled["flight_time_jitter"] = X_unscaled["flight_time_jitter"].clip(upper=5000)

    # ── 7. Aggregate session-level features (mean across windows) ────
    agg_features: Dict[str, float] = {
        col: round(float(X_unscaled[col].mean()), 4)
        for col in X_unscaled.columns
    }
    # Add the raw-event-derived features (used by the Streamlit dashboard)
    agg_features["mean_flight_time"] = round(mean_flight_time, 2)
    agg_features["std_flight_time"]  = round(std_flight_time, 2)
    agg_features["num_windows"]      = len(windows)

    # ── 8. ML Classification ─────────────────────────────────────────
    if not _models_loaded:
        return {
            "status":       "error",
            "error":        f"Models failed to load: {_load_error}",
            "num_events":   num_events,
            "session_meta": session_meta,
            "ground_truth": ground_truth,
            "features":     agg_features,
            "prediction":   {},
            "class_distribution": {},
            "per_window":   [],
        }

    try:
        X_scaled   = _cls_scaler.transform(X_unscaled)
        cls_preds  = _cls_model.predict(X_scaled)
        decoded    = list(_cls_encoder.inverse_transform(cls_preds))  # ['h','p','a',...]

        # Probability estimates (for confidence + authenticity score)
        if hasattr(_cls_model, "predict_proba"):
            proba       = _cls_model.predict_proba(X_scaled)   # shape (n_windows, n_classes)
            # classes_ already holds the original string labels ('a', 'h', 'p')
            classes_dec = list(_cls_encoder.classes_)
            mean_proba  = proba.mean(axis=0)                    # average across windows
            proba_map   = dict(zip(classes_dec, mean_proba.tolist()))
        else:
            proba_map = {}

    except Exception as exc:
        return {
            "status":       "error",
            "error":        f"Prediction failed: {exc}",
            "num_events":   num_events,
            "session_meta": session_meta,
            "ground_truth": ground_truth,
            "features":     agg_features,
            "prediction":   {},
            "class_distribution": {},
            "per_window":   [],
        }

    # ── 9. Weighted class distribution (from window predictions) ────
    weighted_counts = {"h": 0.0, "p": 0.0, "a": 0.0}
    for pred_tag, length in zip(decoded, lengths):
        if pred_tag in weighted_counts:
            weighted_counts[pred_tag] += length

    class_distribution = {
        _TAG_MAP[k]: round(weighted_counts[k] / total_length_weighted * 100, 2)
        for k in ["h", "p", "a"]
    }

    # ── 10. Session-level label = dominant weighted class ─────────────
    dominant_tag    = max(weighted_counts, key=weighted_counts.get)
    dominant_label  = _TAG_MAP[dominant_tag]
    dominant_weight = weighted_counts[dominant_tag] / total_length_weighted

    human_prob  = proba_map.get("h", 0.0)
    paste_prob  = proba_map.get("p", 0.0)
    ai_prob     = proba_map.get("a", 0.0)
    confidence  = float(dominant_weight)
    auth_score  = round(human_prob * 100.0, 2)

    prediction = {
        "label_name":        dominant_label,
        "model":             _model_name,
        "confidence":        round(confidence, 4),
        "authenticity_score": auth_score,
        "human_probability": round(human_prob, 4),
        "paste_probability": round(paste_prob, 4),
        "ai_probability":    round(ai_prob, 4),
    }

    # ── 11. Per-window breakdown ──────────────────────────────────────
    per_window = [
        {
            "window":       i + 1,
            "length":       int(lengths[i]),
            "ground_truth": window_gt_cls[i],
            "prediction":   _TAG_MAP.get(decoded[i], "Unknown"),
        }
        for i in range(len(windows))
    ]

    return {
        "status":             "ok",
        "num_events":         num_events,
        "session_meta":       session_meta,
        "ground_truth":       ground_truth,
        "features":           agg_features,
        "prediction":         prediction,
        "class_distribution": class_distribution,
        "per_window":         per_window,
        "rhythm_data":        rhythm_data,
    }
