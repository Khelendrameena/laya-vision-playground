# 🛡 Screen Guard v3 — live screen blocker (NudeNet), bypass-resistant

Live screen scan karke explicit (18+) content mile to saari screens
block kar deta hai. Local chalta hai — screenshot kahin upload nahi
hota. **v3 ka pura design ek hi maksad par hai: khud se bypass
mushkil ho** — kyunki v2 ka Esc snooze hi sabse bada bypass tha.

## Bypass-resistance — kya hai, kya nahi

Hai:
- **Esc snooze NAHI, ✕ button NAHI, overlay band karne ka koi
  rasta NAHI.** Block se nikalne ka ek hi tareeka: galat page/app
  se hat jao — screen safe hote hi (lagatar 3 safe frame) overlay
  khud hat jata hai.
- **Watchdog:** ek dusra bina-window wala process guard ko zinda
  rakhta hai. Guard mara (Ctrl+C / Task Manager / crash) to ~10
  second me khud wapas chalu. Guard bhi watchdog ko dekhta hai.
- **Band karne ka ek hi rasta:** `py stop_guard.py` → poori line
  haath se type karo → **10 minute countdown** (pill par dikhta
  hai, is dauran blocking chaalu rehti hai) → tab band hoga.
  Mann badle to `py stop_guard.py --cancel`.
- Overlay **har monitor** par, hamesha sabse upar; band ho jaye
  to poll loop use khud wapas bana deta hai.

Nahi hai (sach):
- Apni machine par admin tum khud ho — **100% unbypassable kuch
  nahi hota.** Dono processes ko ek saath Task Manager se marna
  ab bhi mumkin hai. Design bypass ko *slow aur annoying* banata
  hai taaki impulse wala pal nikal jaye — Cold Turkey jaise
  professional tools bhi bilkul yahi karte hain.

## Strict mode (15 Nov shaam — "thoda bhi dark nahi chalega")

`start_guard.bat` ab **STRICT** me chalta hai:

- **Threshold 0.50 → 0.25** — NudeNet isse neeche ja hi nahi sakta
  (uska apna floor ~0.20–0.25 hai), ye sabse sakht setting hai.
- **Pehli hit par hi BLOCK** — lagatar 2 ka intezaar khatm.
- **Covered classes bhi block:** `FEMALE_BREAST_COVERED`,
  `FEMALE_GENITALIA_COVERED`, `BUTTOCKS_COVERED`, `ANUS_COVERED`,
  `BELLY_EXPOSED`, `BELLY_COVERED` — kapdon ke upar se suggestive
  dikhe to bhi block.
- **Bug fix:** purane rule me `FEMALE/MALE_BUTTOCKS_EXPOSED` aur
  `FEMALE/MALE_ANUS_EXPOSED` naam the — NudeNet v3 ke 18 labels me
  ye naam hote hi nahi (sahi: `BUTTOCKS_EXPOSED`, `ANUS_EXPOSED`),
  isiliye buttocks wali detection kabhi gini hi nahi jaati thi.
- **Keemat (pehle se jaan lo):** gym / dance / sports / beach jaisi
  normal skin-heavy videos bhi block ho sakti hain — strict ka
  matlab hi ye hai. Normal mode chahiye to `py screen_guard.py`
  (bina `--strict`) chalao.
- `--test-image` ab **saari detections** score ke saath dikhata hai,
  sirf hits nahi — isiliye apni dark image par pehle ye chalao:
  `py screen_guard.py --strict --test-image "C:\path\image.jpg"`.
  Agar usme **koi detection hi nahi** aaye to samajh lo content
  nudity wala hai hi nahi — phir horror/violence ka alag engine
  lagega, strict NudeNet se wo kabhi block nahi hoga.

## Engine ki limit (ye bhi sach)

- **NudeNet v3** (ONNX, ~12 MB, CPU par ~20–100 ms/frame) — sirf
  **nudity** pakadta hai. **Violence / horror / gore iske scope
  me NAHI hain** — aisi content par ye miss karega.
- License: NudeNet repo AGPL-3.0 — personal use theek, paid
  product me lagane se pehle check karo.

## Chalana — Windows Python me (WSL me NAHI)

WSL se Windows desktop ka screenshot nahi liya ja sakta — script
WSL me chalane par khud ruk kar yahi warning deti hai.

```powershell
py -m pip install nudenet mss pillow
cd laya-vision-playground\screen-guard
py screen_guard.py --test-image "C:\path\to\image.jpg"   # pehle test
start_guard.bat                                          # phir live
```

- `start_guard.bat` double-click karne se guard **bina terminal
  ke** background me chalega (pythonw) — band karne ko terminal
  hi nahi milega, sirf stop_guard wala rasta rahega.
- Terminal se chalana ho to `py screen_guard.py` — par yaad rahe,
  Ctrl+C se mara to watchdog wapas chalu kar dega.
- Upar right corner ka **status pill** hamesha dikhega:
  🛡 SAFE (scans/skip/last ms) · ⛔ BLOCKED · ⏳ countdown.
- Login par khud chalu karna ho to `start_guard.bat` ka shortcut
  Startup folder me daal do (`Win+R` → `shell:startup`).

## Kaise kaam karta hai

- Har **0.5s** screen check; pehle **frame-diff** — screen badli
  hi nahi to detection skip, sirf badlaav par asli check (512px).
- **Lagatar 2 BLOCK** → saari screens par overlay. **Lagatar 3
  SAFE** → overlay khud hata.
- Block rule: `GENITALIA / BREAST / BUTTOCKS / ANUS + EXPOSED`,
  score ≥ 0.50. Belly/feet/armpits/face jaan-bujh kar bahar.
  **Strict (`--strict`, ab default):** threshold 0.25, covered +
  belly classes bhi, pehli hit par BLOCK.
- Guard ↔ watchdog **heartbeat files** se ek dusre ko dekhte
  hain; stop ka sanket `stop_request.txt` / `stop_done.txt`
  files se jaata hai (sab isi folder me, sab gitignore me).
- Log: `screen_guard_log.txt` — sirf verdict + time.

## Verified (15 Nov 2026)

- Is VM par: NudeNet detect ~20–100 ms, frame-diff/verdict unit
  checks pass, stop-flow ka simulation pass (sahi line → request
  file → countdown → proper stop; galat line → reject; --cancel
  kaam karta hai — ek argv bug test me pakda gaya aur fix hua).
- Live capture/overlay/watchdog ka pehla asal test **tumhare
  Windows PC** par hoga — is VM par screen hi nahi hai.
