/

mhm a ai-system (prolly local model, maybe gemma4) based on creating grocery inventories to proactively push notifications with receipts what to eat. it evaluates past user choices to base its suggetions with focus on nutricion and obviously it will challenge the users tastes. it will also consider season and weather.
probably will need to evaluate some sort of visual feed to create grocery list for inventory. idk maybe sqlite or valkey backend but i dont really have full intention to absolutely need database. will probably work just fine with flat text

Interesting project. A few thoughts on the architecture before you commit to anything.

On the "no database" instinct: for a personal single-user system, flat files genuinely are fine, and I'd push back on anyone reflexively reaching for SQLite. But think about your access patterns. You'll want to query "what's expiring in the next 3 days", "what proteins have I eaten in the last 2 weeks" (for the variety/challenge logic), and "what's currently in stock". That's three different indices over the same data. Flat text works if you load everything into memory on each run — which for a grocery inventory is maybe a few hundred items, so totally fine. JSON or TOML per-entity, parsed on startup. Valkey is overkill unless you want pub/sub for the notification layer, and even then a cron + a script is simpler. SQLite becomes worth it the moment you want history/analytics without writing your own aggregation.

On the vision part: this is the hard problem, not the LLM part. Options, roughly in order of effort:

    Receipt OCR (Tesseract or PaddleOCR) + a small LLM pass to normalize line items. Works well because receipts are structured. This is probably your highest-leverage input.
    Fridge/pantry photo → object detection. Much harder. YOLO-world or a VLM like Qwen2.5-VL or moondream can do it, but occlusion and packaging kill accuracy. I'd treat this as a "nice to have" phase 2.
    Barcode scanning on intake. Trivial, very accurate, but requires you to actually scan things.

On the model choice: Gemma 3 is the current Gemma line (there's no Gemma 4 as of now that I'm aware of — you may be thinking of Gemma 3, or confusing it with another release). For a suggestion engine that reasons over ~50-200 inventory items plus history plus weather, a 4B–12B model is plenty. Qwen 2.5 7B, Gemma 3 4B/12B, or Llama 3.1 8B all handle this cleanly. The nutrition reasoning doesn't need frontier capability — it needs good instruction following and the ability to not hallucinate ingredients you don't have. Constrain it with structured output (JSON schema via llama.cpp grammars or outlines).

On the "challenge the user's tastes" part — this is the most interesting design question and the easiest to get wrong. If the model just randomly suggests unfamiliar things, users ignore it. The useful framing is: track a taste vector (cuisines, ingredients, techniques, textures) and deliberately suggest adjacent-but-novel items — one axis of novelty at a time. Familiar ingredient, new technique. Or known technique, unfamiliar spice. That's a much better UX than "you eat a lot of pasta, try Ethiopian injera tonight".

Seasonality/weather is straightforward: pull from a local weather API, hardcode a seasonal produce table for your region, inject both into the prompt context. Don't overthink it.

What's your deployment target — always-on homelab box, or something that wakes up on a schedule?

https://deepmind.google/models/gemma/gemma-4/

you can access the web cant you? gemma4 blows many bigger models completly away
Fetched: Gemma 4

You're right, my bad — Gemma 4 is real and I was working from stale knowledge. The lineup is E2B/E4B (edge/mobile), plus 26B (which is an A4B mixture-of-experts — 26B total params, ~4B active) and a dense 31B. The benchmarks are genuinely impressive: Gemma 4 31B IT Thinking hits 89.2% on AIME 2026, 84.3% on GPQA Diamond, and 80.0% on LiveCodeBench v6,
deepmind
which is frontier-ish territory for an open model you can run locally.

For your project specifically, the interesting pick is the 26B A4B. MoE means you pay 26B in VRAM but only activate ~4B per token, so inference is fast on a single consumer GPU while you still get near-31B quality. For a background notification service that wakes up a few times a day to reason over inventory + history + weather, that's ideal — you don't care about sustained throughput, you care about quality per wakeup and low idle cost.

The E4B is worth considering too if you want this to run on something small like a Jetson or even a Pi 5. It supports audio and vision natively and can run completely offline on edge devices,
deepmind
which matters for your "visual feed → grocery list" idea — you could do the pantry photo → item extraction step on-device without shipping images anywhere. The quality tradeoff is real though (E4B thinking is 52% on LiveCodeBench vs 80% for 31B), and for the reasoning-heavy "challenge my tastes with nutritional justification" part you'd feel it.

