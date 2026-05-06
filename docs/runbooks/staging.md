# Staging the cloud relay end-to-end

Goal: prove that on-prem `cloud_relay` → edge service → viewer page works
without touching prod. Run the edge locally, run a second on-prem
instance on a different Flask port pointed at simulator data, and verify
the edge state mirror updates in real time.

The prod on-prem instance is unaffected. The staging instance uses:

- a distinct Flask port (default `5050`)
- a distinct sources file (`data_sources.staging.json`)
- a distinct edge SQLite database (`instance/edge-staging.db`)

## Prerequisites

Two repos checked out side-by-side:

- `flaskVirtualScoreboard` — on-prem app, on the `external-access` branch
- `unc-virtual-score-edge` — AWS edge service

Python 3.14, edge requirements installed user-locally:

```bash
python3.14 -m pip install --user --break-system-packages \
  -r ../unc-virtual-score-edge/requirements.txt
```

## 1. Boot the edge service

```bash
cd ../unc-virtual-score-edge

# Provision a viewer with Basketball access against an isolated DB.
rm -f instance/edge-staging.db
DATABASE_URL=sqlite:///edge-staging.db \
PUBLISHER_AUTH_TOKEN=stage-secret-xyz \
  python3.14 -m flask --app main.py user create stageviewer --password viewerpass

DATABASE_URL=sqlite:///edge-staging.db \
PUBLISHER_AUTH_TOKEN=stage-secret-xyz \
  python3.14 -m flask --app main.py user grant stageviewer Basketball

# Start the edge on :8000.
DATABASE_URL=sqlite:///edge-staging.db \
PUBLISHER_AUTH_TOKEN=stage-secret-xyz \
FLASK_PORT=8000 FLASK_HOST=127.0.0.1 \
  python3.14 main.py > /tmp/edge.log 2>&1 &

# Sanity-check.
curl -sf http://127.0.0.1:8000/healthz
```

## 2. Boot at least one OES simulator

The on-prem repo ships sport simulators under `simulators/` that listen
on TCP for connections from the staging instance.

```bash
cd ../flaskVirtualScoreboard
python3.14 simulators/sim_basketball.py --port 6001 > /tmp/sim_bball.log 2>&1 &
```

`scripts/run_staging.sh` will try to reach all 9 sports' default ports
(`6001`-`6009`); unconfigured ports just log connection-refused and are
otherwise harmless. To exercise everything at once:

```bash
python3.14 simulators/run_all.py > /tmp/sims.log 2>&1 &
```

## 3. Boot the staging on-prem instance

```bash
CLOUD_RELAY_TOKEN=stage-secret-xyz \
CLOUD_RELAY_URL=ws://127.0.0.1:8000/ws/publisher \
  bash scripts/run_staging.sh > /tmp/staging.log 2>&1 &
```

This uses `data_sources.staging.json`, Flask port `5050`, and starts the
relay against the local edge. Prod paths are untouched.

## 4. Verify the wire

Log in to the edge and pull the mirrored state. The `game_clock` should
tick down between samples and at least one of the scores should change as
the simulator plays.

```bash
curl -s -c /tmp/cookies.txt http://127.0.0.1:8000/login -o /dev/null
curl -s -b /tmp/cookies.txt -c /tmp/cookies.txt -X POST \
  http://127.0.0.1:8000/login \
  --data-urlencode "username=stageviewer" \
  --data-urlencode "password=viewerpass" -L -o /dev/null

curl -s -b /tmp/cookies.txt http://127.0.0.1:8000/get_raw_data/Basketball
curl -s -b /tmp/cookies.txt http://127.0.0.1:8000/get_sources
```

Expected:

- `get_raw_data/Basketball` returns a populated dict with `game_clock`,
  `home_score`, etc., including a `_meta.source` of `tcp:127.0.0.1:6001`.
- `get_sources` lists the simulator under the user's visible sports.
- Sleeping a few seconds and re-querying shows the clock has advanced.
- Browsing http://127.0.0.1:8000/Basketball renders the viewer page.

## 5. Tear down

```bash
# Find and kill the python3.14 children we started.
pkill -f "simulators/sim_"
pkill -f "scripts/run_staging.sh"
pkill -f "unc-virtual-score-edge/main.py"
```

Or kill by recorded PIDs if you captured them.

## Known gotchas

- `curl -L` after a successful `POST /login` chases the 302 redirect with
  a re-issued POST and gets `405` from `/`. The login itself succeeded —
  the session cookie is set. Ignore the 405 line in test output.
- StatCrew/Virtius config files (`statcrew_sources.json`,
  `virtius_sources.json`) are not env-isolated; the staging instance
  reads them but the simulators don't drive those paths, so nothing is
  written.
- The Flask dev server logs WebSocket lifecycle at INFO level only.
  Empty `/tmp/edge.log` after handshake is normal — verify via the API.
