"""Screen Guard v2 — live screen blocker (NudeNet engine, fast).

Kya karta hai: screen ko har ~0.5 second scan karta hai, NudeNet v3
(ONNX, local, koi upload nahi) se explicit content check karta hai,
aur lagatar 2 baar mile to poori screen par kaala BLOCK overlay
dikha deta hai. Safe frames wapas aate hi overlay khud hat jata hai.

TEZ kaise hai (v1 se fark):
  * Frame-diff skip: screen badli hi nahi (static page, ruka hua
    video) to detection skip — bekaar ki mehnat zero. Badlaav par
    hi asli check chalta hai (~20–80 ms ONNX inference).
  * Chhota scan frame (512px) + sirf latest frame par kaam —
    purane frames ka queue nahi banta, guard hamesha current
    screen par rehta hai.
  * Upar right corner me chhota status pill: 🛡 SAFE / ⛔ BLOCK /
    💤 SNOOZE + last scan ka time — guard chal raha hai ya nahi,
    hamesha dikhta hai.

Engine scope: NudeNet SIRF nudity pakadta hai (exposed body parts).
Violence / horror / gore / dark scenes iske scope me NAHI hain.

Galat block ho jaye to: **Esc** dabao — 60 second snooze (overlay
hat jayega, scanning chalti rahegi, block nahi lagega).

IMPORTANT — Windows par chalao, WSL me nahi (WSL se Windows desktop
ka screenshot nahi liya ja sakta):
    py -m pip install nudenet mss pillow
    py screen_guard.py                # live guard
    py screen_guard.py --test-image "C:\\path\\image.jpg"   # ek image test
Band karne ke liye terminal me Ctrl+C, ya pill par ✕.

Privacy: screenshots kahin upload/save nahi hote. Har frame ek hi
temp file par overwrite hota hai; sirf verdict + time log banta hai.
"""

from __future__ import annotations

import argparse
import os
import sys
import threading
import time

# Sirf ye exposed classes BLOCK karte hain. BELLY / FEET / ARMPITS
# jaan-bujh kar bahar — aam photos me aate hain, false block karte
# hain. FACE_* kabhi block nahi.
EXPLICIT_CLASSES = {
    "FEMALE_GENITALIA_EXPOSED",
    "MALE_GENITALIA_EXPOSED",
    "FEMALE_BREAST_EXPOSED",
    "MALE_BREAST_EXPOSED",
    "FEMALE_BUTTOCKS_EXPOSED",
    "MALE_BUTTOCKS_EXPOSED",
    "ANUS_EXPOSED",
    "FEMALE_ANUS_EXPOSED",
    "MALE_ANUS_EXPOSED",
}
DEFAULT_THRESHOLD = 0.50   # isse upar ka explicit detection = hit
SCAN_EVERY_SEC = 0.5       # scan cadence (diff-skip ke saath sasta hai)
DETECT_WIDTH = 512         # detection ke liye frame ki chaudai (px)
DIFF_THRESHOLD = 1.5       # isse kam average badlaav = frame same, skip
HITS_TO_BLOCK = 2          # lagatar 2 hit tabhi overlay (flicker rokne ko)
SAFE_TO_UNBLOCK = 3        # lagatar 3 safe tabhi overlay hatayega
SNOOZE_SEC = 60
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "screen_guard_log.txt")
TMP_SHOT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "screen_guard_last.png")


def log(msg: str) -> None:
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')}  {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def verdict_for(detections, threshold: float = DEFAULT_THRESHOLD):
    """NudeNet detections -> (block?, hits)."""
    hits = [d for d in (detections or [])
            if d.get("class") in EXPLICIT_CLASSES
            and float(d.get("score", 0)) >= threshold]
    return bool(hits), hits


def frame_changed(prev_gray, cur_gray, threshold: float = DIFF_THRESHOLD) -> bool:
    """Do chhote grayscale frames (numpy) me kaafi badlaav hai kya?
    Static screen par detection skip karne ke liye."""
    if prev_gray is None or cur_gray is None:
        return True
    import numpy as np

    diff = np.abs(cur_gray.astype("float32") - prev_gray.astype("float32"))
    return float(diff.mean()) >= threshold


