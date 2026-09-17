# TODO

Order = priority. Each phase ships something usable before the next starts.
Live since 2026-09-17 on a Poco F5 Pro (12 GB), Termux, CPU-only Gemma 4 E4B.

## Use pattern

Poco = headless box anywhere on LAN, never touched. Daily driver = only UI, no custom app.
1. Home-screen shortcut → PWA → camera button → receipt photo → upload. One tap + shutter.
2. Poco reads it, files items with category and expiry, pushes "N items added" via ntfy.
3. 17:00: push "Heute kochen?" with two dinners from stock, soonest-expiring first.
4. Tap "gekocht" in the PWA: used items leave stock, recipe enters history. 👍/👎 teaches the profile.

## 0. Server bring-up — done

- Termux sshd, Termux:Boot wake-lock, runit via `~/.termux/boot/10-services.sh`, crond, syncthing
- llama.cpp CPU build. E4B Q4_0: 8 thr pp 24 / tg 4.9 tok/s, 4 thr pp 13 / tg 6.7. Battery 39→40 °C
- Models: gemma-4-E4B-it-Q4_0 (4.6 GB) + mmproj Q8_0. PaddleOCR-VL 1.6 downloaded, unused
- Vision via `llama-server --jinja` + `enable_thinking=false`. Without it Gemma thinks until max_tokens
- ntfy.sh topic in `~/mealprep/.env`, never in repo
- Dead: OpenCL. Android linker namespace blocks `/vendor/lib64/libOpenCL.so` from Termux, `opencl-vendor-driver` shim exports nothing usable
- Dead: Hexagon. llama.cpp backend ships HTP v73+ only (8 Gen 2+), Gen 1 is v69. LiteRT+QNN lists SM8450 but only inside an APK
- [ ] Reboot Poco once, verify sshd/syncthing/crond/llama/mealprep come back

## 1. Intake — done

`server/intake.py`, spawned by `POST /upload`, plus cron every 5 min for Syncthing drops. `flock` serialises.

- Photo → E4B → `[{raw, name, qty, unit, category}]`. No OCR stage, no grammar, JSON has been clean so far
- Prompt tuned on real REWE photos: expansions work ("JOGH. GRIE. ART." → Joghurt griechischer Art), Kassenkarton skipped
- `data/aliases.json`: raw line or name → canonical, `""` drops. Seeded with bag, straws, Kassenkarton
- Non-receipt photo → 0 items, recorded, no retry, push shows what the model saw
- Categories `[shelf, grace]` in `server/config.py`, override `data/config.json`, editable in PWA
- Status ok / soon / expired (past date, still fine) / bad (past grace)
- Fixed: lock handle was garbage-collected, cron + upload ran the same file twice → duplicates and double pushes
- [ ] Blurry input misreads ("SPREESHAHNE"). Real camera photos, not screenshots, then judge
- [ ] Quantity is almost always 1 Packung. Fine until partial decrement matters

## 2. Suggest — done

`server/suggest.py`, cron 17:00. Text-only prompt, ~90 s when the LLM is idle.

- Stock in tiers: DRINGEND / BALD / rest / NICHT verwenden. Season from month. Profile tags + text. Liked, disliked, cooked, skipped last 14 d
- 2 dinners as JSON with `uses` naming stock items. One of the two changes exactly one axis
- First run picked Lachs (expiring next day) and "neu: Curry-Gewürz". Rule works
- [ ] Weather. open-meteo one request, when missed
- [ ] ntfy action buttons on the push itself. Now: open PWA, tap gekocht

## 3. Consumption + PWA — done

`server/app.py` stdlib http.server :8090, `server/index.html` vanilla JS.

- Offen (unmade, last 2 d, gekocht button) / Gekocht (date, 👍👎, last 7 d + ältere) / Vorrat (tiers, weg) / Bons (per day, tap for photo)
- ☰: taste toggles, free text, learned likes/dislikes, tag editor, category table. `data/profile.json`, `data/config.json`
- Camera button fixed at bottom
- `server/janitor.py` cron 16:50: dedupe stock, suggestions, receipts, drop alias-"" junk. Never removes food. Pushes "entsorgen?" for items past grace
- [ ] Partial decrement (2 of 10 eggs). Now all-or-nothing
- [ ] Add-to-home-screen is a bookmark on plain HTTP. Tailscale HTTPS for standalone + web push, then drop ntfy

## 4. Image recognition + NPU

### 4a. Fridge / pantry photo → stock diff

- [ ] Second camera button "Kühlschrank" → `POST /upload?kind=fridge` → `fridge/` (Syncthing folder exists)
- [ ] E4B: "list every food item visible" → JSON names. Score recall on 10 real fridge photos before trusting it
- [ ] Diff against stock: seen but not in stock → propose add; in stock (produce/dairy/meat) but not seen twice in a row → propose remove
- [ ] Proposals land in PWA as a checklist, nothing changes stock without a tap. Occlusion and drawers make auto-apply wrong
- [ ] Qwen3-VL-2B as second opinion if E4B recall is poor

### 4b. NPU / GPU on 8 Gen 1

Termux is `untrusted_app`, vendor libs are out of reach. Three routes, in order of effort:

- [ ] adb self-connect: `pkg install android-tools`, wireless debugging, pair once, `adb shell` = shell uid with vendor namespace. Push `build-ocl` to `/data/local/tmp`, `LD_LIBRARY_PATH=/vendor/lib64` llama-bench. This is how upstream tests Adreno. Catch: wireless debugging is off after reboot, needs a tap
- [ ] Hexagon via same route: upstream HTP libs are v73+, Gen 1 is v69. Check zhouwg/ggml-hexagon fork (claims Gen 1) once source is public. Likely no
- [ ] LiteRT + QNN delegate lists SM8450. Needs an APK: minimal Android app hosting LiteRT-LM (Gemma E2B `.litertlm` exists for Qualcomm) or a YOLO QNN export, exposing HTTP on localhost for Termux. Only worth it if 4a is too slow on CPU
- Reality check: CPU does a receipt in 90 s, a fridge photo similar, suggestions in 90 s. Nothing here needs to be faster for a cron loop. NPU is curiosity, not need

## Later / maybe never

- Voice input on unpack (whisper.cpp)
- SQLite when history queries outgrow in-memory JSON
- postmarketOS instead of Termux if marble support lands
- Barcode scan → OpenFoodFacts nutrition. Receipt path covers intake, this only adds macros
