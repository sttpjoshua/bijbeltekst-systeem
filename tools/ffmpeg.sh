#!/bin/sh
# ffmpeg installeren in GitHub Actions via de gewone Ubuntu-pakketten, met tijdslimieten
# (de installatie bleef op 11 nov soms hangen) en een tweede poging na een pakketlijst-update.
if command -v ffmpeg >/dev/null 2>&1; then echo "ffmpeg is er al"; exit 0; fi
OPT="-o Acquire::Retries=3 -o Acquire::http::Timeout=30 -o DPkg::Lock::Timeout=60"
timeout 240 sudo apt-get $OPT install -y -qq --no-install-recommends ffmpeg >/dev/null 2>&1 && echo "ffmpeg geinstalleerd" && exit 0
echo "Eerste poging mislukt of te traag; pakketlijst bijwerken en opnieuw"
timeout 180 sudo apt-get $OPT update -qq >/dev/null 2>&1
timeout 300 sudo apt-get $OPT install -y -qq --no-install-recommends ffmpeg >/dev/null 2>&1 && echo "ffmpeg geinstalleerd (tweede poging)" && exit 0
echo "ffmpeg installeren mislukt"; exit 1
