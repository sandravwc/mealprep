# TODO

Order = priority. Each phase ships something usable before the next starts.

## Use pattern (decided 2026-09-17)

Poco = headless box anywhere on LAN, never touched. Daily driver = only UI, no custom app.
1. Home-screen shortcut / NFC tag → camera app saving into a Syncthing-shared folder. One tap + shutter.
2. Poco picks up photo, runs model, pushes result to daily driver via ntfy (ntfy.sh topic for v1, self-host later).
3. ntfy action buttons "made it" / "skip" → HTTP back to Poco → inventory update.
4. Fridge photo = same path, second folder.

## 0. Server bring-up (Poco F5 Pro, Termux)

Hardware reality: 12 GB variant (11 GB usable), Android 15, Termux sshd already up for days.

- [x] Termux + termux-api + termux-services, sshd, Termux:Boot wake-lock. Already there
- [x] `~/.termux/boot/10-services.sh` starts runsvdir so services survive reboot
- [x] crond service enabled
- [x] syncthing service enabled, GUI :8384, folders `mealprep-receipts` + `mealprep-fridge`. Device ID in `docs/server.md`
- [x] llama.cpp CPU build: `~/mealprep/llama.cpp/build-cpu/bin/{llama-server,llama-bench,llama-mtmd-cli}`
- [x] llama.cpp OpenCL build in `build-ocl`. Builds, but no platform: Android linker namespace blocks `/vendor/lib64/libOpenCL.so`, and Termux `opencl-vendor-driver` copy loads with no usable exports. Adreno 730 GPU = dead from Termux. CPU only
- [x] Models in `~/mealprep/models`: gemma-4-E4B-it-Q4_0 (4.6 GB), mmproj Q8_0, PaddleOCR-VL-1.6 + mmproj
- [x] `llama-bench` E4B Q4_0 CPU, pp512/tg128: 4 thr = 12.8 / 6.7 tok/s, 8 thr = 24.4 / 4.9 tok/s. Battery temp 39→40 °C. Use 8 thr for image jobs (pp dominates)
- [x] `termux-notification` works (but pops on Poco only, hence ntfy)
- [x] Vision smoke test via `llama-server --jinja` + `chat_template_kwargs.enable_thinking=false`: synthetic REWE receipt → 7/7 items as JSON. 189 prompt tok @ 15 tok/s, 320 gen tok @ 4.1 tok/s, 90 s wall. Without `enable_thinking=false` it burns the whole budget thinking
- [x] ntfy.sh topic generated, stored in `~/mealprep/.env` on Poco (not in repo). Test push sent
- [ ] Daily driver: Syncthing app, pair with Poco, share both folders. Camera app with save-folder setting (Open Camera) + home shortcut
- [ ] ntfy app on daily driver, subscribe to topic from `.env`, confirm test push arrived
- [ ] Reboot Poco once, verify sshd/syncthing/crond come back (Termux:Boot)
- [x] Cron every 5 min runs `intake.py` for files Syncthing dropped

## 0b. Model eval (before writing intake code)

Test set: 5 receipts each REWE/Edeka/Aldi/Lidl, hand-labelled items. Score = exact item+qty match.

- [ ] A: Gemma 4 E4B vision → JSON directly. One model for receipts, fridge photos, suggestions. Reported 91% field accuracy on English receipts. Try first.
- [ ] B: PaddleOCR-VL 1.6 (0.9B, GGUF, llama.cpp) → text → E4B normalizes. Top OmniDocBench score, ~1 GB. Use if A < 90%
- [ ] C: Keyven/german-ocr-2b (Qwen3-VL-2B finetune, German docs, 1.4 GB). Backup for B
- [ ] Fridge photo: E4B "list every food item visible" vs Qwen3-VL-2B. Score recall on 10 fridge photos. No YOLO: fixed 30-class fridge models useless for open inventory, onnxruntime has no Termux wheels
- [ ] Memory: E4B + mmproj ~4 GB resident. Run OCR model and E4B sequentially, not both loaded

