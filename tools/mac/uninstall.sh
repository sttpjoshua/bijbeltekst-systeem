#!/bin/bash
# Haalt de Bibleverse lokale AI van deze Mac (het gedownloade model blijft in de Hugging Face-cache staan).
launchctl bootout "gui/$(id -u)/nl.sttpmedia.bibleverse.ai" 2>/dev/null || true
rm -f "$HOME/Library/LaunchAgents/nl.sttpmedia.bibleverse.ai.plist"
rm -rf "$HOME/Library/Application Support/Bibleverse"
echo "Verwijderd. De sleutel staat nog in de sleutelhanger; verwijderen met:"
echo "  security delete-generic-password -s bibleverse-mac"