Practical suggestion: split the pipeline by model size. E4B handles vision (receipt OCR, pantry photos) and structured extraction — cheap, fast, runs anywhere. 26B A4B handles the meal reasoning and notification generation on a schedule. Both are Gemma 4 so you keep prompt/format consistency, and Ollama already has them (ollama pull gemma4:26b-a4b and gemma4:e4b per the download links on that page).

Does your target hardware have a GPU, or are you aiming for CPU/edge only? That changes which of the two tiers is actually viable.

Both are genuinely strong choices and yeah, the price/perf on Poco is absurd for what you get. Let me break down the tradeoff because it actually matters for your use case.

F5 Pro (SD8 Gen 1, 8 GB) is more than enough for E2B and will run E4B with some patience. The SD8 Gen 1 has the Hexagon NPU which MediaPipe/AI Edge can target, and 8 GB RAM means you can comfortably load a Q4_K_M quant of E4B (~3 GB) plus your Python service, OCR pipeline, and SQLite with headroom. The catch with Gen 1 specifically is that it's the hot one — Samsung's 4nm process had known thermal issues, and the F5 Pro has no vapor chamber worth mentioning. For bursty inference 3-4x a day, totally fine. If you start doing continuous vision processing, it'll throttle.

F8 Pro (SD8 Elite, 12 GB) is a different league. The Elite's Hexagon NPU is roughly 2-3x faster than Gen 1 on INT8 workloads, and more importantly it's built on TSMC N3E so thermals are dramatically better. 12 GB RAM means E4B fits at higher precision (Q5 or Q6) with zero stress, and you could even experiment with the 26B A4B at aggressive quantization — MoE's active-param story means ~4B active fits in memory budget, though the full 26B weights at Q4 would be ~14 GB which exceeds your RAM. So 26B is borderline-not-really even on the F8 Pro unless you want to swap to storage, which on a phone is a bad idea.

Here's the thing though: for your actual workload, the F5 Pro is probably enough. You're doing scheduled inference, not interactive chat. The difference between a notification generated in 8 seconds vs 3 seconds doesn't matter when it fires at 6pm regardless. The 500 EUR delta buys you headroom you won't use, unless you later decide you want the vision pipeline to be real-time (live camera feed of the fridge) rather than "snap a photo when you unpack groceries".

What the F8 Pro actually buys you that matters:

    Longer usable lifespan as a 24/7 device (better thermals = less battery degradation, N3E SoC runs cooler at idle)
    Headroom to upgrade to larger models as Gemma 5/6 comes out without rebuying hardware
    The NPU is genuinely future-proofed for on-device ML in a way Gen 1 isn't

What it doesn't buy you:

    Meaningful latency improvement for a cron-driven notification service
    Ability to run 26B tier (still out of reach)

My actual recommendation: if you have an F5 Pro lying around already, use it — it's completely sufficient for E2B/E4B workloads and you'll learn whether the project is worth investing in before spending anything. If you're buying fresh and plan to run this for 3+ years, the F8 Pro is worth it purely for the thermal/longevity story on a device that'll be pegged at low-but-constant load.

One more thing worth flagging for either: check postmarketOS device support before buying. The F5 Pro (marble/marbleprc) has community work but isn't mainline-supported last I checked, and the F8 Pro is too new to have any meaningful support. If you go Poco and want proper Linux, you may be stuck with Termux + termux-services for the foreseeable future, which works but means you're fighting Android's background killer instead of using systemd timers. Worth knowing upfront.

Are you leaning toward keeping it on Android with Termux, or is "buy new phone and put postmarketOS on it eventually" part of the plan?

grocery inventory has to be as seamless as possible becsuse using will be otherwise a chore so itll be harder to form habits. what are my options

Correct framing — friction kills this project faster than any technical problem. Let me lay out the options by how much effort they demand per grocery trip, roughly from most to least friction.

