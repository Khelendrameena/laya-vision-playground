#!/usr/bin/env bash
# Laya Vision Playground — pehli baar venv + deps install honge
# (torch bada hai, time lagega), phir site http://localhost:8200 par.
set -e
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt

echo ""
echo "  👁  Laya Vision Playground"
echo "  Kholo:  http://localhost:8200"
echo "  Pehli baar model (~800 MB) HuggingFace se download hoga —"
echo "  site par 'Model load ho raha hai…' dikhega, ready hone par ✅ aayega."
echo ""
exec .venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8200
