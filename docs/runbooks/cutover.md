# Production cutover: enable the cloud relay

Goal: turn `CLOUD_RELAY_ENABLED=1` on the production on-prem instance,
restart, and confirm state mirrors to the AWS edge service. Rollback is
a one-line env change plus a restart — the relay is fully flag-gated.

## Pre-conditions (do these first)

1. **Edge is deployed and reachable on AWS.** A `wss://` URL exists. The
   edge service is running on a `t4g.small` (or equivalent) with
   `PUBLISHER_AUTH_TOKEN` set in its environment.
2. **A real publisher token has been generated** and stored somewhere
   safe (e.g. team password vault):
   ```bash
   python3 -c 'import secrets; print(secrets.token_urlsafe(48))'
   ```
   Set the same value as `PUBLISHER_AUTH_TOKEN` on the edge and as
   `CLOUD_RELAY_TOKEN` on prod.
3. **At least one viewer account exists on the edge** with sport ACL,
   provisioned via `flask user create` / `flask user grant`.
4. **HTTPS is decided.** If go-live is exposing real users, work
   through `docs/runbooks/https.md` *before* this cutover so users hit
   `https://`. If staging only, plain HTTP is fine and the relay URL is
   `wss://` regardless (the WSS path can run over either).

## Pre-flight on prod (no flag flip yet)

The prod instance is still running with `CLOUD_RELAY_ENABLED=0` (the
default). Validate the relay credentials *without* turning anything on:

```bash
cd /opt/scoreboard
sudo -u scoreboard \
  CLOUD_RELAY_URL=wss://<edge-host>/ws/publisher \
  CLOUD_RELAY_TOKEN=<token> \
  CLOUD_RELAY_PUBLISHER_NAME=onprem-prod \
  /opt/scoreboard/venv/bin/python scripts/preflight_relay.py
```

Expected: `OK: hello accepted, pong received. Relay credentials are valid.`

If it fails:

- Exit `1` → URL or network. Check DNS, firewall, that 443 outbound is
  unrestricted from the prod box.
- Exit `2` → token mismatch or IP allowlist. Cross-check
  `PUBLISHER_AUTH_TOKEN` on the edge and `PUBLISHER_ALLOWED_IPS` (if
  set).

Do **not** proceed to the flag flip until preflight returns 0.

## Cutover

1. **Append the relay env to `/opt/scoreboard/.env`:**
   ```ini
   CLOUD_RELAY_ENABLED=1
   CLOUD_RELAY_URL=wss://<edge-host>/ws/publisher
   CLOUD_RELAY_TOKEN=<token>
   CLOUD_RELAY_PUBLISHER_NAME=onprem-prod
   CLOUD_RELAY_POLL_INTERVAL=0.5
   ```

2. **Restart the service:**
   ```bash
   sudo systemctl restart scoreboard
   sudo systemctl status scoreboard --no-pager
   ```

3. **Watch the prod log for the relay startup line:**
   ```bash
   sudo journalctl -u scoreboard -f
   # Expect: cloud relay started → wss://<edge-host>/ws/publisher
   ```
   No relay-related WARN lines should appear after the first second.

4. **Confirm the edge sees the publisher.**
   On the edge box (or wherever `AUTH_LOG_FILE` is shipped):
   ```bash
   tail -f $AUTH_LOG_FILE | jq -c 'select(.event | startswith("publisher"))'
   # Expect: {"event":"publisher_connect","publisher":"onprem-prod",...}
   ```
   Then hit a viewer route as a real user and confirm live data renders.

## What to monitor for the first 24 hours

| Signal | Where | Healthy | Investigate |
|--------|-------|---------|-------------|
| Relay reconnect storm | prod `journalctl` | < 1 reconnect/hour | repeated `cloud relay session ended` lines |
| State staleness | edge `/get_sources` `age_seconds` | seconds | minutes |
| Publisher disconnects | edge `auth.log` | 0 unexpected | repeated `publisher_disconnect` without `publisher_connect` after |
| Login failures | edge `auth.log` | < users × 3 / day | spikes or `login_locked_out` from real users |
| Memory growth | prod `systemctl status` | flat | climbing (relay leaks) |

`grep cloud_relay /var/log/syslog` and `journalctl -u scoreboard --since "1 hour ago"` are useful spot checks.

## Rollback

The relay is the only behavior change. Rollback is one line:

1. Edit `/opt/scoreboard/.env`:
   ```ini
   CLOUD_RELAY_ENABLED=0
   ```
2. `sudo systemctl restart scoreboard`

The prod app comes back identical to its pre-cutover behavior. No
database migration to undo, no code rollback needed. If a deeper
rollback is required (e.g. revert the on-prem code itself), check out
`main` (pre-`external-access` merge) and redeploy.

## After 24 hours

If all signals stay green:

- Move to **Milestone 8**: merge `external-access` → `main` on the
  on-prem repo. The code is already running in prod; the merge is just
  bookkeeping.
- Then **Milestone 9**: hand out user credentials.

If anything looked off, leave the relay disabled, capture the prod and
edge logs from the affected window, and triage before retrying.
