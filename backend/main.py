"""
main.py — Verve FastAPI Backend

Endpoints:
  POST /process-session   ← receives VerveSession JSON from the VS Code extension
  GET  /latest            ← returns the most recently processed session result

Run from the project root (verve/):
    uvicorn backend.main:app --reload
"""

from __future__ import annotations

import threading
from typing import Any, Dict

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.preprocess import process_session

# ── App setup ─────────────────────────────────────────────────────────
app = FastAPI(
    title="Verve Authenticity API",
    description="Behavioral biometrics analysis — Human vs AI vs Paste detection",
    version="1.0.0",
)

# Allow the VS Code extension (any localhost port) and Streamlit to call us
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── In-memory store for the latest result ─────────────────────────────
_store_lock: threading.Lock = threading.Lock()
_latest_result: Dict[str, Any] = {"status": "no_data"}


# ── Endpoints ─────────────────────────────────────────────────────────

@app.post("/process-session", summary="Process a VerveSession from the extension")
async def process_session_endpoint(request: Request) -> JSONResponse:
    """
    Accepts the raw VerveSession JSON payload POSTed by the VS Code extension,
    runs preprocessing + ML inference, caches the result, and returns it.

    Expected payload shape (from TrackerService.ts):
    {
        "sessionId":  string,
        "startTime":  number,
        "endTime":    number,
        "languageId": string,
        "filePath":   string,
        "events": [
            { "t": number, "f": number, "d": number,
              "o": number, "l": number, "s": string, "k": string },
            ...
        ]
    }
    """
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="Payload must be a JSON object")

    # Run the ML pipeline
    result = process_session(data)

    # Cache in memory so GET /latest can serve it
    global _latest_result
    with _store_lock:
        _latest_result = result

    return JSONResponse(content=result)


@app.get("/latest", summary="Return the most recently processed session result")
async def get_latest() -> JSONResponse:
    """
    Returns the result of the last POST /process-session call.
    If no session has been processed yet, returns {"status": "no_data"}.

    Polled by the Streamlit dashboard on every refresh.
    """
    with _store_lock:
        result = dict(_latest_result)
    return JSONResponse(content=result)


@app.get("/health", summary="Health check")
async def health() -> Dict[str, str]:
    return {"status": "ok", "service": "verve-api"}