def check_image(detector, path: str, threshold: float = DEFAULT_THRESHOLD):
    t0 = time.time()
    detections = detector.detect(path)
    ms = int((time.time() - t0) * 1000)
    block, hits = verdict_for(detections, threshold)
    return block, hits, ms


def make_detector():
    from nudenet import NudeDetector

    return NudeDetector()


# ------------------------------------------------------------------
# Live guard: worker thread scan karta hai, Tk main thread pill +
# overlay sambhalta hai. Dono ke beech ek shared state dict hai.
# ------------------------------------------------------------------

class GuardState:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.mode = "starting"      # starting|safe|hit|blocked|snooze
        self.last_ms = None
        self.scans = 0              # asli detections kitne hue
        self.skips = 0              # diff-skip kitne hue
        self.top = ""               # last hit ka description
        self.snooze_until = 0.0
        self.stop = False


def scan_worker(state: GuardState, threshold: float, interval: float,
                width: int) -> None:
    import mss
    import numpy as np
    from PIL import Image

    detector = make_detector()
    hits = safe = 0
    prev_gray = None
    log(f"Screen Guard v2 shuru — har {interval}s scan, frame-diff skip on. "
        "Band karne ke liye Ctrl+C ya pill par ✕.")
    with mss.mss() as sct:
        monitor = sct.monitors[1]  # primary monitor
        while not state.stop:
            t0 = time.time()
            try:
                shot = sct.grab(monitor)
                img = Image.frombytes("RGB", shot.size, shot.rgb)
                gray = np.asarray(
                    img.convert("L").resize((160, 90)), dtype="uint8")
                snoozed = time.time() < state.snooze_until
                if not frame_changed(prev_gray, gray):
                    with state.lock:
                        state.skips += 1
                        if state.mode not in ("blocked",) and not snoozed:
                            state.mode = "safe" if state.mode != "hit" \
                                else state.mode
                    prev_gray = gray
                else:
                    prev_gray = gray
                    small = img.resize(
                        (width, int(img.height * width / img.width)))
                    small.save(TMP_SHOT)
                    block, top, ms = check_image(detector, TMP_SHOT, threshold)
                    with state.lock:
                        state.scans += 1
                        state.last_ms = ms
                    if snoozed:
                        with state.lock:
                            state.mode = "snooze"
                    elif block:
                        hits += 1
                        safe = 0
                        desc = ", ".join(
                            f"{d['class']} {float(d['score']):.2f}"
                            for d in top)
                        log(f"HIT ({ms}ms): {desc}")
                        with state.lock:
                            state.top = desc
                            state.mode = "blocked" if hits >= HITS_TO_BLOCK \
                                else "hit"
                    else:
                        safe += 1
                        hits = 0
                        with state.lock:
                            if safe >= SAFE_TO_UNBLOCK or state.mode != "blocked":
                                state.mode = "safe"
            except Exception as exc:  # noqa: BLE001 — ek frame fail = rukna nahi
                log(f"Scan error (chalta rahega): {exc}")
            elapsed = time.time() - t0
            time.sleep(max(0.05, interval - elapsed))


