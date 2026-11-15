"""Laya Vision Playground — localhost site to try the laya-vision
image decision model (github.com/r33drichards/laya-vision).

Model: `thaitea/laya-vision` (SmolVLM-256M backbone, 201M params) —
Laya ka independent fork: image + optional text note par typed,
calibrated decisions (choice / score / noul), koi text generation
nahi. Model startup par background thread me load hota hai; tab tak
/api/status "loading" deta hai aur site par loader dikhta hai —
bina progress ke latka hua blank page nahi.

LAYA_VISION_MOCK=1 ho to asli model ki jagah ek deterministic fake
agent chalta hai (sirf UI/API plumbing test karne ke liye — results
asli model ke NAHI hote, UI me saaf "MOCK" badge dikhta hai).
"""
from __future__ import annotations

import io
import json
import os
import threading
import time

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

MODEL_ID = os.environ.get("LAYA_VISION_MODEL", "thaitea/laya-vision")
MOCK = os.environ.get("LAYA_VISION_MOCK", "") == "1"
FRONTEND = os.path.join(os.path.dirname(__file__), "..", "frontend")

app = FastAPI(title="Laya Vision Playground")

_state = {"status": "loading", "device": None, "error": None,
          "model": MODEL_ID, "mock": MOCK}
_agent = None
_lock = threading.Lock()


class _MockAgent:
    """Deterministic fake — sirf plumbing test ke liye."""

    def predict(self, state, questions):
        import hashlib

        seed = hashlib.md5(
            json.dumps(questions, sort_keys=True).encode()).digest()
        answers = {}
        for i, (qid, q) in enumerate(questions.items()):
            crit = q.get("criteria") or []
            base = (seed[i % len(seed)] % 40) / 100.0  # 0.00–0.39 shift
            if q["type"] == "choice" and crit:
                probs = {c: round(1.0 / len(crit), 4) for c in crit}
                probs[crit[0]] = round(probs[crit[0]] + base, 4)
                answers[qid] = {"type": "choice", "choice": crit[0],
                                "probabilities": probs, "confidence": 0.5}
            elif q["type"] == "score" and crit:
                k = len(crit)
                probs = {str(j): round(1.0 / k, 4) for j in range(k)}
                answers[qid] = {
                    "type": "score",
                    "score": round((k - 1) * (0.4 + base), 2),
                    "legend": {str(j): c for j, c in enumerate(crit)},
                    "probabilities": probs, "confidence": 0.5}
            else:
                answers[qid] = {"type": "noul", "noul": round(0.5 + base, 4),
                                "confidence": 0.6}
        return {"model": "mock", "answers": answers}


def _load_model() -> None:
    global _agent
    try:
        if MOCK:
            _agent = _MockAgent()
            _state.update(status="ready", device="mock")
            return
        import torch

        device = "cuda" if torch.cuda.is_available() else "cpu"
        import laya

        _agent = laya.load_vlm(MODEL_ID, device=device)
        _state.update(status="ready", device=device)
    except Exception as exc:  # load fail = saaf error, hang nahi
        _state.update(status="error", error=f"{type(exc).__name__}: {exc}")


threading.Thread(target=_load_model, daemon=True).start()


@app.get("/api/status")
def status():
    return _state


@app.post("/api/predict")
def predict(image: UploadFile = File(...), note: str = Form(default=""),
            questions: str = Form(...)):
    if _state["status"] == "loading":
        raise HTTPException(503, "Model abhi load ho raha hai — "
                                 "thoda ruk kar dobara try karo")
    if _state["status"] == "error":
        raise HTTPException(503, f"Model load nahi hua: {_state['error']}")
    try:
        qs = json.loads(questions)
    except Exception:
        raise HTTPException(400, "questions valid JSON nahi hai")
    if not isinstance(qs, dict) or not qs:
        raise HTTPException(400, "Kam se kam ek question chahiye")
    if len(qs) > 8:
        raise HTTPException(400, "Ek baar me zyada se zyada 8 questions")
    for qid, q in qs.items():
        t = (q or {}).get("type")
        if t not in ("choice", "score", "noul"):
            raise HTTPException(400, f"{qid}: type choice/score/noul me "
                                     "se ek hona chahiye")
        if t in ("choice", "score") and len(q.get("criteria") or []) < 2:
            raise HTTPException(400, f"{qid}: choice/score ke liye kam "
                                     "se kam 2 criteria chahiye")
    from PIL import Image

    raw = image.file.read()
    if len(raw) > 12 * 1024 * 1024:
        raise HTTPException(400, "Image 12 MB se badi hai")
    try:
        img = Image.open(io.BytesIO(raw)).convert("RGB")
    except Exception:
        raise HTTPException(400, "Ye file image nahi lagti — JPG/PNG do")

    state = {"image": img, "note": note or ""}
    t0 = time.time()
    with _lock:  # ek time par ek hi predict — chhota model, VRAM bachegi
        result = _agent.predict(state, qs)
    ms = int((time.time() - t0) * 1000)
    return {"answers": result.get("answers", {}), "ms": ms,
            "device": _state["device"], "mock": MOCK,
            "model": MODEL_ID}


@app.get("/")
def index():
    return FileResponse(os.path.join(FRONTEND, "index.html"))


app.mount("/static", StaticFiles(directory=FRONTEND), name="static")
