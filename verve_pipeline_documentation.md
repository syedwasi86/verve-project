# Project Verve — Complete Pipeline Documentation

**Team:** 1604-23-733 · Syed Majid Ali · Syed Wasi Uddin · Syed Ghulam Hussain  
**Stack:** TypeScript (VS Code Extension) → FastAPI (Python Backend) → Scikit-learn (ML) → Streamlit (Dashboard)

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Data Flow Diagram](#2-data-flow-diagram)
3. [Layer 1 — VS Code Extension](#3-layer-1--vs-code-extension)
4. [Layer 2 — FastAPI Backend](#4-layer-2--fastapi-backend)
5. [Layer 3 — ML Pipeline](#5-layer-3--ml-pipeline)
6. [Layer 4 — Streamlit Dashboard](#6-layer-4--streamlit-dashboard)
7. [Data Schemas](#7-data-schemas)
8. [Feature Definitions](#8-feature-definitions)
9. [Source Detection Algorithm](#9-source-detection-algorithm)
10. [Running the System](#10-running-the-system)

---

## 1. System Overview

Project Verve is a **behavioral biometrics pipeline** that passively monitors a developer's typing patterns inside VS Code and determines, with machine-learning confidence, whether the code being produced is:

| Label | Meaning |
|---|---|
| **Human** | Typed character-by-character by the developer |
| **AI** | Inserted by an AI autocomplete/copilot tool (large block, near-zero inter-key delay) |
| **Paste** | Pasted from clipboard (multi-char insertion matching clipboard content) |

The system does **not** require any code changes from the developer. It hooks into VS Code's `onDidChangeTextDocument` event and silently collects biometric signals — flight times, dwell times, insertion sizes, cursor jumps — that are then shipped to a backend ML classifier.

---

## 2. Data Flow Diagram

```
┌─────────────────────────────────────────────────────────┐
│              VS Code Extension (TypeScript)             │
│                                                         │
│  Developer types / AI inserts / pastes                  │
│         ↓ onDidChangeTextDocument                       │
│  TrackerService.ts                                      │
│  ├─ calculateDwellTime()  → d (dwell ms)                │
│  ├─ determineKeyType()    → k (single/bulk/enter/bs)    │
│  ├─ determineSource()     → s (h/a/p/u)                 │
│  └─ Emit VerveEvent {t,f,d,o,l,s,k}                    │
│         ↓ Stop Tracking                                 │
│  VerveSession JSON assembled                            │
│         ↓                                               │
│  ┌──────────────────────────────┐                       │
│  │ Save Locally (fs.writeFile)  │ → projects/data/*.json│
│  │ Post to Backend (fetch POST) │ → localhost:8000      │
│  └──────────────────────────────┘                       │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼ POST /process-session
┌─────────────────────────────────────────────────────────┐
│              FastAPI Backend (Python)                   │
│                        main.py                          │
│                          ↓                              │
│              preprocess.py : process_session()          │
│  ├─ 1. Parse events → DataFrame                         │
│  ├─ 2. Ground-truth % (character-weighted)              │
│  ├─ 3. Build rhythm_data (real flight times + source)   │
│  ├─ 4. Sliding windows (size=40, step=8)                │
│  ├─ 5. extract_features() per window (9 features)       │
│  ├─ 6. StandardScaler → scale features                  │
│  ├─ 7. RandomForest / best_classifier.pkl → predict     │
│  ├─ 8. Weighted class distribution                      │
│  └─ 9. Assemble JSON result                             │
│                          ↓                              │
│           Cache result in _latest_result                │
│                          ↓ GET /latest                  │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼ Streamlit polls GET /latest
┌─────────────────────────────────────────────────────────┐
│           Streamlit Dashboard  (app.py)                 │
│  Section 1 — Session Metadata                           │
│  Section 2 — Authenticity Metrics (5 KPIs)              │
│  Section 3 — Ground Truth vs ML Prediction charts       │
│  Section 4 — Keystroke Rhythm (real flight-time chart)  │
│  Section 5 — Extracted Features Table (9 features)      │
│  Section 6 — Per-Window Breakdown (GT vs Pred)          │
│  Section 7 — Final System Verdict + probabilities       │
└─────────────────────────────────────────────────────────┘
```

---

## 3. Layer 1 — VS Code Extension

### 3.1 Architecture

The extension consists of two source files:

| File | Role |
|---|---|
| `src/extension.ts` | VS Code entry point — registers commands, webview provider, lifecycle |
| `src/TrackerService.ts` | All tracking logic — event capture, source detection, save/post |

Supporting resources:

| File | Role |
|---|---|
| `resources/webview.js` | In-panel UI logic (button clicks, status display) |
| `resources/webview.css` | In-panel styling |
| `resources/verveicon.png` | Activity-bar icon |

### 3.2 Activation & UI

The extension registers a **Webview View** in VS Code's Activity Bar under the panel titled **"Verve Tracking"**. It activates automatically when this panel is first opened (`onView:verveTrackingView`).

The panel renders a minimal HTML page with:
- A **status indicator** that shows `"Status: Inactive"` or `"Status: Tracking Active ⏱️"` (green background when active)  
- A **Start Tracking** button (disabled during active tracking)  
- A **Stop Tracking** button (disabled when not tracking)  
- A **session info** line showing `"Session in progress..."` during capture

### 3.3 Registered Commands

| Command ID | Title | Behavior |
|---|---|---|
| `verve.startTracking` | Verve: Start Typing Dynamics Tracking | Initializes a new session, attaches listeners |
| `verve.stopTracking` | Verve: Stop Typing Dynamics Tracking | Stops session, shows QuickPick for output |
| `verve.endTracking` | Verve: End Tracking & Save + Post | Stops and immediately does both save + post in parallel |

### 3.4 TrackerService — Core Logic

#### Session Lifecycle

```
startTracking()
  ├─ Guard: already tracking? → warn & return
  ├─ Guard: no active editor? → error & return
  ├─ Create VerveSession { sessionId (UUID v4), startTime, languageId, filePath, events:[] }
  └─ Call setupListeners()

stopTracking()
  ├─ Guard: not tracking? → warn & return null
  ├─ Dispose all listeners
  ├─ Set session.endTime = Date.now()
  └─ Return the completed VerveSession
```

#### Event Listener

The core listener is `vscode.workspace.onDidChangeTextDocument`. It fires on **every** text change in the active editor  — keystrokes, deletions, AI completions, pastes.

For each `ContentChange` in the event:

```
1. flightTime = now - lastEventTimestamp    (0 for first event)
2. lastEventTimestamp = now
3. dwellTime  = calculateDwellTime(context)
4. keyType    = determineKeyType(context)
5. source     = determineSource(context, flightTime, keyType, dwellTime)
6. If source ∈ {a, p} → override keyType = 'bulk'
7. Push VerveEvent to session.events[]
```

#### 3.4.1 Dwell Time Estimation

VS Code's extension API cannot directly read raw key-up/key-down hardware events, so dwell time is **estimated** based on key type:

| Key Type | Dwell Time | Rationale |
|---|---|---|
| `single` | 40–100 ms (random) | Typical human finger contact duration |
| `backspace` | 50–120 ms (random) | Slightly longer, deliberate correction |
| `enter` | 60–150 ms (random) | Intentional line-break keystroke |
| `bulk` / `paste` / AI | **0 ms** | Instant machine insertion, no physical key held |

The 0 ms bulk dwell time is a **golden feature** — it is the clearest signal separating human from AI/paste at the single-event level.

#### 3.4.2 Key Type Classification

Priority order (first match wins):

```
1. BACKSPACE  rangeLength > 0  AND  text === ""
2. BULK       text.length > 5
3. ENTER      text contains '\n' or '\r'   (only if not bulk)
4. SINGLE     text.length === 1
5. BULK (2-5) text.length > 1             (fallback)
6. DEFAULT    'single'
```

> **Why bulk has priority over enter:** A multi-line AI completion (e.g., an entire function body) contains newlines but should be classified as `bulk` so the Random Forest sees the `burst_ratio` signal.

#### 3.4.3 Source Detection Algorithm

Priority order (first match wins):

```
1. isFirstEvent                                → 'h'   (always human)
2. text.length > 1  AND  clipboardCache match  → 'p'   (paste verified)
3. text.length > 1  AND  dwellTime === 0
       AND  text is not whitespace-only        → 'a'   (AI insertion)
4. keyType === 'backspace'                     → 'h'   (error correction)
5. text.length === 1  AND  flightTime > 20ms   → 'h'   (human keystroke)
6. keyType === 'enter'                         → 'h'   (intentional enter)
7. (none matched)                              → 'u'   (unknown)
```

**Clipboard detection** is done asynchronously via `vscode.env.clipboard.readText()`. The result is cached in `clipboardCache`. When a multi-character insertion arrives, its text is compared (after normalization of whitespace/CRLF) to the cached clipboard. A match → `'p'` (paste).

#### 3.4.4 Dual Output

**Save Locally (`saveSessionLocally`):**
- Target directory: `C:\Users\syed wasi uddin\OneDrive\Desktop\projects\data`
- Auto-creates the directory with `fs.mkdirSync({ recursive: true })` if it doesn't exist
- Filename: `verve-session-<ISO-timestamp>.json`
- Content: minified JSON (no whitespace), UTF-8 encoded
- Written synchronously via `fs.writeFileSync`
- Notification toast shows the full path + event count

**Post to Backend (`postSessionToBackend`):**
- Endpoint: `POST http://localhost:8000/process-session`
- Body: full `VerveSession` JSON
- Fires a standard `fetch()` from the Node.js context
- Shows success toast with event count, or error toast with HTTP status

---

## 4. Layer 2 — FastAPI Backend

### 4.1 File: `backend/main.py`

Minimal FastAPI wrapper. Responsibilities:
- Expose `POST /process-session` — receives the VerveSession, calls `process_session()`, caches result
- Expose `GET /latest` — returns the cached result to the Streamlit dashboard
- Expose `GET /health` — simple liveness check
- CORS middleware opened (`allow_origins=["*"]`) so both the extension and Streamlit can reach it

The result is stored in the module-level dict `_latest_result` protected by a `threading.Lock` (thread-safe for FastAPI's async workers).

### 4.2 File: `backend/preprocess.py`

The pipeline's brain. Called once per session POST.

```python
process_session(data: dict) → dict
```

#### Step-by-step

**Step 1 — Parse events into DataFrame**  
`events_to_dataframe(data)` converts the JSON `events` list into a pandas DataFrame with columns:

| Column | Type | Description |
|---|---|---|
| `t` | int | Timestamp (ms epoch) |
| `f` | float | Flight time (ms) |
| `d` | float | Dwell time (ms) |
| `o` | int | Cursor offset (char position) |
| `l` | int | Text length (chars inserted) |
| `s` | str | Source tag: h/a/p/u |
| `k` | str | Key type: single/bulk/enter/backspace |

Events are sorted by `t` and numeric coercion is applied to `l` and `f`.

---

**Step 2 — Session metadata**  
Extracts `sessionId`, `languageId`, `filePath`, and calculates `duration_s = (endTime - startTime) / 1000`.

---

**Step 3 — Ground Truth Percentages (character-weighted)**  

```python
total_chars = df["l"].sum()
true_h = df[df["s"]=="h"]["l"].sum() / total_chars * 100
true_p = df[df["s"]=="p"]["l"].sum() / total_chars * 100
true_a = df[df["s"]=="a"]["l"].sum() / total_chars * 100
```

This is **character-weighted**, not event-weighted. A single 500-character AI-generated function counts as 500 AI characters, giving an accurate picture of the actual content split.

---

**Step 4 — Rhythm Data (real flight times)**

Builds a `rhythm_data` list of up to 200 sampled events with:
- `i` — keystroke sequence number
- `f` — actual flight time in ms (clipped to [0, 8000])
- `s` — source label (Human / AI / Paste / Unknown)

This is sampled evenly if the session has >200 events. The data is returned to the dashboard to plot the real rhythm chart with colour-coded dots by source.

---

**Step 5 — Sliding Window Extraction**

```
Window size : 40 events
Step size   : 8 events   (80% overlap)
```

Events tagged as `'u'` (unknown) are excluded before windowing.

Edge cases:
- Session ≤ 40 events → single window containing all events
- Final partial window → last 40 events appended to ensure full coverage

For each window, the dominant source tag (by character count) determines the window's ground-truth label.

---

**Step 6 — Feature Extraction (per window)**

9 features are extracted from every window. See [Section 8](#8-feature-definitions) for detail.

---

**Step 7 — Outlier Clipping**

`flight_time_jitter` is clipped to a maximum of 5000 ms before scaling, preventing extreme outliers from dominating the StandardScaler.

---

**Step 8 — Session-Level Feature Aggregation**

All per-window feature vectors are averaged (column-wise mean) to produce a single session feature dict. The raw-event `mean_flight_time` and `std_flight_time` are also attached for the dashboard display.

---

**Step 9 — ML Inference**

Three model artifacts are loaded once at import time:

| File | Object | Role |
|---|---|---|
| `scaler_cls.pkl` | `StandardScaler` | Normalise feature values |
| `best_classifier.pkl` | `RandomForestClassifier` | Predict label per window |
| `label_encoder.pkl` | `LabelEncoder` | Decode `h/a/p` → class index |

```python
X_scaled  = scaler.transform(X_unscaled)     # (n_windows × 9)
cls_preds = model.predict(X_scaled)          # (n_windows,) → encoded ints
decoded   = encoder.inverse_transform(...)   # (n_windows,) → ['h','p','a',...]
proba     = model.predict_proba(X_scaled)    # (n_windows × 3) — if supported
```

---

**Step 10 — Weighted Class Distribution**

Each window's prediction is weighted by its character count (`l.sum()`):

```python
for pred_tag, length in zip(decoded, lengths):
    weighted_counts[pred_tag] += length

class_distribution = { label: (count / total) * 100 for ... }
```

This produces a percentage breakdown like `{"Human": 12.0, "AI": 85.0, "Paste": 3.0}` that reflects how many *characters* (not windows) were estimated to be each type.

---

**Step 11 — Session-Level Verdict**

- `dominant_label` = class with highest weighted count  
- `confidence` = its share of the weighted total  
- `authenticity_score` = `mean_proba["h"] × 100` — higher = more human  
- `human_probability`, `paste_probability`, `ai_probability` = mean window probabilities

---

**Step 12 — Per-Window Breakdown**

A list of records: `{ window, length, ground_truth, prediction }` for every window, allowing the dashboard to show a window-by-window accuracy view.

---

### 4.3 File: `backend/features_util.py`

Pure utility module. Contains:

| Function | Description |
|---|---|
| `events_to_dataframe(json_data)` | Converts event list → DataFrame, validates columns |
| `create_sliding_windows(df, size, step)` | Yields overlapping windows, handles small sessions |
| `extract_features(window)` | Calls all 9 calculators, returns dict |
| `calculate_mean_dwell_time(w)` | Mean of `d` column |
| `calcultate_std_flight_time(w)` | Std of `f` column (= jitter) |
| `calculate_typing_velocity(w)` | `sum(l)` / window duration in seconds |
| `calculate_correction_rate(w)` | `count(k=='backspace')` / len(window) |
| `calculate_burst_ratio(w)` | `count(l>1)` / len(window) |
| `calculate_max_burst_length(w)` | `max(l)` |
| `calculate_bulk_event_ratio(w)` | `count(k=='bulk')` / len(window) |
| `calculate_mean_cursor_jump(w)` | Mean absolute difference of `o` column |
| `calculate_event_entropy(w)` | Shannon entropy of `k` value distribution |

---

## 5. Layer 3 — ML Pipeline

### 5.1 Classifier

The model artifact `best_classifier.pkl` is a trained **Random Forest Classifier** with label-encoded targets (`h`, `a`, `p`).

The classifier was trained on labelled session data with the 9 window-level features as input. The `LabelEncoder` maps:

| Code | Label |
|---|---|
| `h` | Human |
| `a` | AI |
| `p` | Paste |

### 5.2 Training Configuration

| Parameter | Value |
|---|---|
| Window size | 40 events |
| Step size | 8 events (80% overlap) |
| Features | 9 engineered features |
| Scaler | `StandardScaler` |
| Model | `RandomForestClassifier` (best_classifier.pkl) |

### 5.3 Why These Features?

| Feature | Human signal | AI/Paste signal |
|---|---|---|
| `mean_dwell_time` | 50–120 ms variable | 0 ms (bulk insert) |
| `flight_time_jitter` | High (80–300 ms) | Near-zero (instant batch) |
| `typing_velocity` | 3–8 CPS | Extremely high (100+ CPS) |
| `correction_rate` | Non-zero (humans make errors) | Usually 0 |
| `burst_ratio` | Low (mostly single chars) | High (many multi-char events) |
| `max_burst_length` | 1–3 chars | Hundreds of chars |
| `bulk_event_ratio` | Low | Very high |
| `mean_cursor_jump` | Small, incremental | Large (entire block inserted at offset) |
| `event_entropy` | Varied key types | Low (all bulk, no backspaces) |

---

## 6. Layer 4 — Streamlit Dashboard

### Overview

`app.py` is a Streamlit app that **polls `GET /latest`** on every page refresh. It reads the cached result from the FastAPI backend and renders 7 sections.

The dashboard is styled with:
- **Font:** Inter (Google Fonts)
- **Background:** `#0e1117` (dark)
- **Accent colours:** Purple `#7c3aed`, Green `#10b981`, Blue `#3b82f6`, Amber `#f59e0b`
- **Verdict banners:** Colour-coded green/blue/amber depending on predicted label

---

### Section 1 — Session Metadata

4-column metric cards showing:
- **Session ID** (first 18 chars + ellipsis)
- **Language** (from VS Code editor, e.g., `TYPESCRIPT`)
- **Duration** (seconds)
- **Events Captured** (total event count)

---

### Section 2 — Authenticity Metrics

5 KPI metric cards:

| Card | Calculation | Interpretation |
|---|---|---|
| **Authenticity Score** | `mean_proba["h"] × 100` | 0–100%; higher = more human |
| **Session Label** | Dominant weighted class | Human / AI / Paste |
| **Avg Flight Time** | `df["f"].mean()` (raw events) | Human ≈ 150–400 ms; AI/Paste ≈ 0 |
| **Burst Ratio** | Avg across windows | < 0.5 → Human; > 0.5 → AI/Paste |
| **Std Flight Time** | `df["f"].std()` (raw events) | High → organic variance |

---

### Section 3 — Ground Truth vs ML Prediction

**Left panel — Ground Truth (bar chart)**  
Colour-coded bar chart (green=Human, amber=Paste, blue=AI) showing the character-weighted ground-truth percentages that came directly from the source tags `s` embedded in the events by the extension.

**Right panel — ML Prediction (donut chart)**  
Plotly donut/pie chart of the character-weighted predicted class distribution from the Random Forest. The hole shows the dominant predicted label proportionally.

> Comparing these two panels reveals how accurately the ML model reproduces what the extension's source-detection logic tagged.

---

### Section 4 — Keystroke Rhythm Chart

**Real data, not simulated.** Uses the `rhythm_data` array returned by the backend.

- **X-axis:** Keystroke sequence number (1–200 sampled evenly)
- **Y-axis:** Flight time in milliseconds (clipped to 8000 ms)
- **Colour coding:**
  - 🟢 **Green dots** — Human keystrokes (high, spiky, irregular variance)
  - 🔵 **Blue dots** — AI keystrokes (collapses flat near zero)
  - 🟡 **Amber dots** — Paste keystrokes (also near-zero, single large jump)
  - ⬛ **Grey dots** — Unknown
- **Dotted reference line** at 200 ms marks the typical human baseline
- **Connector line** (barely visible grey) joins all points in sequence order
- **Filled area** (translucent) under the line adds depth

Below the chart, a **summary table** shows Avg Flight Time / Std Dev / # Keystrokes per source — the numerical contrast between Human (high avg, high std) and AI/Paste (near-zero avg, near-zero std) is immediately obvious.

> **Why this works:** AI completions and pastes are bulk insertions that happen in a single event. The flight time for that event is the time since the last keypress — which may be any value — but then immediately followed by nothing (no continuation keystrokes). Within the bulk insertion event itself, `f=0` for every character of the block. The coloured chart exposes this signature visually.

---

### Section 5 — Extracted Features Table

A dataframe table showing the 9 averaged window-level features plus raw-event scalars:

| Feature | Description |
|---|---|
| Mean Dwell Time | Average key-hold duration (ms) |
| Flight Time Jitter | Std dev of flight time (ms) — irregularity measure |
| Mean Flight Time | Raw-event flight time mean (ms) |
| Std Flight Time | Raw-event flight time std (ms) |
| Typing Velocity | Characters per second |
| Correction Rate | Fraction of events that are backspaces |
| Burst Ratio | Fraction of events with `l > 1` |
| Max Burst Length | Largest single insertion (chars) |
| Bulk Event Ratio | Fraction of events classified as `bulk` |
| Mean Cursor Jump | Average absolute cursor position change |
| Event Entropy | Shannon entropy of key-type distribution |
| Windows Analysed | Total sliding windows extracted |

---

### Section 6 — Per-Window Breakdown

Collapsible expander showing a colour-coded table of every window:

| Column | Description |
|---|---|
| Window # | Sequence index |
| Chars in Window | `l.sum()` for that window |
| Ground Truth | Dominant source tag translated to Human/AI/Paste |
| Prediction | Model's predicted label for that window |

Rows are **green-tinted** where GT == Prediction, **red-tinted** where they disagree.

A `Window-level Accuracy` metric shows `correct / total` windows.

If ≤60 windows exist, a **line chart** is also rendered overlaying GT (green solid) and Prediction (purple dotted) as numeric levels (0=Human, 1=AI, 2=Paste).

---

### Section 7 — Final System Verdict

**Verdict Banner** — colour-coded full-width card:
- 🟢 Green banner → Human Authorship Verified
- 🔵 Blue banner → AI-Assisted Pattern Detected
- 🟡 Amber banner → Paste / Mixed Input Detected

Each banner shows:
- Bold verdict title
- Authenticity score (%)
- Model confidence (%)
- Ground truth source pills (Human X% | Paste X% | AI X%)

Below the banner, a **bar chart** of `[Human, AI, Paste]` class probabilities (average across all windows from `predict_proba`) gives a visual sense of the model's certainty.

---

## 7. Data Schemas

### VerveEvent (emitted by extension per text change)

```json
{
  "t": 1712282401000,  // timestamp (ms epoch)
  "f": 120,            // flight time (ms)
  "d": 65,             // dwell time (ms, estimated)
  "o": 42,             // cursor offset (char position)
  "l": 1,              // text length (chars inserted/deleted)
  "s": "h",            // source: h|a|p|u
  "k": "single"        // key type: single|bulk|enter|backspace
}
```

### VerveSession (sent to backend)

```json
{
  "sessionId": "550e8400-e29b-41d4-a716-446655440000",
  "startTime": 1712282400000,
  "endTime":   1712282450000,
  "languageId": "typescript",
  "filePath": "C:/Users/.../src/app.ts",
  "events": [ ...VerveEvent[] ]
}
```

### API Response (`/process-session` and `/latest`)

```json
{
  "status": "ok",
  "num_events": 312,
  "session_meta": {
    "sessionId": "...", "languageId": "python",
    "filePath": "...", "duration_s": 47.3
  },
  "ground_truth":       { "Human": 14.2, "Paste": 0.0, "AI": 85.8 },
  "features": {
    "mean_dwell_time": 0.0, "flight_time_jitter": 12.4,
    "typing_velocity": 98.3, "correction_rate": 0.0,
    "burst_ratio": 0.94, "max_burst_length": 412,
    "bulk_event_ratio": 0.93, "mean_cursor_jump": 215.0,
    "event_entropy": 0.21,
    "mean_flight_time": 8.1, "std_flight_time": 22.3,
    "num_windows": 18
  },
  "prediction": {
    "label_name": "AI", "confidence": 0.9722,
    "authenticity_score": 3.5,
    "human_probability": 0.035,
    "paste_probability": 0.008,
    "ai_probability": 0.957
  },
  "class_distribution": { "Human": 2.3, "Paste": 0.0, "AI": 97.7 },
  "per_window": [
    { "window": 1, "length": 40, "ground_truth": "AI", "prediction": "AI" },
    ...
  ],
  "rhythm_data": [
    { "i": 1, "f": 0.0, "s": "AI" },
    { "i": 2, "f": 2.1, "s": "AI" },
    ...
  ]
}
```

---

## 8. Feature Definitions

| Feature | Formula | Human range | AI/Paste range |
|---|---|---|---|
| `mean_dwell_time` | `mean(d)` | 50–100 ms | ~0 ms |
| `flight_time_jitter` | `std(f)` | 80–400 ms | ~0 ms |
| `typing_velocity` | `sum(l) / duration_s` | 3–8 CPS | 100–10 000 CPS |
| `correction_rate` | `count(k==bs) / n` | 0.05–0.25 | ~0 |
| `burst_ratio` | `count(l>1) / n` | 0.05–0.2 | 0.8–1.0 |
| `max_burst_length` | `max(l)` | 1–5 chars | 50–5 000 chars |
| `bulk_event_ratio` | `count(k==bulk) / n` | 0.0–0.1 | 0.7–1.0 |
| `mean_cursor_jump` | `mean(|diff(o)|)` | 1–10 | 50–1 000 |
| `event_entropy` | `-sum(p log2 p)` over `k` values | 1.5–2.5 bits | 0.1–0.5 bits |

---

## 9. Source Detection Algorithm

The extension uses a **deterministic priority-chain** to assign a source tag to every text change event.

```
Priority 1 (highest): isFirstEvent → 'h'
  Rationale: The very first keystroke in any session is always a human action.

Priority 2: text.length > 1  AND  text matches clipboardCache → 'p'
  Rationale: Clipboard verification is the most reliable paste signal.
  Implementation: vscode.env.clipboard.readText() is called async whenever
  a multi-char insertion arrives. The cache is compared (trim + CRLF normalised).

Priority 3: text.length > 1  AND  dwellTime == 0  AND  not whitespace → 'a'
  Rationale: Multi-character instant insertions with zero dwell = machine-generated.
  Whitespace-only text is excluded to avoid tagging auto-indent as AI.

Priority 4: keyType == 'backspace' → 'h'
  Rationale: Backspace is always a human error-correction action.

Priority 5: text.length == 1  AND  flightTime > 20ms → 'h'
  Rationale: A single character with meaningful inter-key delay = human typed key.

Priority 6: keyType == 'enter' → 'h'
  Rationale: Deliberate newline insertion by the user.

Default: → 'u'
  Very fast single chars (< 20ms) or other ambiguous events are left unknown.
```

---

## 10. Running the System

### Prerequisites

```bash
# Python packages (backend + dashboard)
pip install fastapi uvicorn streamlit pandas numpy plotly scikit-learn joblib requests

# Extension (one-time)
cd verve-project
npm install
npm run compile
```

### Start order

```bash
# Terminal 1 — Backend (from verve/ root)
uvicorn backend.main:app --reload

# Terminal 2 — Dashboard
streamlit run app.py

# VS Code
# Press F5 in verve-project/ to launch Extension Development Host
# Click the Verve icon in the Activity Bar to open the tracking panel
```

### Typical Session Workflow

```
1. Open a source file in VS Code
2. Open Verve panel → click "Start Tracking"
3. Write code (or let AI complete / paste snippets)
4. Click "Stop Tracking"
5. Choose "Post to Backend" (or "Both")
6. Open http://localhost:8501 → Streamlit dashboard refreshes automatically
7. Review all 7 sections for the session analysis
8. Local JSON also saved to C:\Users\syed wasi uddin\OneDrive\Desktop\projects\data\
```

### API Endpoints

| Method | URL | Description |
|---|---|---|
| `POST` | `/process-session` | Submit a VerveSession for analysis |
| `GET` | `/latest` | Retrieve last processed result |
| `GET` | `/health` | Liveness check `{"status":"ok"}` |
| `GET` | `/docs` | FastAPI auto-generated Swagger UI |

---

*Documentation generated: April 2026 — Project Verve v0.0.1*
