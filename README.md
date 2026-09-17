# mealprep

Self-hosted meal loop on a phone. Receipt photo in, "cook this tonight" push
out. Runs on a Poco F5 Pro (Snapdragon 8+ Gen 1, 8 GB + 4 GB swap) under Termux, all
inference local via llama.cpp + Gemma 4 E4B. No cloud model, no account,
no database. Three Python files and one HTML page.

## Goal

1. Shop. Open the page on your phone, tap the camera button, photograph the
   receipt. Done, 1 tap + shutter.
2. Server reads the photo with a vision model, expands REWE-speak
   ("JOGH. GRIE. ART." -> "Joghurt griechischer Art"), files each item with a
   category and expiry date.
3. 17:00 daily: push notification with two dinner ideas built from what is in
   stock, soonest-expiring first, matching your taste profile, one of the two
   nudging you toward something new.
4. Tap "gekocht": used ingredients leave the stock, recipe lands in history.
   Thumbs up/down teaches the profile.

```
 daily driver phone                      poco f5 pro (termux, anywhere on LAN)
┌──────────────────────┐                ┌──────────────────────────────────────┐
│ browser (PWA)        │ POST /upload   │ app.py :8090 ─► intake.py / fridge.py│
│  camera, stock,      ├───────────────►│      ▲               │               │
│  recipes, profile    │◄───────────────┤      │               ▼               │
│                      │ GET /api/state │ data/*.json    llama-server :8080    │
│                      │                │      ▲        (started per job)      │
│ ntfy app             │                │      │               │               │
│  push + click ◄──────┼── ntfy.sh ◄────┤ suggest.py ◄─────────┘               │
│                      │                │ janitor.py      cron 16:50 / 17:00   │
└──────────────────────┘                └──────────────────────────────────────┘
```

## Why this stack

- Phone as server: already on, 8 GB RAM plus 4 GB swap, sips power. Termux
  gives sshd, cron, runit, Python, clang. Nothing else needed. Model is loaded
  per job, not resident: HyperOS kills the app when it sits on 5 GB all day.
- Gemma 4 E4B via llama.cpp: only model tier that fits and reads German
  receipts well. One model for receipts, fridge photos and recipe text.
  CPU only in Termux: the Hexagon NPU has no llama.cpp support on this SoC and
  Adreno OpenCL is unreachable from an app's linker namespace. The GPU does
  work from an adb shell (see docs/TODO.md, phase 4b).
- PWA instead of APK: one HTML file, no toolchain, no signing, no yearly SDK
  tax. Push comes from ntfy because plain-HTTP pages cannot do web push.
- Flat JSON instead of SQLite: a household has hundreds of items, not
  millions. Everything loads in one `json.load`.
- Python stdlib only: `http.server`, `urllib`, `json`, `fcntl`. Zero pip.

## Layout

```
server/app.py            PWA + API, ThreadingHTTPServer, ~120 lines
server/config.py         defaults for categories [shelf, grace] and taste tags, overrides in data/config.json
server/intake.py         photo -> llama-server -> inventory.json, ntfy
server/suggest.py        stock + history + profile -> 2 recipes -> suggestions.json, ntfy
server/fridge.py         fridge photo -> seen items -> add/remove proposals, applied only on tap
server/janitor.py        daily dedupe/junk pass, flags food past grace, never deletes food
server/index.html        the whole UI, vanilla JS, German labels
server/test_*.py         one assert-based check per script, run with python3
docs/server.md           how the Poco is wired (services, paths, cron)
docs/TODO.md             phases, decisions, dead ends
```

Runtime data on the Poco, outside the repo: `~/mealprep/data/*.json`,
`~/mealprep/receipts/*.jpg`, `~/mealprep/models/*.gguf`, `~/mealprep/.env`.

## Modules

### 1. Intake (`intake.py`)

- Triggered by `POST /upload` (spawns a subprocess) and by cron every 5 min
  for files Syncthing dropped into `receipts/`. `flock` serialises runs.
- Image -> `llama-server` chat completion with `enable_thinking: false`
  (Gemma otherwise burns the whole budget thinking). Prompt asks for
  `[{raw, name, qty, unit, category}]`, expansion rules, skip non-food.
- `data/aliases.json`: `{"raw line or name, lowercase": "canonical" | ""}`.
  Empty string drops the item. Hand-edit when the model keeps a bad name.
- Categories carry `[shelf, grace]`: days from purchase to expiry, days past
  expiry still fine. `status()` yields ok / soon / expired / bad. Editable in
  the PWA, `other` always exists.
- Non-receipt photo: model answers in prose, recorded as 0 items, no retry.
- ~90 s per receipt on the 8+ Gen 1 CPU, plus 15 s model load. Fine for cron.

### 2. Suggest (`suggest.py`)

