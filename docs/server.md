# Poco F5 Pro server notes

- Termux sshd :8022, proot Debian sshd :8122 (unrelated, Shoko)
- Services: `export SVDIR=$PREFIX/var/service` first in non-login shells, then `sv status ...`
- Syncthing GUI: http://<poco>:8384, device ID `TQ66ARI-ELDGF2D-Q4WLRPI-4MCQXJD-NOD43KZ-HOF2QAS-HUUJBDW-IUFAOQT`
- Folders: `~/mealprep/receipts` (id mealprep-receipts), `~/mealprep/fridge` (id mealprep-fridge)
- llama.cpp: `~/mealprep/llama.cpp/build-cpu/bin`, models in `~/mealprep/models`
- CPU thermal zones: `/sys/class/thermal/thermal_zone19..22` = cpuss-0..3, millidegrees
