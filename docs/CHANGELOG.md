# Changelog

All notable changes to this project will be documented in this file.

## 2026-02-16

- **Major refactor**: Split 1527-line `main.py` monolith into 5 focused modules (`protocol.py`, `ingestion.py`, `trackman.py`, `api.py`, `sports.py`).
- Renamed `auth.py` → `sports.py` (blueprint renamed accordingly).
- Added `identify_and_parse()` dispatch function to `protocol.py`.
- Converted thread-stop bools to `threading.Event` for thread safety.
- Added stale source cleanup daemon thread (1hr TTL, 5min interval).
- Fixed innerHTML XSS in `Debug.html` and `home.html` (replaced with `textContent`).
- Added 47 pytest tests across protocol, ingestion, trackman, and API modules.
- Added systemd unit file (`deploy/scoreboard.service`) for Ubuntu server deployment.
- Added `README.md` with full deployment instructions and `.env` configuration guide.
- Added `.gitignore`, removed tracked IDE files (`.idea/`, `.vs/`).
- Deleted stale files (`main.py.auth`, `.bak`, `.final`, `final_main.py`, `models.py`).
- Bound Flask to `0.0.0.0` by default; host/port/debug configurable via environment.
- Pushed to new repo: `furrymayo/unc-virtual-score-server`.

## 2026-02-14

- Rebuilt sport scoreboards with a dark UNC-themed design and sport-specific layouts.
- Added dynamic baseball/softball line scores (extra innings) and B/S/O emphasis.
- Added TrackMan UDP config, parsing, and dashboard tiles with debug output.
- Added Gymnastics placeholder page and navigation.
- Reduced polling to 150ms and disabled fetch caching for live clocks.

## 2026-02-13

- Added TCP/UDP ingestion alongside serial input with auto mode selection.
- Implemented full sport parsing based on the legacy desktop app.
- Added packet-length guards for shared packet types.
- Introduced source tracking endpoints (`/get_sources`, `?source=...`).
- Refreshed the home page and config UI for non-technical users.
