# 👁 Laya Vision Playground

[github.com/r33drichards/laya-vision](https://github.com/r33drichards/laya-vision)
ko apni Ubuntu/WSL machine par try karne ke liye ek chhoti si localhost
site — image upload karo, optional text note do, typed questions
(`choice` / `score` / `noul`) ke calibrated decisions dekho.

**Model:** `thaitea/laya-vision` — Laya (text decision model) ka
independent fork; text encoder ki jagah SmolVLM-256M vision-language
backbone (201M params). Non-generative: koi text generate nahi hota,
har question ka jawab probability ke saath aata hai.

⚠️ **License:** code Apache-2.0, par model **weights CC BY-NC-SA 4.0**
hain (non-commercial) — personal try/learning ke liye theek, paid
product me mat lagana.

## Chalana (Ubuntu / WSL)

```bash
git clone https://github.com/Khelendrameena/laya-vision-playground
cd laya-vision-playground
bash run.sh
```

Phir browser me kholo: **http://localhost:8200**

- Pehli baar `run.sh` venv banayega, torch + laya-vision install
  karega (bada download, kuch minute), aur model (~800 MB)
  HuggingFace se aayega. Site ke upar status pill me progress
  dikhega — `✅ Ready · cuda` aane par Decision chalao.
- **Versions pinned hain** (`requirements.txt` me note dekho):
  latest transformers (5.23) se upstream laya-vision ka predict
  crash hota hai, isiliye official demo wala verified set
  (transformers 5.17.0 + torch 2.14.0) lagaya hai — inhe upgrade
  mat karna.
- GPU (RTX) ho to khud `cuda` chunega, warna `cpu` (CPU par ek
  predict ~2–4 second lag sakta hai).

## Presets

- **🎬 Shorts Frame Judge** — video frame kitna engaging hai (score),
  face dikh raha hai kya (noul), frame kis type ka hai (choice)
- **📦 Product Damage** — README wala example: damage level, item
  category, outdoors hai ya nahi
- **🖼 Photo Check** — photo quality score, log hain ya nahi, setting

Questions khud bhi edit/add kar sakte ho — id, type, instructions,
aur choice/score ke liye criteria (ek line = ek option).

## Bina model ke sirf site dekhna ho to (mock)

```bash
LAYA_VISION_MOCK=1 bash run.sh
```

Is mode me results nakli (deterministic fake) aate hain aur site par
🧪 MOCK badge dikhta hai — sirf UI check karne ke liye hai.

## Structure

- `backend/main.py` — FastAPI: `/api/status`, `/api/predict`, static site
- `frontend/index.html` — poori UI ek hi file me (koi build step nahi)
- Port **8200** (Shorts Generator ke 8000/3000 se takraav nahi)
