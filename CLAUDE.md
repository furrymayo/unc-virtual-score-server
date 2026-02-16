# Flask Virtual Scoreboard

**Last Updated**: 2026-02-16
**Status**: Active
**Primary OS**: Both (Windows + Linux)
**Repo**: https://github.com/furrymayo/unc-virtual-score-server

## Overview
Flask web application that displays real-time sports scoreboards by reading data from OES serial controllers over TCP, UDP, or serial COM ports. Supports 10 sports with dedicated display templates. Optional TrackMan UDP integration for Baseball/Softball pitch/hit tracking.

## Current State
- Modular architecture: monolith refactored into 5 focused modules
- All 10 sport parsers fully implemented
- TCP data source management with persistence (data_sources.json)
- TrackMan UDP integration for Baseball/Softball
- 47 pytest tests covering protocol, ingestion, trackman, and API
- systemd deployment config for Ubuntu server
- Stale source cleanup thread (1hr TTL, 5min interval)
- innerHTML XSS vulnerabilities fixed in Debug and home templates

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
| `main.py` | Slim entry point (~12 lines), starts app + background threads |
| `website/__init__.py` | App factory, registers 3 blueprints (views, sports, api) |
| `website/views.py` | Home page route |
| `website/sports.py` | Sport page routes (renders templates) |
| `website/api.py` | 9 API routes (Blueprint), calls ingestion/trackman accessors |
| `website/protocol.py` | Protocol constants, PacketStreamParser, decoders, 9 sport parsers, `identify_and_parse()` |
| `website/ingestion.py` | Data store, serial/TCP/UDP readers, source management, cleanup thread |
| `website/trackman.py` | TrackMan state, JSON parser, UDP listener, config management |

## Dependency Graph (no cycles)
```
protocol.py      → (nothing)
trackman.py      → (nothing in website/)
ingestion.py     → protocol
api.py           → ingestion, trackman
__init__.py      → views, sports, api
main.py          → website (create_app), ingestion
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

## Recent Activity
- 2026-02-16: Major refactor — split main.py monolith into 5 modules, added tests, systemd deploy, XSS fixes, pushed to new repo (unc-virtual-score-server)
- 2026-02-14: Rebuilt sport UIs with dark UNC theme, added TrackMan dashboard
- 2026-02-13: Added TCP/UDP ingestion, full sport parsers, source tracking
- 2025-12-30: Project structure standardization, credentials secured to .env
- 2023-08-31: Removed UDP/TCP, added COM port dropdown selection