- Cron 17:00. Text-only prompt: stock in tiers (DRINGEND / BALD / rest /
  NICHT verwenden), season from month, today's weather (Open-Meteo, no key,
  place from `.env`, cold and wet steers to soup and oven, hot to salad),
  taste profile, liked and disliked recipes, cooked and skipped in the last
  14 days.
- Asks for 2 dinners as JSON with `uses` naming stock items exactly. One of
  the two must change exactly one axis: new technique or new spice, not both.
- Push "Heute kochen?" with both titles, click opens the PWA.

### 3. Janitor (`janitor.py`)

- Cron 16:50. Dedupes stock by receipt + name, drops alias-"" junk, dedupes
  suggestions and receipt records. Pushes a summary only if it removed
  something.
- Food past its grace period is never deleted, only pushed as "entsorgen?".

### 4. Fridge photo (`fridge.py`)

- 🧊 button or a file dropped into `fridge/`. Model lists visible items, a
  second text-only pass on the loaded model keeps only what it calls food or
  drink, container-only names ("Kleine blaue Dose") are dropped by regex.
  Then the script diffs against stock: unseen-in-stock -> "add?", perishable stock unseen on two
  photos in a row -> "remove?". Proposals sit in the PWA until tapped ✓ or ✕.
  Occlusion makes auto-apply wrong, so nothing is automatic here.

### 5. PWA (`app.py` + `index.html`)

- Sections: Offen (unmade, last 2 days, "gekocht" button), Gekocht (date,
  thumbs, last 7 days + "ältere"), Schrank-Vorschläge (✓ ✕), Vorrat
  grouped by shelf stability (verdirbt schnell / hält eine Woche / einen
  Monat / überlebt dich) with expiry tags per item, Bons
  (collapsible per day, tap thumbnail for the photo).
- Burger menu: taste toggles, free text, learned likes/dislikes, tag editor,
  category table (shelf and grace days). Saved to `data/profile.json` and
  `data/config.json`.
- Two camera buttons fixed at the bottom: Bon, Kühlschrank.
- Endpoints: `GET /api/state`, `POST /upload`, `POST /api/made/<id>`,
  `POST /api/rate/<id>/<up|down|none>`, `POST /api/remove/<id>`,
  `POST /api/profile`, `POST /api/config`, `POST /upload?kind=fridge`,
  `POST /api/proposal/<id>/<accept|reject>`.
- Plain HTTP on the LAN, so "add to home screen" gives a bookmark, not a
  standalone install. Good enough.

## Config

`~/mealprep/.env` on the Poco, `KEY=VALUE` lines, never committed:

```
NTFY_TOPIC=mealprep-<random>          required for pushes
BASE_URL=http://192.168.1.106:8090    click target in pushes
LLM_URL=http://127.0.0.1:8080/v1/chat/completions   default
WEATHER_PLACE=Berlin                  optional, any town name, geocoded once
```

`PORT` env var for `app.py` (default 8090).

## Install on the Poco

```sh
pkg install cmake ninja git python cronie termux-api termux-services
git clone --depth 1 https://github.com/ggml-org/llama.cpp ~/mealprep/llama.cpp
cmake -S ~/mealprep/llama.cpp -B ~/mealprep/llama.cpp/build-cpu -G Ninja -DCMAKE_BUILD_TYPE=Release -DGGML_NATIVE=ON -DLLAMA_CURL=OFF
cmake --build ~/mealprep/llama.cpp/build-cpu --target llama-server -j8
# models: ggml-org/gemma-4-E4B-it-GGUF  gemma-4-E4B-it-Q4_0.gguf + mmproj-gemma-4-E4B-it-Q8_0.gguf -> ~/mealprep/models/
git clone https://github.com/sandravwc/mealprep ~/mealprep/repo
```

Then one runit service (`mealprep`) and four cron lines, exact contents in
`docs/server.md`. The model server is started by each job and stopped after,
nothing holds 5 GB while idle. Deploy = `git pull && sv restart mealprep`.

Daily driver: open `http://<poco>:8090`, add to home screen, install ntfy,
subscribe to the topic. Optional: Syncthing-Fork sharing `receipts/`.

## Test

```sh
cd server && for t in test_*.py; do python3 $t; done
```

## Status

Phases 0 to 3 built and running live (2026-09-17). Receipts parsed from real
REWE photos, recipes generated, pushes arriving. Now: daily use, tune
`SHELF`/`GRACE`/prompt/aliases as reality disagrees.

## Later / maybe

- Partial quantities on "gekocht" (2 of 10 eggs).
- Action buttons on the ntfy push itself.
- HTTPS via Tailscale, then web push, then drop ntfy. Planned as phase 5.
- NPU: only via an Android APK hosting LiteRT + QNN. Not from Termux.
