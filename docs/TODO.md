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

- Stock in tiers: DRINGEND / BALD / rest / NICHT verwenden. Season from month. Weather from Open-Meteo when `WEATHER_PLACE` is set, skipped silently otherwise. Profile tags + text. Liked, disliked, cooked, skipped last 14 d
- 2 dinners as JSON with `uses` naming stock items. One of the two changes exactly one axis
- First run picked Lachs (expiring next day) and "neu: Curry-Gewürz". Rule works
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

`server/fridge.py`, spawned by `POST /upload?kind=fridge`, cron every 5 min for Syncthing drops into `fridge/`.

- [x] Second camera button 🧊 → `fridge/` → E4B "list every visible food item" → `[{name, category}]`
- [x] Diff against stock: seen but not in stock → add proposal. Perishable in stock but unseen on 2 consecutive photos → remove proposal. Substring name match, no fuzzy lib
- [x] Proposals in PWA with ✓ / ✕. Nothing touches stock without a tap. Accept-add uses category shelf days, qty 1 Stück
- [ ] Score recall on 10 real fridge photos before trusting it. No real photo tested yet
- [ ] E4B recall on real photos is poor: top shelf 2 of ~8 readable products, pantry only generic groups. Prompt tightened, untested
- [x] Qwen3-VL-2B tested on the 3 photos: with product examples in the prompt it parrots the examples, without them it loops one word ("Schnaps" x 200) until max_tokens. Rejected. Files stay in `models/` for a later retry with repeat penalty
- [x] Prompt examples removed for E4B too, same parroting risk
- [x] Tiling tested (2x2, 10 % overlap) on shelf + door photos. Tiles read 2 extra real labels per photo (Sahnig, Brie / Werder, Deutsche Butter) and add 3-4 invented items per photo (Red Bull, Nüsse, Kleine blaue Dose), at 4x the time (~7 min per photo). Not worth it: every invented item is a proposal you must reject. Stays full-photo
- [ ] Recall ceiling with E4B on cluttered shelves is ~50 %, names generic (Käse, Brot). Prompt in German with no examples is the best variant found. Treat proposals as reminders, not truth
- [ ] Next real lever: bigger VLM in the same 5 GB budget, one at a time. Qwen3-VL-8B Q4_K_M (~5 GB) is the OCR-strong candidate. Qwen3-VL-2B looped, 8B may not. Gemma 4 12B does not fit
- [ ] Photo hygiene beats model tuning: one shelf per photo, labels facing the camera, no stickers in frame (the sticker table gave "Bon Jovi" and "Placebo")
- Incident 2026-09-17, twice: Android killed the Termux app process, `dumpsys activity exit-info com.termux` says LOW_MEMORY, an earlier one says OneKeyClean (HyperOS cleaner). Resident E4B (5 GB) + Shoko proot inside one app process is what HyperOS sees. Fix: no resident llama service, `intake.llm()` starts the server per job and stops it after. Baseline went 8.2 → 3.4 GB used. Recovery without touching the phone: `adb shell am start -n com.termux/.HomeActivity`, profile.d starts the services
- [ ] HyperOS side, needs taps: lock Termux in recents (so clear-all skips it), Battery saver → No restrictions. `dumpsys deviceidle whitelist +com.termux` and RUN_IN_BACKGROUND allow are already set via adb

### 4b. NPU / GPU on 8 Gen 1

SoC is SM8475 = 8+ Gen 1 (TSMC), not 8 Gen 1. Same Hexagon v69, same Adreno 730. Termux is `untrusted_app`, vendor libs are out of reach. Three routes:

- [x] GPU via adb shell WORKS (2026-09-17). Recipe: wireless debugging paired, from Termux copy `build-ocl/bin/*` + every NEEDED lib from `$PREFIX/lib` (libc++_shared, libssl.so.3, libcrypto.so.3) + model to `/sdcard/llm`, `adb shell cp` to `/data/local/tmp/llm`, DELETE the copied `libOpenCL.so` (Termux ICD loader shadows the vendor driver), run with `LD_LIBRARY_PATH=/data/local/tmp/llm:/vendor/lib64 -ngl 99`. Qwen3-VL-2B Q8_0 under CPU load: GPU pp 62 / tg 13.9, CPU pp 88 / tg 11.5 tok/s
- [ ] Fair bench: idle CPU, Q4_0 file (Adreno-tuned path), same binary CPU vs GPU
- [ ] Decide: two processes (vision on GPU as shell uid, E4B text on CPU in Termux) only if the fair bench and the 8 GB budget allow. Wireless debugging resets on reboot, so the GPU side needs a tap after every reboot and the CPU path must always work alone
- [ ] Hexagon via same route: upstream HTP libs are v73+, Gen 1 is v69. Check zhouwg/ggml-hexagon fork (claims Gen 1) once source is public. Likely no
- [ ] LiteRT + QNN delegate lists SM8450. Needs an APK: minimal Android app hosting LiteRT-LM (Gemma E2B `.litertlm` exists for Qualcomm) or a YOLO QNN export, exposing HTTP on localhost for Termux. Only worth it if 4a is too slow on CPU
- Memory reality: 8 GB physical + 4 GB swap, not 12. E4B resident = 5 GB. Two models at once killed Termux once already
- Reality check: CPU does a receipt in 90 s, a fridge photo similar, suggestions in 90 s. Nothing here needs to be faster for a cron loop. NPU is curiosity, not need

## 5. HTTPS + web push, drop ntfy

Plain HTTP cannot install a PWA or receive web push. Need a trusted cert on the LAN.

- [ ] Tailscale: `pkg install tailscale` in Termux (userspace networking), `tailscale up`, `tailscale cert` / `tailscale serve --bg 8090` → `https://poco.<tailnet>.ts.net`. Daily driver: Tailscale app. Login on Poco is an auth URL the user opens once
- [ ] Service worker + manifest icons → real standalone install
- [ ] Web push: VAPID keys, subscription stored in `data/push.json`, `pywebpush` (`pkg install python-cryptography` first). `notify()` in intake.py sends web push, ntfy stays as fallback until push proves reliable through Android doze
- [ ] Action buttons in the push (gekocht / weg) via service worker `notificationclick`
- [ ] Then remove ntfy

## Later / maybe never

- Voice input on unpack (whisper.cpp)
- SQLite when history queries outgrow in-memory JSON
- postmarketOS instead of Termux if marble support lands
- Barcode scan → OpenFoodFacts nutrition. Receipt path covers intake, this only adds macros
