# TODO

Order = priority. Each phase ships something usable before the next starts.

## 0. Server bring-up (Poco F5 Pro, Termux)

- [ ] Termux + termux-api + termux-services, sshd, keep-alive (wakelock, battery optimization off)
- [ ] Verify Android background killer does not kill sshd/cron over 48 h
- [ ] `ollama pull gemma4:e4b` (Q4_K_M ~3 GB), measure tokens/s and thermal throttling after 5 min
- [ ] Decide OCR: PaddleOCR vs Tesseract on German receipts, one sample each from REWE/Edeka/Aldi/Lidl
- [ ] Cron job fires `termux-notification` on schedule (proves push path works)

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
- postmarketOS on marble instead of Termux if it gets stable

## Open questions

- Receipt photo transport: same phone (server = camera) or separate daily-driver phone syncing to server?
- Is 8 GB enough for E4B + PaddleOCR resident, or load/unload per job?
- How much does E4B throttle on SD8 Gen 1 with no cooling?
