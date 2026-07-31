#!/usr/bin/env bash
# Run the CUA-Gym-Hub state API locally, against our own cua-gym Postgres.
#
# Why this exists: the hosted hub lives at cua-gym-hub.delta.soulhq.ai, in a DNS
# zone we do not control, and that zone has already vanished once (NOERROR, no A
# record) while the database stayed perfectly healthy. The hub is a thin FastAPI
# layer over mock_states/mock_state_events -- there is no reason our ability to
# demo or run episodes should depend on someone else's DNS.
#
# Set CUA_DATABASE_URL and the hub uses the Postgres store instead of its flat
# files (backend/app/config.py:56-58), so this serves the same 1560 seeded cells
# the hosted one would.
#
#   ./tools/run_local_hub.sh                 # port 9077
#   CUA_HUB_PORT=9100 ./tools/run_local_hub.sh
#
# Then point the mocks at it and rebuild -- VITE_API_BASE is baked in at build
# time, so this must be set before the build, not after:
#   VITE_API_BASE=http://127.0.0.1:9077 ./tools/build_hub_mocks.sh
set -euo pipefail

HUB_SRC="${CUA_HUB_SRC:-/Users/dhiren/Downloads/deccan-ai-cua-gym-hub-9c5be3cdb693/backend}"
PORT="${CUA_HUB_PORT:-9077}"
VENV="${CUA_HUB_VENV:-$HOME/.cache/cua-hub-venv}"

# Password lives in ~/.pgpass (chmod 600); keep it out of argv and out of logs.
: "${CUA_DB_HOST:=10.0.141.72}"
: "${CUA_DB_USER:=postgres}"
: "${CUA_DB_NAME:=cua-gym}"
if [[ -z "${CUA_DATABASE_URL:-}" ]]; then
  pw=$(awk -F: -v h="$CUA_DB_HOST" -v d="$CUA_DB_NAME" -v u="$CUA_DB_USER" \
        '$1==h && ($3==d||$3=="*") && $4==u {print $5; exit}' ~/.pgpass 2>/dev/null || true)
  [[ -z "$pw" ]] && { echo "no ~/.pgpass entry for $CUA_DB_USER@$CUA_DB_HOST/$CUA_DB_NAME" >&2; exit 1; }
  # percent-encode, so a password containing @ or : cannot break the DSN
  pw_enc=$(python3 -c 'import sys,urllib.parse;print(urllib.parse.quote(sys.argv[1],safe=""))' "$pw")
  export CUA_DATABASE_URL="postgresql://${CUA_DB_USER}:${pw_enc}@${CUA_DB_HOST}:5432/${CUA_DB_NAME}"
fi

[[ -d "$HUB_SRC" ]] || { echo "hub source not found: $HUB_SRC (set CUA_HUB_SRC)" >&2; exit 1; }

if [[ ! -x "$VENV/bin/uvicorn" ]]; then
  echo "creating hub venv at $VENV"
  python3.12 -m venv "$VENV" 2>/dev/null || python3 -m venv "$VENV"
  "$VENV/bin/pip" -q install -r "$HUB_SRC/requirements.txt"
fi

# The store makes SYNCHRONOUS psycopg calls inside async handlers, so a single
# slow round-trip to a remote Postgres (e.g. over a VPN) blocks the whole event
# loop and the hub goes unresponsive under any concurrency. Running several
# workers means one blocked call can't freeze the others. Each worker opens its
# own pool, so keep the count modest.
WORKERS="${CUA_HUB_WORKERS:-4}"

echo "hub  -> http://127.0.0.1:$PORT   (db: $CUA_DB_USER@$CUA_DB_HOST/$CUA_DB_NAME, workers=$WORKERS)"
cd "$HUB_SRC"
exec "$VENV/bin/uvicorn" app.main:app --host 127.0.0.1 --port "$PORT" --workers "$WORKERS"
