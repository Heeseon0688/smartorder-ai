#!/bin/sh
# Reinstall into the node_modules volume only when package-lock.json changed.
set -eu
hash=$(sha256sum package-lock.json | cut -d' ' -f1)
if [ "$(cat node_modules/.lock-hash 2>/dev/null)" != "$hash" ]; then
  npm ci --no-audit --no-fund
  echo "$hash" > node_modules/.lock-hash
fi
exec npm run dev -- --host 0.0.0.0
