# Changelog

All notable changes to this project will be documented in this file.

## 2026-02-18

### Gymnastics Page Overhaul
- Full TV-optimized Gymnastics template: rotation bar, Home|Clock|Away grid, lineup cards, all-around leaders panel.
- Virtius live scoring API integration: polls `api.virti.us/session/{key}/json` for real-time NCAA gymnastics data.
- Exhibition gymnasts now included in lineup displays with visual `counting` flag to distinguish from scoring athletes.
- Running all-around leaders update throughout the meet (2+ events threshold instead of waiting for all 4).
- Collapsible Virtius config panel at bottom of Gymnastics page (hidden during broadcast).

### Duplicate Host:Port Data Sources
- TCP data sources with the same host:port now get auto-suffixed unique IDs (`:2`, `:3`, etc.) instead of being rejected.
- Enables a single OES controller to feed both Lacrosse and Gymnastics pages simultaneously with different sport overrides.
- Added `_make_unique_source_id()` to `ingestion.py`.
- Updated test suite to verify sequential duplicate source creation.

### Home Page Data Source UI
- Added "Sport Override" dropdown to the data source form (currently supports Lacrosse → Gymnastics).
- Source list displays active overrides in brackets (e.g., `[Lacrosse → Gymnastics]`).
- Edit mode preserves and restores sport override selection.
- Replaced CSS Grid layout with custom flexbox for reliable single-row form alignment.

### Virtius Auto-Start
- Virtius configured watchers now start automatically on server boot from persisted `virtius_sources.json`.
- Previously, watchers only started when manually saved via the config API.

### Other
- Fixed `sports.py` Gymnastics route rendering wrong template (`copyPasta.html` → `Gymnastics.html`).
- Gymnastics template uses compound CSS selector (`.scoreboard-shell.gym-shell`) to override base viewport height, allowing config panel to be visible below the scoreboard.

## 2026-02-17

### StatCrew XML Integration
- Added `website/statcrew.py` module for parsing StatCrew XML files (venue, teams, players, stats).
- Added file watcher thread with mtime polling (configurable interval, default 5s).
- Added API endpoints: `GET/POST /statcrew_config/<sport>`, `GET /get_statcrew_data/<sport>`.
- Added `GET /browse_files` endpoint for server-side file browser (XML file selection).
- Config persistence via `statcrew_sources.json`.
- Updated `main.py` to start StatCrew watchers on boot.

### Baseball Page Redesign
- Redesigned Baseball scoreboard with StatCrew data integration:
  - Team names, records, and LOB from StatCrew XML.
  - Stadium/location and weather display in header.
  - Current pitcher card with IP, K, pitch count.
  - Current batter card with H-AB, RBI, AVG.
  - Center-stacked Inning/Pitching/At Bat cards layout.
- Narrower TrackMan dashboard with rounded values (tenths).
- Larger strike zone canvas with smaller grid for better ball tracking.
- Added "Additional Data Sources" collapsible panel for config UI.

### Strike Zone Coordinate Fixes
- Fixed vertical coordinate mapping: now uses Z (height) instead of Y (depth).
  - TrackMan coordinates: X=horizontal, Y=depth toward pitcher, Z=height.
- Removed incorrect xOffset (1.42) and xScale (0.85) calibration values.
  - TrackMan X is already centered at 0 (center of plate).
- **Note**: Awaiting verification with live TrackMan data.

### Gymnastics Special Case
- Added per-source `sport_overrides` so a gymnastics venue can remap Lacrosse-coded packets to Gymnastics.
- Gymnastics parsing now consumes only the running clock from Lacrosse packets.
- Data source API supports `sport_overrides` on create/update.

### StatCrew Network Share (Server)
- Added CIFS mount instructions to `README.md` for persistent network share at `/mnt/stats`.
- Credentials stored in `/etc/credentials-statcrew` (mode 600) on the Ubuntu server.
- Persistent via `/etc/fstab` with `_netdev,nofail` options.
- StatCrew XML files browsable from the app's config UI via `/browse_files`.

### Other
- Added `tests/test_statcrew.py` with unit tests for StatCrew parsing.
- Added `examples/baseballDataStats.xml` sample StatCrew file.
- Added CSS/JS helpers in `base.html` for data sources panel and file browser modal.

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
