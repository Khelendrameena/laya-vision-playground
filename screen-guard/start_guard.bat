@echo off
rem Screen Guard bina terminal ke background me chalao (pythonw).
rem Double-click karo — koi window nahi khulegi, upar corner me
rem sirf chhota sa status pill dikhega. STRICT mode me chalta hai
rem (threshold 0.25, covered classes bhi block, pehli hit par BLOCK).
rem Normal mode chahiye to: py screen_guard.py
rem Band karne ke liye stop_guard.py chalana padega (10 minute
rem countdown ke saath).
cd /d %~dp0
start "" pythonw screen_guard.py --strict
