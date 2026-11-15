"""Screen Guard v3 — live screen blocker (NudeNet), bypass-resistant.

Kya karta hai: screen ko har ~0.5 second scan karta hai, NudeNet v3
(ONNX, local, koi upload nahi) se explicit content check karta hai,
aur lagatar 2 baar mile to saari screens par kaala BLOCK overlay
dikha deta hai. Safe frames wapas aate hi overlay khud hat jata hai.

BYPASS-RESISTANT DESIGN (v3 — v2 ka Esc snooze hi sabse bada
bypass tha, isiliye hata diya):
  * Esc snooze NAHI hai, pill par ✕ NAHI hai, overlay band karne
    ka koi button NAHI hai. Block se nikalne ka ek hi tareeka hai:
    galat page/app se hat jao — screen safe hote hi overlay khud
    hat jata hai (lagatar 3 safe frame).
  * Overlay har monitor par aata hai, hamesha sabse upar rehta
    hai, aur band ho jaye to poll loop use khud wapas bana deta hai.
  * WATCHDOG: ek dusra process (pythonw, bina window ke) guard ko
    dekhta rehta hai. Guard mara (Ctrl+C, Task Manager, crash) to
    watchdog use ~10 second me wapas chalu kar deta hai. Guard bhi
    watchdog ko dekhta hai — dono ek dusre ko zinda rakhte hain.
  * Band karne ka EK HI sanctioned rasta: stop_guard.py chalao,
    lambi wali line type karo, phir 10 MINUTE rukna padega
    (pill par countdown dikhta hai). Countdown ke beech mann
    badal jaye to stop cancel ho sakta hai. Impulse wala pal
    nikaalne ke liye hi ye deri hai — Cold Turkey jaise tools
    bhi yahi karte hain.
  * Sach ye bhi hai: apni machine par admin tum khud ho, isiliye
    100% unbypassable kuch nahi hota (dono processes ko ek saath
    Task Manager se marna ab bhi mumkin hai). Design ka maksad
    bypass ko slow/annoying banana hai, impossible nahi.

Chalana (Windows Python, WSL me NAHI):
    py -m pip install nudenet mss pillow
    start_guard.bat            <- double-click; bina terminal ke
                                  background me chalega (pythonw)
                                  — ab STRICT mode me chalta hai
  ya terminal se:  py screen_guard.py --strict
Test pehle:  py screen_guard.py --strict --test-image "C:\\path\\image.jpg"
Band karna:  py stop_guard.py   (phir 10 minute ka countdown)

STRICT MODE (--strict, ab start_guard.bat ka default):
  * Threshold 0.50 -> 0.25 (NudeNet isse neeche ja hi nahi sakta —
    uska apna floor ~0.20-0.25 hai, isiliye 0.25 hi sabse sakht hai)
  * Pehli hit par hi BLOCK (lagatar 2 ka intezaar nahi)
  * Covered suggestive classes bhi block: FEMALE_BREAST_COVERED,
    FEMALE_GENITALIA_COVERED, BUTTOCKS_COVERED, ANUS_COVERED,
    BELLY_EXPOSED / BELLY_COVERED
  * Keemat: normal skin-heavy videos (gym, dance, sports, beach)
    bhi block ho sakte hain — strict ka matlab hi ye hai.
  * Normal mode ab bhi hai: bina --strict chalao.
  * BUG FIX (strict ke saath): purane EXPLICIT_CLASSES me
    FEMALE/MALE_BUTTOCKS_EXPOSED aur FEMALE/MALE_ANUS_EXPOSED
    naam the — NudeNet v3 ke 18 labels me ye naam hote hi nahi
    (sahi naam: BUTTOCKS_EXPOSED, ANUS_EXPOSED), isiliye buttocks
    wali detection kabhi gini hi nahi jaati thi. Ab sahi naam hain.

Engine scope: NudeNet SIRF nudity pakadta hai. Violence / horror /
gore iske scope me NAHI hain — strict mode skin detection ko
zyada se zyada sensitive banata hai, violence ka detector nahi
jodta. Horror/violence wali content ke liye alag engine (CLIP
zero-shot ya Qwen2.5-VL) lagega — wo agla step hai.
Privacy: screenshots kahin upload/save nahi hote; har frame ek hi
temp file par overwrite hota hai, sirf verdict + time log banta hai.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))

# NudeNet v3 ke asal 18 labels (nudenet/nudenet.py __labels) — inke
# bahar ka koi naam kabhi match nahi karega, isiliye yahi likhne hain.
EXPLICIT_CLASSES = {
    "FEMALE_GENITALIA_EXPOSED",
    "MALE_GENITALIA_EXPOSED",
    "FEMALE_BREAST_EXPOSED",
    "MALE_BREAST_EXPOSED",
    "BUTTOCKS_EXPOSED",
    "ANUS_EXPOSED",
}
# Strict: exposed ke saath covered/suggestive bhi. FACE / FEET /
# ARMPITS jaan-bujh kar bahar — un par block hota to har chehre
# wali video block ho jaati, guard bekaar ho jaata.
STRICT_CLASSES = EXPLICIT_CLASSES | {
    "FEMALE_BREAST_COVERED",
    "FEMALE_GENITALIA_COVERED",
    "BUTTOCKS_COVERED",
    "ANUS_COVERED",
    "BELLY_EXPOSED",
    "BELLY_COVERED",
}
DEFAULT_THRESHOLD = 0.50
STRICT_THRESHOLD = 0.25
SCAN_EVERY_SEC = 0.5
DETECT_WIDTH = 512
DIFF_THRESHOLD = 1.5
HITS_TO_BLOCK = 2
STRICT_HITS_TO_BLOCK = 1
SAFE_TO_UNBLOCK = 3
STOP_DELAY_SEC = 600        # stop_guard ke baad itni der rukna padega
LOG_FILE = os.path.join(HERE, "screen_guard_log.txt")
TMP_SHOT = os.path.join(HERE, "screen_guard_last.png")
GUARD_HB = os.path.join(HERE, "guard.heartbeat")
WATCHDOG_HB = os.path.join(HERE, "watchdog.heartbeat")
STOP_REQ = os.path.join(HERE, "stop_request.txt")
STOP_DONE = os.path.join(HERE, "stop_done.txt")


def log(msg: str) -> None:
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')}  {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def _touch(path: str) -> None:
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(str(time.time()))
    except OSError:
        pass


def _age(path: str):
    """File kitni purani hai (seconds) — na ho to None."""
    try:
        return time.time() - os.path.getmtime(path)
    except OSError:
        return None


def _remove(path: str) -> None:
    try:
        os.unlink(path)
    except OSError:
        pass


def _pythonw() -> str:
    """Console-less python (pythonw.exe) ka path, na mile to current."""
    exe = sys.executable
    cand = exe.replace("python.exe", "pythonw.exe")
    if cand != exe and os.path.exists(cand):
        return cand
    return exe


def verdict_for(detections, threshold: float = DEFAULT_THRESHOLD,
                classes=EXPLICIT_CLASSES):
    hits = [d for d in (detections or [])
            if d.get("class") in classes
            and float(d.get("score", 0)) >= threshold]
    return bool(hits), hits


def frame_changed(prev_gray, cur_gray, threshold: float = DIFF_THRESHOLD) -> bool:
    if prev_gray is None or cur_gray is None:
        return True
    import numpy as np

    diff = np.abs(cur_gray.astype("float32") - prev_gray.astype("float32"))
    return float(diff.mean()) >= threshold


def check_image(detector, path: str, threshold: float = DEFAULT_THRESHOLD,
                classes=EXPLICIT_CLASSES):
    t0 = time.time()
    detections = detector.detect(path)
    ms = int((time.time() - t0) * 1000)
    block, hits = verdict_for(detections, threshold, classes)
    return block, hits, ms, detections


def make_detector():
    from nudenet import NudeDetector

    return NudeDetector()


def _is_wsl() -> bool:
    if os.environ.get("WSL_DISTRO_NAME"):
        return True
    try:
        with open("/proc/sys/kernel/osrelease", encoding="utf-8") as f:
            return "microsoft" in f.read().lower()
    except OSError:
        return False


# ------------------------------------------------------------------
# Watchdog: guard mare to wapas chalaye. Guard bhi ise zinda rakhta
# hai. Dono heartbeat files se ek dusre ko dekhte hain.
# ------------------------------------------------------------------

# Strict flag ko watchdog respawn me bhi saath le jaana hai — warna
# guard mar kar wapas normal mode me chalu ho jaata. main() ise set
# karta hai; _spawn har child command me jod deta hai.
_STRICT = False


def _spawn(mode) -> None:
    script = os.path.join(HERE, "screen_guard.py")
    cmd = [_pythonw(), script]
    if _STRICT:
        cmd.append("--strict")
    cmd += [mode] if mode else []
    try:
        subprocess.Popen(cmd, cwd=HERE, close_fds=True)
    except Exception as exc:  # noqa: BLE001
        log(f"Spawn fail ({mode}): {exc}")


def run_watchdog() -> int:
    log("Watchdog shuru.")
    while True:
        _touch(WATCHDOG_HB)
        if os.path.exists(STOP_DONE):
            _remove(STOP_REQ)
            _remove(STOP_DONE)
            log("Watchdog band (proper stop ho gaya).")
            return 0
        req_age = _age(STOP_REQ)
        if req_age is not None:
            # Stop ka countdown chal raha hai — guard ko restart
            # NAHI karna. Guard mar bhi gaya ho aur request bahut
            # purani ho gayi ho, to safai karke band ho jao.
            if req_age > STOP_DELAY_SEC + 300 and \
                    (_age(GUARD_HB) or 0) > 15:
                _remove(STOP_REQ)
                log("Watchdog band (purani stop request saaf ki).")
                return 0
            time.sleep(3)
            continue
        hb_age = _age(GUARD_HB)
        if hb_age is None or hb_age > 12:
            log("Guard band mila — wapas chalu kar raha hu.")
            _spawn(None)  # pura guard (wo khud watchdog ko dekhega)
            time.sleep(8)
        time.sleep(3)


# ------------------------------------------------------------------
# Guard
# ------------------------------------------------------------------

class GuardState:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.mode = "starting"      # starting|safe|hit|stopping (pill ke liye)
        self.blocked_now = False    # overlay ka asal switch — mode se alag,
                                    # taaki stop-countdown ke dauran bhi
                                    # blocking chaalu rahe
        self.last_ms = None
        self.scans = 0
        self.skips = 0
        self.top = ""
        self.stop_deadline = None   # stopping mode me kab band hoga
        self.stop = False


def scan_worker(state: GuardState, threshold: float, interval: float,
                width: int, classes=EXPLICIT_CLASSES,
                hits_to_block: int = HITS_TO_BLOCK) -> None:
    import mss
    import numpy as np
    from PIL import Image

    detector = make_detector()
    hits = safe = 0
    prev_gray = None
    mode_name = "STRICT" if classes is STRICT_CLASSES else "normal"
    log(f"Screen Guard v3 shuru [{mode_name}: threshold {threshold}, "
        f"pehli {hits_to_block} hit par BLOCK] — har {interval}s scan, "
        "frame-diff on, watchdog saath me. Band karne ka rasta: "
        f"stop_guard.py (phir {STOP_DELAY_SEC // 60} min countdown).")
    mss_factory = getattr(mss, "MSS", None) or getattr(mss, "mss")
    with mss_factory() as sct:
        # monitors[0] = saari screens mila kar — pehle sirf primary
        # monitor scan hota tha, dusri screen par chala video guard
        # ko dikhta hi nahi tha (overlay sab par aata tha, aankhein
        # sirf ek screen par thi).
        monitor = sct.monitors[0]
        while not state.stop:
            t0 = time.time()
            _touch(GUARD_HB)
            try:
                shot = sct.grab(monitor)
                img = Image.frombytes("RGB", shot.size, shot.rgb)
                gray = np.asarray(
                    img.convert("L").resize((160, 90)), dtype="uint8")
                if not frame_changed(prev_gray, gray):
                    with state.lock:
                        state.skips += 1
                    prev_gray = gray
                else:
                    prev_gray = gray
                    small = img.resize(
                        (width, int(img.height * width / img.width)))
                    small.save(TMP_SHOT)
                    block, top, ms, _all = check_image(
                        detector, TMP_SHOT, threshold, classes)
                    with state.lock:
                        state.scans += 1
                        state.last_ms = ms
                    if block:
                        hits += 1
                        safe = 0
                        desc = ", ".join(
                            f"{d['class']} {float(d['score']):.2f}"
                            for d in top)
                        log(f"HIT ({ms}ms): {desc}")
                        with state.lock:
                            state.top = desc
                            if hits >= hits_to_block:
                                state.blocked_now = True
                            elif state.mode != "stopping":
                                state.mode = "hit"
                    else:
                        safe += 1
                        hits = 0
                        with state.lock:
                            if safe >= SAFE_TO_UNBLOCK:
                                state.blocked_now = False
                            if state.mode != "stopping" \
                                    and not state.blocked_now:
                                state.mode = "safe"
            except Exception as exc:  # noqa: BLE001
                log(f"Scan error (chalta rahega): {exc}")
            elapsed = time.time() - t0
            time.sleep(max(0.05, interval - elapsed))


def watchdog_monitor(state: GuardState) -> None:
    """Watchdog mar gaya ho to use wapas chalao."""
    while not state.stop:
        age = _age(WATCHDOG_HB)
        if age is None or age > 15:
            if not os.path.exists(STOP_DONE):
                _spawn("--watchdog")
                time.sleep(10)
        time.sleep(5)


def stop_monitor(state: GuardState) -> None:
    """stop_request.txt aaye to countdown shuru; file hate to cancel;
    countdown pura ho to proper band."""
    while not state.stop:
        if os.path.exists(STOP_REQ):
            with state.lock:
                if state.mode != "stopping":
                    state.mode = "stopping"
                    state.stop_deadline = time.time() + STOP_DELAY_SEC
                    log(f"Stop request mili — {STOP_DELAY_SEC // 60} min "
                        "baad band hoga. Cancel karna ho to "
                        "stop_request.txt hata do.")
            if state.stop_deadline and time.time() >= state.stop_deadline:
                _touch(STOP_DONE)
                log("Countdown pura — guard band ho raha hai.")
                state.stop = True
                return
        else:
            with state.lock:
                if state.mode == "stopping":
                    state.mode = "safe"
                    state.stop_deadline = None
                    log("Stop cancel ho gaya — guard chalta rahega.")
        time.sleep(1)


def run_guard(with_watchdog: bool = True, strict: bool = False) -> int:
    if _is_wsl():
        print("=" * 62)
        print("⚠  RUKO — ye script WSL ke andar chal raha hai!")
        print("WSL se Windows ki screen NAHI dikhti. Guard ek khaali")
        print("Linux virtual screen scan karega aur KABHI kuch detect")
        print("nahi hoga — block kabhi nahi aayega.")
        print("")
        print("Sahi tareeka: Windows PowerShell kholo aur chalao:")
        print("    py -m pip install nudenet mss pillow")
        print("    start_guard.bat   (ya: py screen_guard.py)")
        print("=" * 62)
        return 2
    try:
        import mss
        from PIL import Image  # noqa: F401
        import tkinter as tk
    except ImportError as exc:
        print(f"Missing dependency: {exc}\n"
              "Windows Python me chalao:  py -m pip install nudenet mss pillow")
        return 2

    # Fresh start = purani stop files saaf (band karne ka rasta
    # stop_guard wala countdown hi rahega, ye safai sirf pichhle
    # proper-stop ke bache hue nishaan hatati hai)
    _remove(STOP_REQ)
    _remove(STOP_DONE)
    _touch(GUARD_HB)

    # Monitors ki list (overlay har screen par)
    with (getattr(mss, "MSS", None) or getattr(mss, "mss"))() as sct:
        monitors = [dict(m) for m in sct.monitors[1:]] or \
                   [dict(sct.monitors[0])]

    state = GuardState()
    threshold = STRICT_THRESHOLD if strict else DEFAULT_THRESHOLD
    classes = STRICT_CLASSES if strict else EXPLICIT_CLASSES
    hits_to_block = STRICT_HITS_TO_BLOCK if strict else HITS_TO_BLOCK
    threading.Thread(target=scan_worker,
                     args=(state, threshold, SCAN_EVERY_SEC,
                           DETECT_WIDTH, classes, hits_to_block),
                     daemon=True).start()
    threading.Thread(target=stop_monitor, args=(state,),
                     daemon=True).start()
    if with_watchdog:
        threading.Thread(target=watchdog_monitor, args=(state,),
                         daemon=True).start()

    root = tk.Tk()
    root.overrideredirect(True)
    root.attributes("-topmost", True)
    root.configure(bg="#131a22")
    sw = root.winfo_screenwidth()
    root.geometry(f"340x34+{sw - 352}+10")
    pill = tk.Label(root, text="🛡 Guard start ho raha hai…"
                    + (" [STRICT]" if strict else ""),
                    font=("Segoe UI", 10, "bold"), fg="#e6edf3",
                    bg="#131a22", anchor="w")
    pill.pack(side="left", fill="both", expand=True, padx=8)

    overlays = []

    def show_overlays():
        # Band ho gaye overlay khud wapas bante hain — yahi poll
        # loop har 150ms me check karta hai.
        alive = [w for w in overlays if w.winfo_exists()]
        if len(alive) == len(monitors):
            for w in alive:  # hamesha sabse upar
                try:
                    w.lift()
                    w.attributes("-topmost", True)
                except Exception:  # noqa: BLE001
                    pass
            return
        hide_overlays()
        for m in monitors:
            win = tk.Toplevel(root)
            win.overrideredirect(True)
            win.attributes("-topmost", True)
            win.configure(bg="black")
            win.geometry(f"{m['width']}x{m['height']}+{m['left']}+{m['top']}")
            tk.Label(win, text="⛔  BLOCKED",
                     font=("Segoe UI", 64, "bold"),
                     fg="white", bg="black").pack(expand=True)
            tk.Label(win, text="Explicit content detect hua hai.\n"
                               "Ise hatane ka koi button nahi hai — page/app "
                               "badal do,\nscreen safe hote hi block khud "
                               "hat jayega.",
                     font=("Segoe UI", 16), fg="#bbbbbb",
                     bg="black").pack()
            overlays.append(win)

    def hide_overlays():
        for w in overlays:
            try:
                w.destroy()
            except Exception:  # noqa: BLE001
                pass
        overlays.clear()

    def poll():
        if state.stop:
            hide_overlays()
            root.destroy()
            return
        with state.lock:
            mode, ms, scans, skips = (state.mode, state.last_ms,
                                      state.scans, state.skips)
            deadline = state.stop_deadline
            blocked_now = state.blocked_now
        if blocked_now:
            show_overlays()
        else:
            hide_overlays()
        if mode == "stopping":
            left = max(0, int((deadline or time.time()) - time.time()))
            pill.config(text=f"⏳ Band hone me {left // 60}:{left % 60:02d} "
                             "baki — blocking ab bhi chaalu hai",
                        fg="#fcd34d")
        elif blocked_now:
            pill.config(text="⛔ BLOCKED — explicit content", fg="#fca5a5")
        elif mode == "hit":
            hide_overlays()
            pill.config(text="⚠ Ek hit mila — agla frame check ho raha hai",
                        fg="#fcd34d")
        elif mode == "safe":
            hide_overlays()
            extra = f" · last {ms}ms" if ms is not None else ""
            pill.config(text=f"🛡 SAFE · scans {scans} · skip {skips}{extra}",
                        fg="#86efac")
        else:
            pill.config(text="🛡 Guard start ho raha hai…", fg="#e6edf3")
        root.after(150, poll)

    poll()
    try:
        root.mainloop()
    except KeyboardInterrupt:
        pass
    state.stop = True
    if not os.path.exists(STOP_DONE):
        # Ctrl+C / window band se process mara to watchdog use
        # wapas chalu kar dega — yahi design hai. Proper band
        # sirf stop_guard.py ke countdown se hota hai.
        log("Guard process band hua (proper stop NAHI — watchdog "
            "wapas chalu kar dega).")
    return 0


def main(argv=None) -> int:
    global _STRICT
    p = argparse.ArgumentParser(description="Live screen guard v3 (NudeNet)")
    p.add_argument("--test-image", metavar="PATH",
                   help="Sirf ek image check karo, live guard mat chalao")
    p.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    p.add_argument("--strict", action="store_true",
                   help="Strict mode: threshold 0.25, covered classes "
                        "bhi block, pehli hit par BLOCK")
    p.add_argument("--watchdog", action="store_true",
                   help="(internal) watchdog process bano")
    p.add_argument("--guard-only", action="store_true",
                   help="(internal) watchdog ke bina guard chalao")
    args = p.parse_args(argv)
    _STRICT = args.strict
    if args.strict:
        args.threshold = STRICT_THRESHOLD
    classes = STRICT_CLASSES if args.strict else EXPLICIT_CLASSES
    if args.test_image:
        if not os.path.exists(args.test_image):
            print(f"File nahi mili: {args.test_image}")
            return 2
        detector = make_detector()
        block, hits, ms, all_dets = check_image(
            detector, args.test_image, args.threshold, classes)
        mode_name = "STRICT" if args.strict else "normal"
        print(f"{'🔴 BLOCK' if block else '🟢 SAFE'}  [{mode_name}, "
              f"threshold {args.threshold}]  ({ms}ms)")
        print("Engine ko sab kuch dikha (score ke saath):")
        for d in sorted(all_dets, key=lambda x: -float(x.get("score", 0))):
            mark = "HIT" if d in hits else "   "
            print(f"  {mark} {d.get('class')}  "
                  f"score {float(d.get('score', 0)):.2f}")
        if not all_dets:
            print("  koi detection hi nahi — engine ko is image me "
                  "kuch dikha hi nahi (na skin, na body part)")
        if not block and all_dets:
            print("  => SAFE isiliye: jo dikha wo block-list me nahi, "
                  "ya score threshold se neeche tha")
        return 0
    if args.watchdog:
        return run_watchdog()
    return run_guard(with_watchdog=not args.guard_only,
                     strict=args.strict)


if __name__ == "__main__":
    sys.exit(main())
