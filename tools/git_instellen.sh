#!/bin/sh
# Eenmalig per clone: registreert de JSON-merge-driver
git config merge.json.name "Bibleverse JSON samenvoegen"
git config merge.json.driver "python3 tools/json_merge.py %O %A %B %P"
