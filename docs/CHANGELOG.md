# Changelog

All notable changes to this project will be documented in this file.

## 2026-02-13

- Added TCP/UDP ingestion alongside serial input with auto mode selection.
- Implemented full sport parsing based on the legacy desktop app.
- Added packet-length guards for shared packet types.
- Introduced source tracking endpoints (`/get_sources`, `?source=...`).
- Refreshed the home page and config UI for non-technical users.

## 2026-02-14

- Rebuilt sport scoreboards with a dark UNC-themed design and sport-specific layouts.
- Added dynamic baseball/softball line scores (extra innings) and B/S/O emphasis.
- Added TrackMan UDP config, parsing, and dashboard tiles with debug output.
- Added Gymnastics placeholder page and navigation.
- Reduced polling to 150ms and disabled fetch caching for live clocks.