def run_live(threshold: float, interval: float, width: int) -> int:
    try:
        import mss  # noqa: F401
        from PIL import Image  # noqa: F401
        import tkinter as tk
    except ImportError as exc:
        print(f"Missing dependency: {exc}\n"
              "Windows Python me chalao:  py -m pip install nudenet mss pillow")
        return 2

    state = GuardState()
    worker = threading.Thread(target=scan_worker,
                              args=(state, threshold, interval, width),
                              daemon=True)
    worker.start()

    root = tk.Tk()
    root.overrideredirect(True)
    root.attributes("-topmost", True)
    root.configure(bg="#131a22")
    sw = root.winfo_screenwidth()
    root.geometry(f"300x34+{sw - 312}+10")
    pill = tk.Label(root, text="🛡 Guard start ho raha hai…",
                    font=("Segoe UI", 10, "bold"), fg="#e6edf3",
                    bg="#131a22", anchor="w")
    pill.pack(side="left", fill="both", expand=True, padx=8)
    quit_btn = tk.Label(root, text=" ✕ ", font=("Segoe UI", 11, "bold"),
                        fg="#f87171", bg="#131a22", cursor="hand2")
    quit_btn.pack(side="right")

    overlay = {"win": None}

    def show_overlay():
        if overlay["win"] is not None:
            return
        win = tk.Toplevel(root)
        win.attributes("-fullscreen", True)
        win.attributes("-topmost", True)
        win.configure(bg="black")
        win.overrideredirect(True)
        tk.Label(win, text="⛔  BLOCKED", font=("Segoe UI", 64, "bold"),
                 fg="white", bg="black").pack(expand=True)
        tk.Label(win, text="Explicit content detect hua — screen block hai\n"
                           "Galat block hai? Esc dabao — 60 second snooze",
                 font=("Segoe UI", 16), fg="#bbbbbb", bg="black").pack()
        win.bind("<Escape>", lambda _e: snooze())
        overlay["win"] = win

    def hide_overlay():
        if overlay["win"] is not None:
            overlay["win"].destroy()
            overlay["win"] = None

    def snooze():
        state.snooze_until = time.time() + SNOOZE_SEC
        with state.lock:
            state.mode = "snooze"
        hide_overlay()
        log(f"Snooze {SNOOZE_SEC}s — galat block report ki tarah treat kiya")

    def quit_all():
        state.stop = True
        root.destroy()

    quit_btn.bind("<Button-1>", lambda _e: quit_all())
    root.bind("<Escape>", lambda _e: snooze())

    def poll():
        with state.lock:
            mode, ms, scans, skips = (state.mode, state.last_ms,
                                      state.scans, state.skips)
        if mode == "blocked":
            show_overlay()
            pill.config(text="⛔ BLOCKED — explicit content", fg="#fca5a5")
        elif mode == "snooze":
            hide_overlay()
            left = max(0, int(state.snooze_until - time.time()))
            pill.config(text=f"💤 SNOOZE {left}s — scan chal raha hai",
                        fg="#fcd34d")
        elif mode == "hit":
            pill.config(text="⚠ Ek hit mila — agla frame check ho raha hai",
                        fg="#fcd34d")
        elif mode == "safe":
            extra = f" · last {ms}ms" if ms is not None else ""
            pill.config(text=f"🛡 SAFE · scans {scans} · skip {skips}{extra}",
                        fg="#86efac")
        else:
            pill.config(text="🛡 Guard start ho raha hai…", fg="#e6edf3")
        if not state.stop:
            root.after(150, poll)

    poll()
    try:
        root.mainloop()
    except KeyboardInterrupt:
        pass
    state.stop = True
    log("Screen Guard band.")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Live screen guard v2 (NudeNet)")
    p.add_argument("--test-image", metavar="PATH",
                   help="Sirf ek image check karo, live guard mat chalao")
    p.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD,
                   help="Explicit score ki seema (default 0.50)")
    p.add_argument("--interval", type=float, default=SCAN_EVERY_SEC,
                   help="Har kitne second me scan (default 0.5)")
    p.add_argument("--width", type=int, default=DETECT_WIDTH,
                   help="Detection frame ki chaudai px me (default 512)")
    args = p.parse_args(argv)
    if args.test_image:
        if not os.path.exists(args.test_image):
            print(f"File nahi mili: {args.test_image}")
            return 2
        detector = make_detector()
        block, hits, ms = check_image(detector, args.test_image,
                                      args.threshold)
        print(f"{'🔴 BLOCK' if block else '🟢 SAFE'}  ({ms}ms)")
        for d in hits:
            print(f"  {d.get('class')}  score {float(d.get('score', 0)):.2f}")
        if not hits:
            print("  koi explicit detection nahi")
        return 0
    return run_live(args.threshold, args.interval, args.width)


if __name__ == "__main__":
    sys.exit(main())
