# Flask Virtual Scoreboard

**Last Updated**: 2025-12-30
**Status**: Active
**Primary OS**: Both (Windows + Linux)

## Overview
Flask web application that displays real-time sports scoreboards by reading data from serial COM ports. Supports 10 sports with dedicated display templates.

## Current State
- Core Flask app structure complete
- Serial port reading implemented (COM port configurable via API)
- Volleyball parsing fully implemented; other sports have stub parsers
- Debug page available for testing

## Quick Reference
| Item | Value |
|------|-------|
| Entry point | `main.py` |
| Default port | 5000 (Flask debug) |
| Serial baud | 9600 |
| Supported sports | Basketball, Hockey, Lacrosse, Football, Volleyball, Wrestling, Soccer, Softball, Baseball, Track |

## File Map
| Need to know... | See |
|-----------------|-----|
| System design & data flow | `docs/architecture.md` |
| Serial protocol details | `docs/infrastructure.md` |
| Why we made X decision | `docs/decisions.md` |
| Current blockers/issues | `docs/known-issues.md` |
| Sport-specific parsing | `docs/reference/` |

## Recent Activity
- 2025-12-30: Project structure standardization, credentials secured to .env
- 2023-08-31: Removed UDP/TCP, added COM port dropdown selection
- 2023-08-30: Added data source type update in nav-bar, raw data display
- 2023-08-29: Initial commit
