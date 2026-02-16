# Architecture

**Last Updated**: 2026-02-13

## Overview

Flask service that ingests live scoreboard packets (serial, TCP, UDP) and renders sport pages in a browser. Parsing logic is based on the legacy desktop app and uses packet-length guards to distinguish sports that share the same packet type.

## Data Flow

```
[Scoreboard Devices] --> [TCP/UDP or COM] --> [Flask Backend] --> [Templates] --> [Browser]
```

## Components

### Backend (Flask)
- `main.py` - Entry point, serial/TCP/UDP readers, parsers, REST API
- `website/__init__.py` - App factory
- `website/views.py` - Main view routes
- `website/auth.py` - Sport-specific routes

### Frontend (Jinja2 Templates)
- `website/Templates/` - Sport-specific scoreboard displays
- `website/static/` - CSS, JS, images

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Home page |
| `/<Sport>` | GET | Sport-specific scoreboard |
| `/Debug` | GET | Debug page |
| `/get_raw_data/<sport>` | GET | Get parsed data for sport (latest) |
| `/get_raw_data/<sport>?source=...` | GET | Get parsed data for sport by source |
| `/get_sources` | GET | List active sources and last seen times |
| `/update_server_config` | POST | Update data source config |
| `/trackman_config/<sport>` | GET/POST | Configure TrackMan UDP input |
| `/get_trackman_data/<sport>` | GET | Latest parsed TrackMan payload |
| `/get_trackman_debug/<sport>` | GET | Raw TrackMan payload + parse status |

## Threading Model

- Main thread: Flask web server
- Background threads: serial reader, TCP listener, UDP listener, TCP connection readers

## Session Summary

- Added TrackMan UDP ingestion + debug feed for baseball/softball.
- Built sport-specific scoreboard layouts with a dark UNC theme and high-frequency polling.
- Added Gymnastics placeholder route for future expansion.
