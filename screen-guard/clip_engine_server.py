"""Screen Guard — Smart Engine Server (WSL / GPU side).

Ye server WSL ke andar chalta hai, jahan playground wali venv me
torch + transformers + nudenet pehle se hain aur RTX GPU milta
hai. Windows wala screen_guard.py har badle hue frame ki chhoti
JPEG isko bhejta hai (http://127.0.0.1:8300/check), ye do engine
chalata hai aur verdict wapas deta hai:

  1. CLIP ViT-L/14 zero-shot — "dark" ki WIDE definition:
     kiss/romance, suggestive, nudity, horror, violence, alcohol.
     Categories sirf English text hain — koi training nahi.
  2. NudeNet (strict rule: threshold 0.25, covered classes bhi)
     — explicit ke liye wahi purana pakka engine.

CLIP KA BLOCK RULE (andha argmax NAHI — saboot ke saath banaya):
    block  agar  dark_best >= 0.60
           ya    (dark_best - safe_best) >= 0.10
Kyoon: 15 Nov 2026 ko 6 asli images par test hua (sab ki sachchai
aankh se verify ki gayi). Plain argmax (dark > safe) par bada
CLIP bhi 2 galat block deta tha — church ki chhat (margin 0.06)
aur suit pehne aadmi (margin 0.05). Asli dark images ka margin
bahut bada tha (asli kiss 0.53, bikini 0.999). Margin rule ke
saath result 6/6 sahi. Chhota CLIP (ViT-B/32) is test me 1/5 par
fail hua aur Falconsai NSFW classifier ne bikini photo ko
"normal 1.0" bola — dono reject. Isi liye bada model + margin.

Chalana (WSL, playground wali venv se):
    cd ~/laya_image/laya-vision-playground
    .venv/bin/python screen-guard/clip_engine_server.py
Pehli baar ~1.7 GB model download hoga (progress dikhega).
Ek image ka test (server chalu kiye bina):
    .venv/bin/python screen-guard/clip_engine_server.py --test-image img.jpg
Privacy: frame sirf localhost par WSL tak jaata hai — machine se
bahar kuch nahi jaata, kuch save nahi hota (ek temp file par
overwrite hota hai, NudeNet ko path chahiye isiliye).
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

PORT = 8300
MODEL_ID = "openai/clip-vit-large-patch14"
TMP_FRAME = os.path.join(HERE, "engine_last.jpg")

DARK_LABELS = [
    "a kissing or romantic scene between a couple",
    "sexually suggestive content, people in revealing clothes or swimwear",
    "nudity or sexual content",
    "a horror, scary or disturbing dark scene",
    "violence, blood or gore",
    "people drinking alcohol, smoking or using drugs",
]
SAFE_LABELS = [
    "people fully clothed in everyday life, working or studying",
    "a nature landscape, building or object, no people",
    "a family friendly scene suitable for children",
]
# Test kiye hue numbers par rakhe hue hain — upar docstring dekho.
CLIP_ABS_BLOCK = 0.60     # dark_best akele itna bada = seedha block
CLIP_MARGIN = 0.10        # dark_best - safe_best itna ya zyada = block


def clip_verdict(scores: dict):
    """scores: {label: probability}. (block, dark_best, dark_label,
    safe_best) lautata hai — margin rule ke saath."""
    dark_best, dark_label = 0.0, ""
    for lab in DARK_LABELS:
        v = float(scores.get(lab, 0.0))
        if v > dark_best:
            dark_best, dark_label = v, lab
    safe_best = max(float(scores.get(lab, 0.0)) for lab in SAFE_LABELS)
    block = dark_best >= CLIP_ABS_BLOCK or \
        (dark_best - safe_best) >= CLIP_MARGIN
    return block, dark_best, dark_label, safe_best


class Engine:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.clip = None
        self.clip_device = "off"
        self.detector = None
        self._load_clip()
        self._load_nudenet()

    def _load_clip(self) -> None:
        try:
            import torch
            from transformers import pipeline

            use_cuda = torch.cuda.is_available()
            print(f"CLIP {MODEL_ID} load ho raha hai "
                  f"({'GPU' if use_cuda else 'CPU'} par) — pehli baar "
                  "download me kuch minute lagenge…", flush=True)
            t0 = time.time()
            self.clip = pipeline("zero-shot-image-classification",
                                 model=MODEL_ID,
                                 device=0 if use_cuda else -1)
            self.clip_device = "cuda" if use_cuda else "cpu"
            print(f"CLIP ready ({time.time() - t0:.0f}s, "
                  f"device={self.clip_device})", flush=True)
        except Exception as exc:  # noqa: BLE001
            print(f"⚠ CLIP load nahi hua ({exc}) — sirf NudeNet "
                  "chalega.", flush=True)
            self.clip = None

    def _load_nudenet(self) -> None:
        try:
            from nudenet import NudeDetector

            self.detector = NudeDetector()
            print("NudeNet ready.", flush=True)
        except Exception as exc:  # noqa: BLE001
            print(f"⚠ NudeNet load nahi hua ({exc}) — sirf CLIP "
                  "chalega.", flush=True)
            self.detector = None

    def check_pil(self, img) -> dict:
        """Ek PIL image par dono engine; combined verdict dict."""
        t0 = time.time()
        out = {"block": False, "reasons": [], "clip": None,
               "nudenet_block": False}
        with self.lock:
            if self.clip is not None:
                res = self.clip(img, candidate_labels=DARK_LABELS
                                + SAFE_LABELS)
                scores = {r["label"]: float(r["score"]) for r in res}
                block, db, dl, sb = clip_verdict(scores)
                out["clip"] = {"dark": round(db, 3),
                               "safe": round(sb, 3),
                               "margin": round(db - sb, 3),
                               "label": dl, "block": block}
                if block:
                    out["block"] = True
                    out["reasons"].append(
                        f"CLIP: {dl} (dark {db:.2f} vs safe {sb:.2f})")
            if self.detector is not None:
                img.save(TMP_FRAME)
                try:
                    from screen_guard import (STRICT_CLASSES,
                                              STRICT_THRESHOLD,
                                              verdict_for)
                    dets = self.detector.detect(TMP_FRAME)
                    nb, hits = verdict_for(dets, STRICT_THRESHOLD,
                                           STRICT_CLASSES)
                except Exception as exc:  # noqa: BLE001
                    print(f"NudeNet check fail: {exc}", flush=True)
                    nb, hits = False, []
                out["nudenet_block"] = bool(nb)
                if nb:
                    out["block"] = True
                    desc = ", ".join(
                        f"{d['class']} {float(d['score']):.2f}"
                        for d in hits)
                    out["reasons"].append(f"NudeNet: {desc}")
        out["ms"] = int((time.time() - t0) * 1000)
        return out

    def status(self) -> dict:
        return {"ok": True, "clip": self.clip is not None,
                "device": self.clip_device,
                "nudenet": self.detector is not None,
                "model": MODEL_ID}


ENGINE: Engine | None = None


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # console saaf rakho
        pass

    def _json(self, code: int, obj: dict) -> None:
        body = json.dumps(obj).encode()
        try:
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass  # client pehle hi chala gaya (timeout) — shor nahi

    def do_GET(self):
        if self.path.startswith("/status"):
            self._json(200, ENGINE.status())
        else:
            self._json(404, {"ok": False})

    def do_POST(self):
        if not self.path.startswith("/check"):
            self._json(404, {"ok": False})
            return
        try:
            n = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(n) or b"{}")
            from PIL import Image

            raw = base64.b64decode(data["image_b64"])
            img = Image.open(io.BytesIO(raw)).convert("RGB")
            self._json(200, ENGINE.check_pil(img))
        except Exception as exc:  # noqa: BLE001
            self._json(500, {"ok": False, "error": str(exc)})


def main(argv=None) -> int:
    global ENGINE
    p = argparse.ArgumentParser(description="Screen Guard smart engine")
    p.add_argument("--test-image", metavar="PATH",
                   help="Server chalu kiye bina ek image check karo")
    p.add_argument("--port", type=int, default=PORT)
    args = p.parse_args(argv)

    ENGINE = Engine()
    if args.test_image:
        from PIL import Image

        img = Image.open(args.test_image).convert("RGB")
        out = ENGINE.check_pil(img)
        print(f"{'🔴 BLOCK' if out['block'] else '🟢 SAFE'}  "
              f"({out['ms']}ms)")
        for r in out["reasons"]:
            print(f"  HIT  {r}")
        if out["clip"]:
            c = out["clip"]
            print(f"  CLIP: dark {c['dark']} ({c['label']}), "
                  f"safe {c['safe']}, margin {c['margin']}")
        print(f"  NudeNet block: {out['nudenet_block']}")
        return 0

    srv = ThreadingHTTPServer(("0.0.0.0", args.port), Handler)
    print("=" * 62, flush=True)
    print(f"✅ ENGINE READY — http://0.0.0.0:{args.port} "
          f"(status: /status, check: POST /check)", flush=True)
    print("Ab Windows par start_guard.bat chalao — guard khud "
          "engine se jud jayega.", flush=True)
    print("=" * 62, flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
