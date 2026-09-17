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
- [ ] llama.cpp OpenCL build in `build-ocl`, does Adreno 730 load at all
- [x] Models in `~/mealprep/models`: gemma-4-E4B-it-Q4_0 (4.6 GB), mmproj Q8_0, PaddleOCR-VL-1.6 + mmproj
- [ ] `llama-bench` E4B CPU: pp/tg tok/s, cpuss temp before/after
- [x] `termux-notification` works (but pops on Poco only, hence ntfy)
- [ ] Daily driver: Syncthing app, pair with Poco, share both folders. Camera app with save-folder setting (Open Camera) + home shortcut
- [ ] ntfy app on daily driver, pick topic, test `curl -d test ntfy.sh/<topic>` from Poco
- [ ] Verify sshd/syncthing/crond survive a reboot
- [ ] Poll `receipts/` from cron every minute → trigger intake job (phase 1)

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

## 1. Intake: receipt → inventory

- [ ] Receipt photo → OCR text (photo via `termux-camera-photo` or sync from phone camera folder)
- [ ] OCR text → Gemma E4B few-shot → JSON `[{name, qty, unit, category, bought}]` (constrain with JSON grammar)
- [ ] Learned mapping cache: raw receipt line → canonical item, skip LLM on hit
- [ ] Strip Pfand, discounts, totals
- [ ] Inventory store: `inventory.json`, load whole file, no DB
- [ ] Per-category default shelf life table (milk 7 d, eggs 21 d, ...) → `expires`

## 2. Suggest + notify

- [ ] Seasonal produce table for region, hardcoded
- [ ] Weather from local API, inject into prompt
- [ ] Meal history `history.json`: what was cooked, when, cuisine, protein, technique
- [ ] Prompt: inventory + expiring-soon + history + weather → 1-3 suggestions, JSON, only ingredients on hand
- [ ] Novelty rule: change one axis per suggestion (ingredient OR technique OR cuisine), never all
- [ ] Nutrition balance check across last 7 d before suggesting
- [ ] Daily notification ~17:00 with suggestions and action buttons

## 3. Consumption loop

- [ ] "Made it" button on notification → decrement ingredients, append history
- [ ] Weekly "what's gone?" notification, batch-confirm expired/used items
- [ ] NFC tag in kitchen → launches receipt capture (day) / made-it (evening)

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

- Does OpenCL on Adreno 730 work at all in Termux? Upstream lists 750+ only
- How much does E4B throttle on SD8 Gen 1 with no cooling?
- German receipt abbreviations: does E4B alone resolve "H-MILCH 3,5%" or does it need the mapping cache from day one?