NPU verdict (2026-09): **not usable from Termux on 8 Gen 1.**
- llama.cpp Hexagon backend ships HTP v73/v75/v79/v81 only = 8 Gen 2 and up. Gen 1 is v69
- Even on 8 Elite, unrooted Termux gave garbled output, issue closed not-planned
- LiteRT + Qualcomm QNN delegate does list SM8450, but only as in-app Android delegate. Needs an APK, not a shell
- Only NPU path = write a tiny Android app that hosts LiteRT+QNN and exposes HTTP. Parked under Later

## 1. Intake: receipt → inventory (shipped 2026-09-17)

PWA at http://poco:8090 (`server/app.py`), llama-server as runit service, `server/intake.py` via upload thread + cron every 5 min for Syncthing drops.

- [x] Camera button in PWA → POST /upload → intake. Syncthing `receipts/` folder also picked up by cron
- [x] Photo → Gemma E4B vision → JSON `{name, qty, unit, category}`, thinking off. No OCR stage, no grammar (JSON came clean every run so far)
- [x] `data/aliases.json` post-fix map (lowercase model name → canonical). Hand-edit when the model keeps a bad abbreviation
- [x] Pfand/totals skipped by prompt. Synthetic test: Basilikum got qty 0.25 from the Pfand line next to it. Watch on real receipts
- [x] `data/inventory.json` flat list, `data/receipts.json` log with raw model output
- [x] Shelf-life table in `intake.py` → `expires`
- [x] Inventory page sorted by expiry, "weg" button removes item (early phase 3)
- [x] ntfy push "N items added" with click → PWA
- [ ] Real receipts from REWE/Edeka/Aldi/Lidl, score, tune prompt + aliases (phase 0b)
- [ ] Add-to-home-screen: plain HTTP gives a bookmark shortcut, not standalone. Fine for now. Tailscale HTTPS later if it bugs you

## 2. Suggest + notify (shipped 2026-09-17)

`server/suggest.py`, cron 17:00. Text-only prompt, ~90 s when LLM idle.

- [x] Season from month, in prompt. Produce table skipped, model knows seasons
- [ ] Weather. Skipped for v1, add open-meteo one-liner when you miss it
- [x] History = `data/suggestions.json` with `made` flag. Cooked + skipped last 14 d go into the prompt
- [x] Prompt: stock sorted by expiry + history + season → 2 dinners, JSON, `uses` lists stock names
- [x] Novelty rule in prompt: exactly one of two changes one axis. First run: "neu: Curry-Gewürz". Works
- [x] Nutrition balance: one sentence in prompt. No scoring. Judge after a month
- [x] ntfy push "Heute kochen?" with both titles, click opens PWA
- [ ] ntfy action buttons on the push itself. Now: open PWA, tap "gekocht"

## 3. Consumption loop

- [x] "gekocht" button in PWA → `made=true`, removes `uses` items from stock (whole item, no partial qty)
- [x] "weg" button per stock item

## 3. Consumption loop

- [ ] Partial decrement (used 2 of 10 eggs). Now all-or-nothing
- [ ] Weekly "what's gone?" push listing expired items, batch-confirm
- [ ] NFC tag / home-screen shortcut → PWA

## 4. Secondary intake

- [ ] Barcode scan → OpenFoodFacts lookup (name, category, macros)
- [ ] Enrich receipt items with OpenFoodFacts nutrition where matched

## Later / maybe never

- Voice input on unpack (whisper.cpp)
- Fridge photo → VLM diff (occlusion makes this unreliable)
- SQLite when history queries outgrow in-memory JSON
- NPU: minimal Android APK hosting LiteRT + QNN delegate (Gemma E2B `.litertlm` exists, YOLO QNN export exists), HTTP to Termux. Only if CPU speed becomes the bottleneck
- postmarketOS on marble instead of Termux if it gets stable

## Open questions

- How much does E4B throttle on SD8 Gen 1 with no cooling?
- German receipt abbreviations: E4B kept "Ba Banane" literal and swapped one price column on the synthetic test. Prompt few-shot + mapping cache needed from day one
- Does OpenCL on Adreno 730 work at all in Termux? No (see phase 0). Revisit only via an Android APK
