#!/bin/bash
# Zet de Bibleverse lokale AI op deze Mac. Opnieuw uitvoeren werkt als update.
# Wat het doet:
#   1. maakt een eigen Python-omgeving (los van de rest van de Mac) met mlx-lm
#   2. kopieert bijbel_helper.py naar ~/Library/Application Support/Bibleverse/
#   3. zet een launchd-taak die elke 30 minuten draait, ook na een herstart
# Verwijderen: bash uninstall.sh
set -euo pipefail
APP="$HOME/Library/Application Support/Bibleverse"
PLIST="$HOME/Library/LaunchAgents/nl.sttpmedia.bibleverse.ai.plist"
LOG="$HOME/Library/Logs/bibleverse-ai.log"

if ! command -v brew >/dev/null 2>&1; then
  for b in /opt/homebrew/bin/brew /usr/local/bin/brew; do [ -x "$b" ] && eval "$("$b" shellenv)"; done
fi
if ! command -v brew >/dev/null 2>&1; then
  echo "Homebrew ontbreekt. Installeer het eerst via https://brew.sh en start dit script opnieuw."; exit 1
fi
brew list --formula python@3.12 >/dev/null 2>&1 || brew install -q python@3.12
PY="$(brew --prefix python@3.12)/bin/python3.12"
[ -x "$PY" ] || PY="$(brew --prefix)/bin/python3"

if ! security find-generic-password -s bibleverse-mac -w >/dev/null 2>&1; then
  echo "Nog geen GitHub-sleutel in de sleutelhanger. Zet hem erin met:"
  echo "  security add-generic-password -a bibleverse -s bibleverse-mac -U -w"
  echo "(hij vraagt dan om de sleutel; plakken en Enter). Start daarna dit script opnieuw."
  echo "Tip: de sleutel van Sideways Wire (service sidewayswire-mac) kan niet hergebruikt worden als hij alleen die repo mag lezen."
  exit 1
fi

mkdir -p "$APP" "$HOME/Library/LaunchAgents" "$HOME/Library/Logs"
[ -x "$APP/venv/bin/python3" ] || "$PY" -m venv "$APP/venv"
"$APP/venv/bin/python3" -m pip install -q --disable-pip-version-check --upgrade mlx-lm
PY="$APP/venv/bin/python3"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || pwd)"
if [ -f "$HERE/bijbel_helper.py" ]; then
  cp "$HERE/bijbel_helper.py" "$APP/bijbel_helper.py"
else   # gestart met curl | bash: pak de nieuwste versie van GitHub
  curl -fsSL "https://raw.githubusercontent.com/sttpjoshua/bijbeltekst-systeem/main/tools/mac/bijbel_helper.py" -o "$APP/bijbel_helper.py"
fi
cat > "$PLIST" <<PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>nl.sttpmedia.bibleverse.ai</string>
  <key>ProgramArguments</key><array><string>$PY</string><string>$APP/bijbel_helper.py</string></array>
  <key>StartInterval</key><integer>1800</integer>
  <key>RunAtLoad</key><true/>
  <key>LowPriorityIO</key><true/>
  <key>Nice</key><integer>10</integer>
  <key>StandardOutPath</key><string>$LOG</string>
  <key>StandardErrorPath</key><string>$LOG</string>
</dict></plist>
PL
launchctl bootout "gui/$(id -u)/nl.sttpmedia.bibleverse.ai" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
echo ""
echo "Klaar. De lokale AI draait nu elke 30 minuten, ook na een herstart."
echo "De eerste keer downloadt hij het taalmodel (ongeveer 8 GB); dat duurt even. Voortgang:"
echo "  tail -f \"$LOG\""
