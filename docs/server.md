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
