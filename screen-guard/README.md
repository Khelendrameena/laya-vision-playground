# 🛡 Screen Guard v2 — live screen blocker (NudeNet engine)

Live screen se image le kar explicit (18+) content mile to screen
block karta hai. Local chalta hai — screenshot kahin upload nahi hota.

**v2 me naya:** NudeNet ab playground ke **Safety preset ke andar
dusra engine** bhi hai (verdict dono engines se banta hai), aur ye
guard ab fast real-time hai — frame-diff skip, 0.5s scan cadence,
status pill, Esc snooze.

## Pehle ye samajh lo — engine ki limit

- **Engine NudeNet v3 hai** (ONNX, ~12 MB model, CPU par ~20–100 ms
  per frame). Sirf **nudity** pakadta hai — exposed body parts.
- **Violence / horror / gore / dark scenes iske scope me NAHI hain.**
  Aisi image par ye guard miss karega — ye NudeNet ki documented
  limit hai, threshold ki galti nahi (Laya Vision wali problem jaisi).
- Agar tumhari test image horror/dark-scene type ki thi, to is
  guard ko mat chalao — uske liye koi ready pip engine nahi hai;
  raaste hain: Laya ko labelled data par fine-tune karna, ya cloud
  moderation API (screenshots bahar jayenge — privacy tradeoff).
- License: NudeNet repo AGPL-3.0 hai (PyPI metadata MIT kehta hai) —
  personal use theek hai, paid product me lagane se pehle check karo.

## Chalana — Windows Python me (WSL me NAHI)

WSL ke andar se Windows desktop ka screenshot nahi liya ja sakta,
isiliye ye script **Windows wale Python** me chalani hai
(python.org installer, tkinter usi me aata hai):

```powershell
py -m pip install nudenet mss pillow
cd laya-vision-playground\screen-guard
py screen_guard.py
```

Band karne ke liye terminal me `Ctrl+C`, ya upar wale pill par `✕`.

## Pehle engine test karo (zaroori)

Live guard chalane se **pehle** apni dark image par engine test karo:

```powershell
py screen_guard.py --test-image "C:\path\to\image.jpg"
```

- `🔴 BLOCK` aaye to live guard use pakdega.
- `🟢 SAFE` aaye to live guard bhi miss karega — guard chalane ka
  koi fayda nahi, doosra raasta chuno.

## Kaise kaam karta hai (v2)

- Har **0.5 second** screen check hoti hai, par pehle **frame-diff**:
  screen badli hi nahi (static page, ruka video) to detection skip —
  sirf badlaav par asli NudeNet check chalta hai (512px frame par).
- **Lagatar 2 BLOCK** mile tabhi fullscreen kaala overlay aata hai
  (ek galat frame se flicker nahi hoga).
- **Lagatar 3 SAFE** frame mile to overlay khud hat jata hai.
- Upar right corner me **status pill** hamesha dikhta hai:
  🛡 SAFE (scans/skips/last ms ke saath) · ⛔ BLOCKED · 💤 SNOOZE.
- Galat block ho to **Esc** dabao — 60 second snooze (scanning
  chalti rahegi, block nahi lagega).
- Block rule: `GENITALIA / BREAST / BUTTOCKS / ANUS + EXPOSED`
  classes, score ≥ 0.50 (`--threshold` se badal sakte ho). Belly/
  feet/armpits aur face jaan-bujh kar bahar hain.
- Log: `screen_guard_log.txt` me sirf verdict + time. Screenshots
  save nahi hote — har frame ek hi temp file par overwrite hota hai.
- Options: `--interval 0.5` (scan cadence), `--width 512`,
  `--threshold 0.50`.

## Verified (15 Nov 2026)

- Is VM (kamzor shared CPU) par: NudeDetector init ~0.3s, detect
  ~20–100 ms/frame (640/512/416px — teeno par lagbhag same, model
  andar khud resize karta hai); safe image par koi false detection
  nahi. Frame-diff + verdict logic ke unit checks pass.
- Playground backend me integration test: `/api/status` me
  `nudenet: true`, Safety predict ke jawab me asli NudeNet result
  (`block: false, ms: 98` safe image par).
- Live capture/overlay **is VM par test nahi hua** — yahan koi
  screen nahi hai; pehla live run tumhare Windows PC par hoga.