Manual text entry (highest friction, don't do this) — typing items into a form. Dead on arrival. You'll do it for a week and stop. Only mentioning it so we can explicitly reject it.

Voice input on unpack. Talk to the phone while putting groceries away: "two liters milk, 500g ground beef, basil, six eggs". Whisper or whisper.cpp runs fine on your Poco, then a small LLM pass normalizes it into structured inventory entries. Friction is low because you're already handling items, and talking is parallelizable with the physical task. Failure mode: you forget to do it, or you're not alone in the kitchen and feel weird talking to your phone. Good fallback layer, not a primary input.

Barcode scanning on unpack. Point phone camera at each item, beep, done. OpenFoodFacts has a massive free database (2M+ products, strong in Europe, particularly Germany) that maps EAN/UPC to product name, category, nutrition data, and often weight. This is the killer feature for nutrition reasoning specifically — you get real macros per item for free, which your suggestion engine desperately wants. Friction is medium: you still handle each item, but the scan is ~1 second and the feedback is instant. Failure modes: unpackaged produce (no barcode), store-brand items not in the DB, and the psychological hurdle of "pick up phone, open app" every time. The last one is solvable with an NFC tag on the fridge that auto-launches the scanner.

Receipt OCR (lowest friction, highest payoff). You already get a receipt. Photograph it once when you get home, done. One action covers 20-40 items. This is almost certainly your primary input path. The hard part is that German supermarket receipts are hostile to parsing — REWE, Edeka, Aldi, Lidl all use cryptic abbreviations ("H-MILCH 3,5%", "BA BANANE", "RZ TOMATEN"), prices are mixed with deposits (Pfand) and discounts, and the layout varies. But this is exactly what a small LLM is good at: give Gemma the raw OCR text plus a few-shot prompt with examples from your specific chains, and it'll produce clean structured output. You build up a learned mapping table over time so recurring items get resolved instantly without an LLM call. PaddleOCR handles German receipts better than Tesseract in my experience, and runs on the phone's NPU.

Bank transaction feed (zero friction, zero detail). Your bank knows you spent 47 EUR at REWE on Tuesday. Useless for inventory because it doesn't tell you what you bought. Mentioning only to rule out.

Pantry/fridge photo (ambient friction, unreliable). Periodically photograph the fridge interior, VLM extracts visible items, diff against last known state. Sounds elegant, fails in practice: occlusion, packaging obscuring contents, things hidden in drawers, the VLM hallucinating items that aren't there. Treat as phase 3 at earliest, or as a passive "what's still here" check rather than primary intake.

The consumption side is the other half of the problem, and people always forget it. Intake tracking is pointless if you don't also track what leaves the pantry. Options:

    Infer from meals cooked. When the system suggests a recipe and you mark "I made this", it decrements ingredients automatically. Zero friction, but requires the user to confirm meals, which is its own habit.
    Expiration-based auto-decrement. Assume items are consumed or expired by a certain date based on category (milk: 7 days after purchase, eggs: 21 days, etc.). Lossy but requires no input.
    Explicit "used up" button. A single tap when you finish something. Low friction if the UI is a persistent notification or widget, not a buried app screen.

My recommended stack for your situation:

    Primary: receipt photo on arrival home → OCR → LLM normalization → inventory insert. One action, covers 90% of intake. Build a learned mapping cache so REWE's "H-MILCH 3,5% 1L" always resolves to the same canonical entry without re-asking the LLM.
    Secondary: barcode scan for things without receipts (gifts, farmers market, refills) and for enriching items with OpenFoodFacts nutrition data when the receipt-OCR path doesn't have a match.
    Consumption: recipe-confirmation decrement (tap "I made this" on the suggestion notification) + a weekly "what's gone?" prompt that shows you items likely expired and lets you batch-confirm.
    Skip entirely for v1: voice input, pantry photos, manual entry. Add later if the core loop is working.

The habit-formation angle matters here: the notification that says "you have X, Y, Z — cook this" is itself the trigger for the consumption tracking loop, because marking "made it" is the natural response. That's the closed loop, and it's what makes the whole thing sustainable vs. yet another tracking app that dies after three weeks.

One concrete ergonomic tip: put an NFC tag on the inside of a kitchen cabinet door. Tap phone on it → launches the receipt scanner directly, no app fumbling. Same tag, different launch context (time of day), could launch the "mark meal as cooked" flow in the evening. Removing the "find the app, open it" friction is worth more than any model quality improvement.
Write a message…


Claude is AI and can make mistakes. Please double-check responses.

