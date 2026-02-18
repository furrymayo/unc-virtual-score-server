# Flask Virtual Scoreboard

**Last Updated**: 2026-02-18
**Status**: Active
**Primary OS**: Both (Windows + Linux)
**Repo**: https://github.com/furrymayo/unc-virtual-score-server

## Overview
Flask web application that displays real-time sports scoreboards by reading data from OES serial controllers over TCP, UDP, or serial COM ports. Supports 10 sports with dedicated display templates. Optional TrackMan UDP integration for Baseball/Softball pitch/hit tracking. StatCrew XML integration for enhanced stats display.

## Current State
- Modular architecture: monolith refactored into 7 focused modules
- All 10 sport parsers fully implemented
- TCP data source management with persistence (data_sources.json)
- Duplicate host:port data sources supported (auto-suffixed IDs: `:2`, `:3`, etc.)
- Per-source `sport_overrides` for Gymnastics (Lacrosse → Gymnastics remap)
- Home page sport override dropdown for assigning overrides to data sources
- TrackMan UDP integration for Baseball/Softball (strike zone visualization)
- Virtius live scoring API integration for Gymnastics (polls `api.virti.us`)
- Virtius watchers auto-start on server boot from `virtius_sources.json`
- Virtius includes exhibition gymnasts in lineups, running all-around leaders from 2+ events
- StatCrew XML integration with `<status>` element for real-time game state (current pitcher, batter, batting team, pitch count)
- StatCrew `<pitching appear>` attribute for accurate pitcher detection after substitutions
- Live pitch count: `<pitching pitches>` (cumulative) + `<status np>` (current at-bat) — self-correcting
- StatCrew `batord` elements reflect live lineup changes (substitutions, pinch hitters)
- StatCrew network share mounted at `/mnt/stats` on Ubuntu server (CIFS, persistent)
- StatCrew poll interval: 2s (file mtime check 0.3ms, full parse 10ms)
- 95 pytest tests covering protocol, ingestion, trackman, statcrew, and API
- systemd deployment config for Ubuntu server
- Stale source cleanup thread (1hr TTL, 5min interval)
- innerHTML XSS vulnerabilities fixed in Debug and home templates
- TV-optimized UI: thin single-row navbar, raised clamp() ceilings for large-screen readability
- TV-optimized Gymnastics layout: rotation bar, team scores, clock, lineup cards, all-around leaders
- Softball layout mirrors Baseball: [Pitching|Inning|AtBat] top row, [Away|B/S/O|Home] score row, 7-inning linescore (no TrackMan)
- Baseball layout: [Pitching|Inning|AtBat] top row, [Away|B/S/O|Home] score row, linescore in center column
- Baseball strike zone uses correct 3:4 portrait aspect ratio (17"×24" real proportions)
- OES baseball batter_num 0x3A blank handling fixed in protocol.py

## Quick Reference
| Item | Value |
|------|-------|
| Entry point | `main.py` |
| Default port | 5000 (Flask) |
| Serial baud | 9600 |
| Supported sports | Basketball, Hockey, Lacrosse, Football, Volleyball, Wrestling, Soccer, Softball, Baseball, Gymnastics |
| Test command | `pytest tests/ -v` |
| Deploy guide | `README.md` |

## Module Map
| Module | Responsibility |
|--------|---------------|
| `main.py` | Slim entry point, starts app + background threads (ingestion, statcrew, virtius) |
| `website/__init__.py` | App factory, registers 3 blueprints (views, sports, api) |
| `website/views.py` | Home page route |
| `website/sports.py` | Sport page routes (renders templates) |
| `website/api.py` | 14 API routes (Blueprint), calls ingestion/trackman/statcrew/virtius accessors |
| `website/protocol.py` | Protocol constants, PacketStreamParser, decoders, 9 sport parsers, `identify_and_parse()` |
| `website/ingestion.py` | Data store, serial/TCP/UDP readers, source management, cleanup thread |
| `website/trackman.py` | TrackMan state, JSON parser, UDP listener, config management |
| `website/statcrew.py` | StatCrew XML parser, file watcher thread, config persistence |
| `website/virtius.py` | Virtius live scoring API poller, session parser, config persistence |

## Dependency Graph (no cycles)
```
protocol.py      → (nothing)
trackman.py      → (nothing in website/)
statcrew.py      → (nothing in website/)
virtius.py       → (nothing in website/)
ingestion.py     → protocol
api.py           → ingestion, trackman, statcrew, virtius
__init__.py      → views, sports, api
main.py          → website (create_app), ingestion, statcrew, virtius
```

## File Map
| Need to know... | See |
|-----------------|-----|
| System design & data flow | `docs/architecture.md` |
| Serial protocol details | `docs/infrastructure.md` |
| Why we made X decision | `docs/decisions.md` |
| Current blockers/issues | `docs/known-issues.md` |
| Deployment instructions | `README.md` |
| Sport-specific parsing | `docs/reference/` |

## StatCrew XML Key Elements
| Element | Purpose |
|---------|---------|
| `<status>` | Real-time game state: `batter`, `pitcher`, `vh` (batting team), `np` (pitches in current at-bat), `b`/`s` (count), `outs`, `inning` |
| `<pitching appear="N">` | Order of pitcher appearance — highest value = most recently entered pitcher per team |
| `<pitching pitches="X">` | Cumulative pitch count — only updates after completed at-bats |
| `<batord>` | Live batting order — updates with substitutions (pinch hitters get `in`/`seq` attrs) |
| `<pitches text="BKSFP">` | Per-at-bat pitch sequence within `<play>` elements |
| `<innsummary>` | Present when a half-inning is complete |

## Recent Activity
- 2026-02-18: Softball rewrite — mirrors Baseball layout (Pitching/Inning/AtBat top row, Away/B-S-O/Home score row, 7-inning linescore), removed TrackMan elements, OES fallback for pitcher/batter. Cleaned up dead files (auth.py, models.py). Added `virtius_sources.json` for boot persistence.
- 2026-02-18: Gymnastics overhaul — TV-optimized template (rotation bar, team scores, clock, lineup cards, all-around leaders), Virtius API integration with exhibition gymnasts and running AA totals, duplicate host:port data sources with auto-suffixed IDs, home page sport override dropdown, Virtius auto-start on boot
- 2026-02-18: Baseball real-time: `<status>` element for live batter/pitcher/batting team, `appear` attr for pitcher detection after subs, live pitch count (`pitches` + `np`), reduced poll/fetch to 2s, TV layout restructure (compact cards, center linescore)
- 2026-02-17: TV readability overhaul — collapsed navbar to thin bar, raised all clamp() ceilings (~2x primary, ~1.5x secondary), fixed baseball TrackMan card overflow, strike zone 3:4 portrait ratio, linescore static Away/Home labels, reduced team score cards, added `away_code`/`home_code` to statcrew parser
- 2026-02-17: Added Gymnastics sport_overrides, CIFS network share mount for StatCrew (`/mnt/stats`), StatCrew XML integration, redesigned Baseball page, fixed strike zone coordinate mapping (needs live verification)
- 2026-02-16: Major refactor — split main.py monolith into 5 modules, added tests, systemd deploy, XSS fixes, pushed to new repo (unc-virtual-score-server)
- 2026-02-14: Rebuilt sport UIs with dark UNC theme, added TrackMan dashboard
- 2026-02-13: Added TCP/UDP ingestion, full sport parsers, source tracking
- 2025-12-30: Project structure standardization, credentials secured to .env
