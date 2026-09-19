# mealprep

Self-hosted meal loop on a phone. Receipt photo in, "cook this tonight" push
out. Runs on a Poco F5 Pro (Snapdragon 8+ Gen 1, 8 GB + 4 GB swap) under
Termux, all inference local via llama.cpp + Gemma 4 E4B. No cloud model, no
account, no database. Couple Python files and one HTML page. No React no
nothing.

## Goal

1. Shop. Open the page on your phone, tap the camera button, photograph
   receipt or groceries. Done, 1 tap + shutter.
2. Server reads the photo with a vision model, expands REWE-speak
   ("JOGH. GRIE. ART." -> "Joghurt griechischer Art"), files each item with a
   category and expiry date. Says so if the photo was bad.
3. Scheduled push notification per meal with two dish ideas built from what is
   in stock, soonest-expiring first, matching your taste profile and today's
   weather, one of the two nudging you toward something new.
4. Tap "gekocht": used ingredients leave the stock, recipe lands in history.
   Thumbs up/down teaches the profile. Photo of dish can be taken and stored
   with recipe for future use after finished.

```txt
 daily driver phone (anywhere)              poco f5 pro (termux, home LAN)
┌──────────────────────┐                  ┌───────────────────────────────────────┐
│ browser (PWA)        │ https :8443      │ app.py ─► intake.py / fridge.py       │
│  camera, stock,      ├─────────────────►│  auth.py     ▲           │            │
│  recipes, profile    │◄─────────────────┤              │           ▼            │
│                      │ http :8090 (LAN) │ data/*.json     llama-server :8080    │
│                      │                  │              ▲  (started per job)     │
│ ntfy app             │                  │              │           │            │
│  push + login link ◄─┼── ntfy.sh ◄──────┤ suggest.py ◄─────────────┘            │
│                      │                  │ janitor.py  dyndns.py  acme.sh  cron  │
└──────────────────────┘                  └───────────────────────────────────────┘
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
  tax.
- ntfy for push: account-free, self-hostable, one HTTP POST. Web push would
  need a service worker and VAPID plumbing for the same result.
- Own domain + Let's Encrypt over the AutoDNS API instead of a VPN or a
  reverse proxy: nothing to install on the client, no port 80, renews itself.
- Flat JSON instead of SQLite: a household has hundreds of items, not
  millions. Everything loads in one `json.load`.
- Python stdlib only: `http.server`, `ssl`, `urllib`, `json`, `fcntl`. Zero pip.

## Layout

```txt
server/app.py            PWA + API, ThreadingHTTPServer, HTTP 8090 + HTTPS 8443
server/auth.py           password login, cookie session, token links for pushes, per-IP ban
server/config.py         defaults for categories [shelf, grace], taste tags, meals; overrides in data/config.json
server/intake.py         receipt photo -> llama-server -> inventory.json, ntfy; shared llm()/lock helpers
server/fridge.py         fridge photo -> seen items -> add/remove proposals, applied only on tap
server/suggest.py        stock + history + profile + weather -> 2 recipes per meal -> suggestions.json, ntfy
server/janitor.py        daily dedupe/junk pass, flags food past grace, never deletes food
server/dyndns.py         public IP -> A record over the AutoDNS API, creds reused from acme.sh
server/index.html        the whole UI, vanilla JS, German labels
server/manifest.json     PWA manifest
server/test_*.py         one assert-based check per script, run with python3
docs/server.md           how the Poco is wired (services, paths, cron)
docs/TODO.md             phases, decisions, dead ends
```

Runtime data on the Poco, outside the repo: `~/mealprep/data/*.json`,
`~/mealprep/{receipts,fridge,dishes}/*.jpg`, `~/mealprep/models/*.gguf`,
`~/mealprep/tls/`, `~/mealprep/.env`.

## Modules

### 1. Intake (`intake.py`)

- Triggered by `POST /upload` (spawns a subprocess) and by cron every 5 min
  for anything left unprocessed in `receipts/`, which doubles as retry.
  `flock` serialises all model jobs, `llm()` starts and stops `llama-server`
  around each run.
- Image -> chat completion with `enable_thinking: false` (Gemma otherwise
  burns the whole budget thinking). Prompt asks for
  `{"hinweis": <what is wrong with the photo, or empty>, "items": [{raw, name, qty, unit, category}]}`,
  expansion rules, skip non-food.
- `data/aliases.json`: `{"raw line or name, lowercase": "canonical" | ""}`.
  Empty string drops the item. Hand-edit when the model keeps a bad name.
- Categories carry `[shelf, grace]`: days from purchase to expiry, days past
  expiry still fine. `status()` yields ok / soon / expired / bad. Editable in
  the PWA, `other` always exists.
- Non-receipt photo: recorded as 0 items with the hint, no retry.
- ~90 s per receipt on the 8+ Gen 1 CPU, plus 15 s model load. Fine for cron.

### 2. Fridge photo (`fridge.py`)

- 🧊 button or a file dropped into `fridge/`. Model lists visible items plus
  a photo hint (unscharf, zu dunkel, Etiketten abgewandt). A second
  text-only pass on the loaded model keeps only what it calls food or drink,
  container-only names ("Kleine blaue Dose") are dropped by regex. Fewer than
  three kept items adds a hint anyway.
- Photos within an hour form one scan. Seen but not in stock -> "add?".
  Perishable stock unseen on two scans in a row -> "remove?". Proposals sit
  in the PWA until tapped ✓ or ✕. Occlusion makes auto-apply wrong, so
  nothing is automatic here.

### 3. Suggest (`suggest.py`)

- Cron every 15 min runs `suggest.py --due`: each meal in the config (name +
  time, default Abendessen 17:00, add Frühstück or Mittagessen in the PWA or
  any other meal) gets one run per day at its time.
- Text-only prompt per meal type: stock in tiers (DRINGEND / BALD / rest /
  NICHT verwenden), season from month, today's weather (Open-Meteo, no key,
  place from `.env`, cold and wet steers to soup and oven, hot to salad),
  taste profile, liked and disliked recipes, cooked and skipped in the last
  14 days. TODO: three months.
- Asks for 2 dishes as JSON with an emoji, `uses` naming stock items exactly.
  One of the two must change exactly one axis: new technique or new spice,
  not both.
- Push "Abendessen?" with both titles, click opens the PWA logged in.

### 4. Janitor (`janitor.py`)

- Cron 16:50. Dedupes stock by receipt + name, drops alias-"" junk, dedupes
  suggestions, receipt records and proposals. Pushes a summary only if it
  removed something.
- Food past its grace period is never deleted, only pushed as "entsorgen?".

### 5. PWA (`app.py` + `index.html`)

Sections, top to bottom, every group collapsible:

| section | shows | actions |
|---|---|---|
| Offen | unmade suggestions of the last 2 days, plate photo from an earlier cook of the same dish | gekocht |
| Gekocht | last 7 days + ältere, date, emoji, plate photo or 📷 | 👍 👎 ↩ (undo, restores stock) |
| Schrank-Vorschläge | add / remove proposals from fridge photos | ✓ ✕ |
| Vorrat | grouped by shelf stability (verdirbt schnell / hält eine Woche / einen Monat / überlebt dich), expiry tag per item | weg |
| Bons | per day, item count, photo hint, items in a dropdown, tap for photo | |
| Schrank-Fotos | per day, time, seen count, photo hint, items in a dropdown, tap for photo | |
| ☰ | taste toggles, free text, learned likes / dislikes, tag editor, meals, category table | speichern, abmelden |
| bottom bar | 📷 Bon, 🧊 Kühl-/Vorratsschrank | camera |

Dates are dd-mm-yyyy. Profile in `data/profile.json`, config in
`data/config.json`.

Endpoints:

| method, path | does |
|---|---|
| `GET /` | the page, or the login form without a session |
| `GET /manifest.json` | public, so the install prompt works before login |
| `GET /api/state` | everything the page renders, one JSON |
| `GET /receipts/<f>`, `/fridge/<f>`, `/dishes/<f>` | photos |
| `POST /upload` | receipt photo body -> intake |
| `POST /upload?kind=fridge` | fridge photo body -> fridge scan |
| `POST /upload?kind=dish&id=<id>` | plate photo for a cooked recipe |
| `POST /api/made/<id>` | cooked: remove `uses` from stock, remember them |
| `POST /api/unmade/<id>` | undo: back to open, stock restored |
| `POST /api/rate/<id>/<up\|down\|none>` | thumbs |
| `POST /api/remove/<id>` | drop a stock item |
| `POST /api/proposal/<id>/<accept\|reject>` | apply or dismiss a fridge proposal |
| `POST /api/profile` | taste tags + text |
| `POST /api/config` | categories, tags, meals |
| `POST /login`, `POST /logout` | cookie session, HTTPS only |

Transport and auth:

- HTTP 8090: LAN only, no auth, never forward it.
- HTTPS 8443: served when `~/mealprep/tls/{fullchain,key}.pem` exist and
  `PASSWORD` is set. Password form sets a cookie for a year, ntfy click links
  carry `?t=<AUTH_TOKEN>` and set the same cookie, "abmelden" clears it. Five
  wrong passwords from one IP lock it for an hour in-process. Every deny,
  fail and ban is one `AUTH ... <ip>` line in the service log, fail2ban-shaped
  for a future load balancer.

### 6. DynDNS (`dyndns.py`)

- Cron every 5 min. Public IP from the router over UPnP, else an account-free
  echo service. On change: rewrite the A record through the same AutoDNS bulk
  task acme.sh uses, TTL 300. Credentials parsed from
  `~/.acme.sh/account.conf`, nothing stored twice.

## Config

`~/mealprep/.env` on the Poco, `KEY=VALUE` lines, never committed:

```sh
NTFY_TOPIC=mealprep-<random>                           # required for pushes
BASE_URL=https://poco.example.org:8443                 # click target in pushes
PASSWORD=<login password>                              # required, HTTPS refuses to start without it
AUTH_TOKEN=<generated on first push>                   # logs the phone in via push links, keep secret
LLM_URL=http://127.0.0.1:8080/v1/chat/completions      # default
WEATHER_PLACE=Berlin                                   # optional, any town name, geocoded once
DYNDNS_ZONE=example.org  DYNDNS_HOST=poco  DYNDNS_NS=a.ns14.net   # defaults match this install
```

`PORT` (default 8090) and `TLS_PORT` (default 8443) env vars for `app.py`.

Certificate, once, on the Poco. The AutoDNS API user is a clone of the main
user with zone read, zone update and zone bulk update rights:

```sh
curl -s https://get.acme.sh | sh -s email=<mail>
AUTODNS_USER=<clone> AUTODNS_PASSWORD=<pw> AUTODNS_CONTEXT=4 \
  ~/.acme.sh/acme.sh --issue --server letsencrypt --dns dns_autodns -d poco.example.org
~/.acme.sh/acme.sh --install-cert -d poco.example.org \
  --fullchain-file ~/mealprep/tls/fullchain.pem --key-file ~/mealprep/tls/key.pem \
  --reloadcmd "SVDIR=$PREFIX/var/service sv restart mealprep"
```

acme.sh renews from its own cron line and restarts the app. Router: forward
TCP 8443 to the Poco (TP-Link calls it Virtual Servers), enable UPnP if you
want the IP lookup to stay inside the LAN.

## Install on the Poco

```sh
pkg install cmake ninja git python cronie termux-api termux-services
git clone --depth 1 https://github.com/ggml-org/llama.cpp ~/mealprep/llama.cpp
cmake -S ~/mealprep/llama.cpp -B ~/mealprep/llama.cpp/build-cpu -G Ninja -DCMAKE_BUILD_TYPE=Release -DGGML_NATIVE=ON -DLLAMA_CURL=OFF
cmake --build ~/mealprep/llama.cpp/build-cpu --target llama-server -j8
# models: ggml-org/gemma-4-E4B-it-GGUF  gemma-4-E4B-it-Q4_0.gguf + mmproj-gemma-4-E4B-it-Q8_0.gguf -> ~/mealprep/models/
git clone https://github.com/sandravwc/mealprep ~/mealprep/repo
```

Then one runit service (`mealprep`) and the cron lines (intake, fridge,
dyndns every 5 min, janitor 16:50, `suggest.py --due` every 15 min, plus
acme.sh's own), exact contents in `docs/server.md`. The model server is
started by each job and stopped after, nothing holds 5 GB while idle.
Deploy = `git pull && sv restart mealprep`.

Daily driver: open `https://poco.example.org:8443` (or `http://<poco>:8090`
on the LAN), log in once, add to home screen, install ntfy, subscribe to the
topic. Pushes log you in from then on.

## Test

```sh
cd server && for t in test_*.py; do python3 $t; done
```

## Status

Phases 0 to 5 built and running live (2026-09-19). Receipts parsed from real
REWE photos, recipes generated, pushes arriving, reachable from outside behind
a login. Now: daily use, tune categories / prompt / aliases as reality
disagrees.

## Later / maybe

- Partial quantities on "gekocht" (2 of 10 eggs).
- Action buttons on the ntfy push itself.
- Web push, manifest icons + service worker for a standalone install.
- Qwen3-VL-8B as the fridge model, one at a time in the 8 GB.
- Load balancer in front with fail2ban reading the `AUTH` lines.
- NPU: only via an Android APK hosting LiteRT + QNN. Not from Termux.
