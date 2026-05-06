# External Access (AWS Edge) Initiative

**Branch**: `external-access` (this branch)
**Companion repo**: https://github.com/furrymayo/unc-virtual-score-edge (private)
**Status**: Milestone 0 complete — scaffolding only; production main is untouched.
**Started**: 2026-05-04

## Goal

Provide authenticated, read-only external access to the on-prem scoreboard for ~100 users with per-sport ACLs, without exposing the on-prem network or modifying production behavior of the existing Flask app.

Campus IT does not allow inbound port forwards or reverse proxies, so all transport is **outbound from on-prem to AWS**.

## Architecture (one paragraph)

A new AWS-hosted Flask service (the "edge") receives live scoreboard state pushed over an outbound WSS connection from a new on-prem module (`website/cloud_relay.py`). The edge mirrors that state in memory, gates access behind admin-issued user accounts with per-sport ACLs, and serves the same TV-optimized templates to external viewers. The on-prem app is unchanged at runtime when the relay is disabled (default).

```
On-prem (UNC)                                     AWS (us-east-1)
┌────────────────────────────────────────┐         ┌────────────────────────────────┐
│  OES / TrackMan / StatCrew / Virtius   │         │   Edge service (separate repo) │
│         (unchanged)                    │         │                                │
│              │                         │         │   WSS server (publisher)       │
│              ▼                         │         │   State mirror (in-mem)        │
│  Flask Virtual Scoreboard (unchanged)  │  WSS    │   Auth + ACL (SQLite)          │
│              │                         │ ◄──────►│   Read-only API + viewer pages │
│              ▼                         │ outbound│                                │
│  cloud_relay.py (NEW, opt-in, gated)   │   443   │                                │
└────────────────────────────────────────┘         └────────────────────────────────┘
                                                                   ▲
                                                                   │ HTTP (Milestone 0–7), revisit before go-live
                                                            External viewers (≤100)
```

## Milestones

| # | Milestone | Repo | Risk to prod |
|---|-----------|------|--------------|
| 0 | Branch on-prem (`external-access`) and scaffold edge repo | both | None — done |
| 1 | Edge skeleton: Flask app, login, user CLI, SQLite | edge | None |
| 2 | Wire protocol + edge WSS server + state mirror, fake publisher | edge | None |
| 3 | Copy/adapt templates, wire to mirrored API, log in and view fake state | edge | None |
| 4 | `cloud_relay.py` on this branch, off by default behind env flag | this branch | None — flag-gated |
| 5 | Stage end-to-end with a second on-prem instance pointed at AWS | both | None |
| 6 | Hardening: rate limits, lockout, log review, HTTPS posture | edge | None |
| 7 | Cut over: enable `CLOUD_RELAY_ENABLED=1` on prod, restart, monitor 24h | prod | Low — flag-gated rollback |
| 8 | Merge `external-access` → `main` | prod | Low — code already running by step 7 |
| 9 | Hand out user credentials | ops | None |

## Key decisions

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-05-04 | Outbound-only WSS from on-prem to AWS | Campus IT does not allow inbound forwards. Outbound 443 is unrestricted. |
| 2026-05-04 | Separate repo for the AWS service (`unc-virtual-score-edge`) | Different runtime, deploy, secrets, release cadence. |
| 2026-05-04 | Per-sport ACL, not per-source | User requirement; simpler model. |
| 2026-05-04 | Read-only viewer endpoints externally — no config plane | User requirement. Keeps `/browse_files`, `/data_sources`, TrackMan/StatCrew/Virtius config off the internet. |
| 2026-05-04 | SQLite for users on AWS | ≤100 users, single instance. |
| 2026-05-04 | EC2 `t4g.small` single instance, no ALB/CloudFront initially | ~$14/mo. |
| 2026-05-04 | Plain HTTP for now, revisit before go-live | User opted out of paying for a domain. HTTPS without a domain requires self-signed (warnings) or paid IP-CA. |
| 2026-05-04 | Admin-only user provisioning via CLI | User requirement: no self-signup. |
| 2026-05-04 | Live state only, no game history | User requirement; keeps state mirror simple. |

## On-prem-side change scope

When Milestone 4 lands, the on-prem footprint is intentionally tiny:

- **One new file**: `website/cloud_relay.py` (~250 lines, single thread, reads existing accessor functions)
- **One new dependency**: `websocket-client` in `requirements.txt`
- **Three new env vars** in `website/config.py`: `CLOUD_RELAY_ENABLED` (default `0`), `CLOUD_RELAY_URL`, `CLOUD_RELAY_KEY`
- **Three lines** added to `main.py` to call `cloud_relay.start()` when enabled
- **Zero edits** to `ingestion.py`, `protocol.py`, `api.py`, `statcrew.py`, `trackman.py`, `virtius.py`, `views.py`, `sports.py`, or any template

If `CLOUD_RELAY_ENABLED` is unset, behavior is byte-for-byte identical to today's `main`.

## Wire protocol

WSS over 443, pre-shared key in handshake header, newline-delimited JSON.

| Type | Direction | Purpose |
|------|-----------|---------|
| `hello` | publisher → edge | Identifies publisher, version negotiation |
| `snapshot` | publisher → edge | Full state replace on connect/reconnect |
| `sport` | publisher → edge | Replace state for one sport |
| `clock` | publisher → edge | High-frequency clock-only update |
| `trackman` | publisher → edge | TrackMan payload for a sport |
| `statcrew` | publisher → edge | StatCrew payload for a sport |
| `virtius` | publisher → edge | Virtius payload for a sport |
| `sources` | publisher → edge | Source list change |
| `ping` / `pong` | both | Keepalive |

State, not events. Bounded send queue drops oldest under backpressure — losing a 200ms-stale packet is correct; the next one is right behind.

## Things explicitly NOT in scope

- Modifying any existing on-prem route, parser, ingestion path, lock, or thread.
- Exposing `/browse_files` or `/mnt/stats` externally.
- Exposing config endpoints externally.
- Adding sessions/auth to the on-prem Flask app.
- Game history / replay.
- Mobile-specific layout.
- User self-signup / password reset / SSO.

## Resuming this work in a new session

1. `cd /mnt/seafile/Seafile/opencode/UNCProjects/flaskVirtualScoreboard`
2. `git checkout external-access`
3. Read this file (`docs/external-access.md`) and the companion plan at `/mnt/seafile/Seafile/opencode/UNCProjects/unc-virtual-score-edge/docs/plan.md`
4. Next milestone is **#1 — Edge skeleton (Flask app, login, user CLI, SQLite)** in the companion repo.
5. AWS access is not yet configured; user will create a dedicated IAM user and run `aws configure --profile unc-edge` when Milestone 1 needs it.
