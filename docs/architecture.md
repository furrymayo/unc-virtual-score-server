# Architecture

**Last Updated**: 2026-02-17

## Overview

Flask service that ingests live scoreboard packets (serial, TCP, UDP) and renders sport pages in a browser. Parsing logic is based on the legacy desktop app and uses packet-length guards to distinguish sports that share the same packet type. Supports TrackMan UDP for pitch/hit tracking and StatCrew XML for enhanced game stats.

## Data Flow

```
[Scoreboard Devices] --> [TCP/UDP or COM] --> [ingestion.py] --> [protocol.py] --> [parsed_data store]
                                                                                          |
[TrackMan System] -----> [UDP] ---------> [trackman.py] --> [trackman_data store]          |
                                                                    |                      |
[StatCrew XML Files] --> [file watcher] --> [statcrew.py] --> [statcrew_data store]        |
                                                                    |                      |
[Browser] <-- [Templates] <-- [views.py / sports.py] <-- [api.py] <-- accessor functions --+
```

## Module Breakdown

### `website/protocol.py` — Pure parsing (no state, no Flask)
- Protocol constants (STX, CR, type bytes, length constants)
- `PacketStreamParser` — stateful byte stream to packet reassembler
- 6 decoder helpers (`_decode_score`, `_decode_clock`, etc.)
- 9 sport parser functions
- `identify_and_parse(packet)` — dispatch by type+length, returns `(sport, dict)`

### `website/ingestion.py` — Data store + all readers
- Thread-safe shared state: `parsed_data`, `parsed_data_by_source`, `last_seen_by_source`
- Accessor functions: `record_packet()`, `get_sport_data()`, `get_sources_snapshot()`, `purge_stale_sources()`
- Serial reader (uses `threading.Event` for stop signaling)
- TCP client workers (outbound connections to OES controllers, with backoff)
- UDP/TCP inbound listeners
- Data source CRUD helpers (`_load_data_sources`, `_save_data_sources`, etc.)
- Stale source cleanup daemon thread (5min interval, 1hr TTL)

### `website/trackman.py` — TrackMan subsystem
- Separate shared state: `trackman_data`, `trackman_debug`, `trackman_config`
- JSON parser with broadcast + scoreboard format support, NDJSON fallback
- UDP listener per sport (Baseball/Softball)
- Accessor functions: `get_data()`, `get_debug()`, `get_config()`, `update_config()`
- Coordinate system: X=horizontal, Y=depth (toward pitcher), Z=height

### `website/statcrew.py` — StatCrew XML subsystem
- Separate shared state: `statcrew_data`, `statcrew_config`
- XML parser for StatCrew format (venue, teams, players, stats)
- File watcher thread with mtime polling (configurable interval)
- Config persistence via `statcrew_sources.json`
- Accessor functions: `get_data()`, `get_config()`, `update_config()`

### `website/api.py` — API routes blueprint
- 12 REST endpoints, calls accessor functions from ingestion/trackman/statcrew
- No direct state access — all through module functions

### `website/sports.py` — Sport page routes
- Renders Jinja2 templates for each sport + Debug page

### `website/views.py` — Home page

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
| `/data_sources` | GET/POST | List or add TCP data sources |
| `/data_sources/<id>` | DELETE/PATCH | Remove or update a data source |
| `/trackman_config/<sport>` | GET/POST | Configure TrackMan UDP input |
| `/get_trackman_data/<sport>` | GET | Latest parsed TrackMan payload |
| `/get_trackman_debug/<sport>` | GET | Raw TrackMan payload + parse status |
| `/statcrew_config/<sport>` | GET/POST | Configure StatCrew XML file watcher |
| `/get_statcrew_data/<sport>` | GET | Latest parsed StatCrew data |
| `/browse_files?path=...` | GET | Browse server filesystem for XML files |
| `/get_available_com_ports` | GET | List serial ports on the machine |

## Threading Model

- Main thread: Flask web server
- Background threads (all daemon):
  - Serial port reader (1 per active serial source)
  - TCP client workers (1 per configured TCP data source, with reconnect backoff)
  - UDP listener (1 for scoreboard data)
  - TrackMan UDP listeners (1 per enabled sport)
  - StatCrew file watchers (1 per enabled sport, polls mtime every 5s)
  - Stale source cleanup (1, runs every 5 minutes)
