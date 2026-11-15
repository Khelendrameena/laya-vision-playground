@echo off
rem Screen Guard v4 — pehle WSL wala smart engine (CLIP, GPU par),
rem phir bina terminal ke guard (pythonw, STRICT mode).
rem
rem Engine wali window KHULI rehne do — pehli baar ~1.7 GB model
rem download hoga, us window me progress dikhega. Engine band bhi
rem ho jaye to guard sirf local NudeNet par chalta rahega (pill par
rem "engine OFF" dikhega) — par kiss/suggestive/horror wali pakad
rem engine se hi aati hai, isiliye engine chalu rakhna.
rem WSL ka repo path alag ho to neeche wali line ka path badal do.
rem
rem Band karne ke liye stop_guard.py chalana padega (10 minute
rem countdown ke saath). Engine window Ctrl+C se band kar sakte ho.
start "ScreenGuard Engine (WSL - band mat karna)" wsl -d Ubuntu -- bash -lc "cd ~/laya_image/laya-vision-playground && .venv/bin/python screen-guard/clip_engine_server.py"
cd /d %~dp0
start "" pythonw screen_guard.py --strict
