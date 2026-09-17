# Poco F5 Pro server notes

- Termux sshd :8022, proot Debian sshd :8122 (unrelated, Shoko)
- Services: `export SVDIR=$PREFIX/var/service` first in non-login shells, then `sv status ...`
- Syncthing GUI: http://<poco>:8384, device ID `TQ66ARI-ELDGF2D-Q4WLRPI-4MCQXJD-NOD43KZ-HOF2QAS-HUUJBDW-IUFAOQT`
- Folders: `~/mealprep/receipts` (id mealprep-receipts), `~/mealprep/fridge` (id mealprep-fridge)
- llama.cpp: `~/mealprep/llama.cpp/build-cpu/bin`, models in `~/mealprep/models`
- CPU thermal zones: `/sys/class/thermal/thermal_zone19..22` = cpuss-0..3, millidegrees
- Run server: `./llama.cpp/build-cpu/bin/llama-server -m models/gemma-4-E4B-it-Q4_0.gguf --mmproj models/mmproj-gemma-4-E4B-it-Q8_0.gguf --jinja -t 8 -c 4096 --host 0.0.0.0 --port 8080`
- Request must include `"chat_template_kwargs":{"enable_thinking":false}` or Gemma thinks until max_tokens
- Secrets (ntfy topic) live in `~/mealprep/.env` on the Poco, never in the repo
- OpenCL: dead. Linker namespace blocks vendor driver from Termux. Don't retry without an APK
- Deploy: `cd ~/mealprep/repo && git pull && sv restart mealprep` (SVDIR exported)
- Services: `llama` (:8080 localhost only), `mealprep` (:8090 LAN). Logs `$PREFIX/var/log/sv/<name>/current`
- Data: `~/mealprep/data/{inventory,receipts,aliases}.json`, images `~/mealprep/receipts/`
- Manual intake: `python3 ~/mealprep/repo/server/intake.py [file]`
- Suggest manually: `python3 ~/mealprep/repo/server/suggest.py`. Cron 17:00 daily
- Mock stock was added 2026-09-17 with `receipt: "mock"`, delete via "weg" or filter inventory.json
- Cron: intake */5, janitor 16:50, suggest 17:00
- Taste profile: `data/profile.txt`, edit in PWA under "Geschmack"
