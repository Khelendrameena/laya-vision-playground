@echo off
rem Screen Guard bina terminal ke background me chalao (pythonw).
rem Double-click karo — koi window nahi khulegi, upar corner me
rem sirf chhota sa status pill dikhega. Band karne ke liye
rem stop_guard.py chalana padega (10 minute countdown ke saath).
cd /d %~dp0
start "" pythonw screen_guard.py
