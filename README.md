# mealprep

Local-only meal suggestion service for a Poco F5 Pro (SD8 Gen 1, 8 GB) running as a home server via Termux.

Loop: receipt photo → OCR → Gemma 4 E4B normalizes into inventory → scheduled push notification: "you have X, Y, Z, cook this" → tap "made it" → inventory decrements.

Design notes: [docs/design-chat.md](docs/design-chat.md). Work plan: [TODO.md](TODO.md).

## Principles

- Intake friction is the enemy. Receipt photo is primary, barcode secondary. No manual entry.
- Flat JSON files, in-memory on load. SQLite only when history queries hurt.
- Two model tiers: E4B on-phone for extraction. Anything bigger is out of scope on 8 GB.
- Bursty inference a few times a day. Never continuous. F5 Pro throttles.
