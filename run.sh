#!/usr/bin/env bash
# Laya Vision Playground — pehli baar venv + deps install honge
# (torch bada hai, time lagega — har step terminal me dikhega),
# phir site http://localhost:8200 par.
set -e
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  echo "==> [1/3] Virtual environment ban raha hai…"
  python3 -m venv .venv
else
  echo "==> [1/3] Virtual environment pehle se hai, skip"
fi

echo "==> [2/3] Dependencies install ho rahi hain (pehli baar torch ki"
echo "          wajah se 5–15 min lag sakte hain — download progress"
echo "          neeche dikhta rahega, terminal band mat karna)…"
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

echo ""
echo "==> [3/3] Server start ho raha hai"
echo ""
echo "  👁  Laya Vision Playground"
echo "  Kholo:  http://localhost:8200"
echo "  Pehli baar model (~800 MB) HuggingFace se download hoga —"
echo "  site par 'Model load ho raha hai…' dikhega, ready hone par ✅ aayega."
echo "  Band karne ke liye: Ctrl+C"
echo ""
exec .venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8200
