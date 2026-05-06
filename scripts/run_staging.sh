#!/usr/bin/env bash
# Staging launcher for the on-prem app. Exposes the cloud relay against a
# locally-running edge service (or any reachable WSS endpoint). Prod paths
# are not touched: distinct Flask port, distinct sources file, distinct
# StatCrew/Virtius config files.
#
# Usage:
#   CLOUD_RELAY_TOKEN=secret \
#   CLOUD_RELAY_URL=ws://127.0.0.1:8000/ws/publisher \
#   scripts/run_staging.sh
#
# Override any default by exporting the matching env var before running.

set -euo pipefail

cd "$(dirname "$0")/.."

# --- Cloud relay --------------------------------------------------------
export CLOUD_RELAY_ENABLED="${CLOUD_RELAY_ENABLED:-1}"
export CLOUD_RELAY_URL="${CLOUD_RELAY_URL:-ws://127.0.0.1:8000/ws/publisher}"
: "${CLOUD_RELAY_TOKEN:?CLOUD_RELAY_TOKEN must be set (must match edge PUBLISHER_AUTH_TOKEN)}"
export CLOUD_RELAY_TOKEN
export CLOUD_RELAY_PUBLISHER_NAME="${CLOUD_RELAY_PUBLISHER_NAME:-onprem-staging}"
export CLOUD_RELAY_POLL_INTERVAL="${CLOUD_RELAY_POLL_INTERVAL:-0.5}"

# --- Flask --------------------------------------------------------------
# Distinct port so a prod instance on :5000 keeps running unaffected.
export FLASK_PORT="${FLASK_PORT:-5050}"
export FLASK_HOST="${FLASK_HOST:-127.0.0.1}"
export FLASK_DEBUG="${FLASK_DEBUG:-0}"

# --- Isolated state files ----------------------------------------------
export SCOREBOARD_SOURCES_FILE="${SCOREBOARD_SOURCES_FILE:-data_sources.staging.json}"
# StatCrew/Virtius configs are not env-isolated yet; the staging run shares
# them with prod. Simulators only emit OES TCP, so neither file is written
# unless the staging UI is manually used to add a watcher.

# --- TCP listener for inbound OES (we use TCP-client mode against
#     simulators, so this just needs to be a free port).
export SCOREBOARD_TCP_PORT="${SCOREBOARD_TCP_PORT:-5051}"
export SCOREBOARD_UDP_PORT="${SCOREBOARD_UDP_PORT:-5052}"

PYTHON_BIN="${PYTHON_BIN:-python3.14}"

echo "Starting staging on-prem instance"
echo "  Flask:        http://${FLASK_HOST}:${FLASK_PORT}"
echo "  Sources file: ${SCOREBOARD_SOURCES_FILE}"
echo "  Cloud relay:  ${CLOUD_RELAY_URL} (publisher=${CLOUD_RELAY_PUBLISHER_NAME})"
echo

exec "${PYTHON_BIN}" main.py
