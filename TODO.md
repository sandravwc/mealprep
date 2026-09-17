# TODO

Order = priority. Each phase ships something usable before the next starts.

## 0. Server bring-up (Poco F5 Pro, Termux)

- [ ] Termux + termux-api + termux-services, sshd, keep-alive (wakelock, battery optimization off)
- [ ] Verify Android background killer does not kill sshd/cron over 48 h
- [ ] Build llama.cpp in Termux, CPU first. Try `-DGGML_OPENCL=ON` (Adreno 730 unverified upstream, cheap to test, fall back to CPU)
- [ ] Gemma 4 E4B Q4_K_M + mmproj via `llama-server`, measure tok/s and throttling after 5 min. Expect ~5-8 tok/s (Gen 3 does 12-20)
- [ ] Cron job fires `termux-notification` on schedule (proves push path works)
- [ ] Syncthing on server + daily-driver phone, shared `receipts/` folder. Server = no camera, stays in place
- [ ] inotify/poll `receipts/` → trigger intake job

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
