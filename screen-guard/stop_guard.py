"""Screen Guard ko band karne ka EKMAATRA sanctioned rasta.

    py stop_guard.py

Kya hoga:
  1. Tumhe neeche wali poori line bilkul waise hi type karni hogi
     (copy-paste nahi chalega soch kar — haath se type karo,
     yahi chhoti si rukawat jaan-bujh kar hai).
  2. Phir guard 10 MINUTE ka countdown shuru karega (pill par
     dikhega). Is dauran blocking CHAALU rahegi.
  3. Countdown pura hote hi guard + watchdog dono band ho jayenge.

Mann badal jaye to countdown cancel karna:
    py stop_guard.py --cancel
(ya screen-guard folder se stop_request.txt file hata do.)
"""

from __future__ import annotations

import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
STOP_REQ = os.path.join(HERE, "stop_request.txt")
STOP_DONE = os.path.join(HERE, "stop_done.txt")
PHRASE = "main jaan bujh kar screen guard band kar raha hu"
DELAY_MIN = 10


def main(argv=None) -> int:
    if argv and "--cancel" in argv:
        try:
            os.unlink(STOP_REQ)
            print("✅ Stop cancel ho gaya — guard chalta rahega.")
        except OSError:
            print("Koi pending stop request mili hi nahi.")
        return 0
    if os.path.exists(STOP_DONE):
        print("Guard pehle hi band ho raha hai / ho gaya hai.")
        return 0
    if os.path.exists(STOP_REQ):
        age = int(time.time() - os.path.getmtime(STOP_REQ))
        print(f"Stop request pehle se pending hai ({age}s purani). "
              f"Countdown chal raha hoga — pill dekho.")
        return 0

    print("Screen Guard band karna hai to neeche wali line")
    print("BILKUL WAISE HI haath se type karo:")
    print()
    print(f"    {PHRASE}")
    print()
    try:
        typed = input("> ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nCancel — guard chalta rahega.")
        return 1
    if typed != PHRASE:
        print("❌ Galat likha — guard chalta rahega. Band karna hai "
              "to sahi line type karke phir koshish karo.")
        return 1

    with open(STOP_REQ, "w", encoding="utf-8") as f:
        f.write(str(time.time()))
    print(f"✅ Ho gaya. Ab {DELAY_MIN} minute rukna padega — pill par "
          "countdown chalega aur is dauran blocking chaalu rahegi.")
    print("Mann badal jaye to:  py stop_guard.py --cancel")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
