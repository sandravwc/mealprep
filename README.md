# mealprep

Self-hosted meal loop on a phone. Receipt photo in, "cook this tonight" push
out. Runs on a Poco F5 Pro (Snapdragon 8 Gen 1, 12 GB) under Termux, all
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
 daily driver phone                           poco f5 pro (termux, anywhere on LAN)
┌──────────────────────┐                     ┌────────────────────────────────────┐
│ browser (PWA)  ──────┼── POST /upload ───► │ app.py :8090 ──► intake.py ──┐     │
│   camera / stock /   │ ◄── /api/state ──── │      ▲                       │     │
│   recipes / profile  │                     │      │            llama-server :8080│
│                      │                     │      │            gemma-4-E4B + mmproj
│ ntfy app  ◄──────────┼── ntfy.sh ◄──────── │ suggest.py ◄─────────────────┘     │
│                      │                     │ janitor.py      cron 16:50 / 17:00 │
│ syncthing (optional) ┼── receipts/ ──────► │ data/*.json     runit services     │
└──────────────────────┘                     └────────────────────────────────────┘
```

## Why this stack

- Phone as server: already on, already has 12 GB RAM, sips power. Termux gives
  sshd, cron, runit, Python, clang. Nothing else needed.
- Gemma 4 E4B via llama.cpp: only model tier that fits and reads German
  receipts well. One model for receipts, fridge photos and recipe text.
  CPU only: Hexagon NPU and Adreno OpenCL are both unreachable from Termux
  on this SoC (see TODO.md, phase 0).
- PWA instead of APK: one HTML file, no toolchain, no signing, no yearly SDK
  tax. Push comes from ntfy because plain-HTTP pages cannot do web push.
- Flat JSON instead of SQLite: a household has hundreds of items, not
  millions. Everything loads in one `json.load`.
- Python stdlib only: `http.server`, `urllib`, `json`, `fcntl`. Zero pip.

## Layout

```
server/app.py            PWA + API, ThreadingHTTPServer, ~120 lines
server/intake.py         photo -> llama-server -> inventory.json, shelf/grace tables, ntfy
server/suggest.py        stock + history + profile -> 2 recipes -> suggestions.json, ntfy
server/janitor.py        daily dedupe/junk pass, flags food past grace, never deletes food
server/index.html        the whole UI, vanilla JS, German labels
server/test_*.py         one assert-based check per script, run with python3
docs/server.md           how the Poco is wired (services, paths, cron)
docs/design-chat.md      original design conversation
TODO.md                  phases, decisions, dead ends
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
- `SHELF` (purchase -> expires) and `GRACE` (days past expires still fine)
  per category. `status()` yields ok / soon / expired / bad.
- Non-receipt photo: model answers in prose, recorded as 0 items, no retry.
- ~90 s per receipt on the 8 Gen 1 CPU. Fine for cron.

### 2. Suggest (`suggest.py`)

- Cron 17:00. Text-only prompt: stock in tiers (DRINGEND / BALD / rest /
  NICHT verwenden), season from month, taste profile, liked and disliked
  recipes, cooked and skipped in the last 14 days.
- Asks for 2 dinners as JSON with `uses` naming stock items exactly. One of
  the two must change exactly one axis: new technique or new spice, not both.
- Push "Heute kochen?" with both titles, click opens the PWA.

### 3. Janitor (`janitor.py`)

- Cron 16:50. Dedupes stock by receipt + name, drops alias-"" junk, dedupes
  suggestions and receipt records. Pushes a summary only if it removed
  something.
- Food past its grace period is never deleted, only pushed as "entsorgen?".

### 4. PWA (`app.py` + `index.html`)

- Sections: Offen (unmade, last 2 days, "gekocht" button), Gekocht (date,
  thumbs, last 7 days + "ältere"), Vorrat (tiers, "weg" button), Bons
  (collapsible per day, tap thumbnail for the photo).
- Burger menu: taste profile toggles, free text, learned likes/dislikes.
- Camera button fixed at the bottom.
- Endpoints: `GET /api/state`, `POST /upload`, `POST /api/made/<id>`,
  `POST /api/rate/<id>/<up|down|none>`, `POST /api/remove/<id>`,
  `POST /api/profile`.
- Plain HTTP on the LAN, so "add to home screen" gives a bookmark, not a
  standalone install. Good enough.

## Config

`~/mealprep/.env` on the Poco, `KEY=VALUE` lines, never committed:

```
NTFY_TOPIC=mealprep-<random>          required for pushes
BASE_URL=http://192.168.1.106:8090    click target in pushes
LLM_URL=http://127.0.0.1:8080/v1/chat/completions   default
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

Then two runit services (`llama`, `mealprep`) and three cron lines, exact
contents in `docs/server.md`. Deploy = `git pull && sv restart mealprep`.

Daily driver: open `http://<poco>:8090`, add to home screen, install ntfy,
subscribe to the topic. Optional: Syncthing-Fork sharing `receipts/`.

## Test

```sh
cd server && python3 test_intake.py && python3 test_suggest.py && python3 test_janitor.py
```

## Status

Phases 0 to 3 built and running live (2026-09-17). Receipts parsed from real
REWE photos, recipes generated, pushes arriving. Now: daily use, tune
`SHELF`/`GRACE`/prompt/aliases as reality disagrees.

## Later / maybe

- Weather in the prompt (open-meteo, one request).
- Partial quantities on "gekocht" (2 of 10 eggs).
- Action buttons on the ntfy push itself.
- Fridge photo -> stock diff. Same model, second Syncthing folder already exists.
- HTTPS via Tailscale for a real standalone PWA and web push, dropping ntfy.
- NPU: only via an Android APK hosting LiteRT + QNN. Not from Termux.
